"""
TaxBuddyApp/ai_guard.py — Phase 0 of the TaxBuddy Umair AI upgrade.

  1. Shared limits   : per-IP + per-session hourly limits and site-wide daily caps
                       (questions, tokens, USD) kept in a cache that ALL Gunicorn
                       workers share (settings.CACHES["ai"] = DatabaseCache).
  2. Server history  : conversation turns are stored on the server per
                       (browser session, chat id). Assistant turns sent by the
                       browser are never trusted (prompt-injection guard).
  3. Usage logging   : one AIUsage row per answer — tokens, cost, tools, latency.

No raw IP, session key, question text or NTN/CNIC is stored: only salted hashes
and lengths.
"""
import hashlib
import logging
import re
import time

from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.base import InvalidCacheBackendError

logger = logging.getLogger(__name__)

# ── tunables (override any of these in settings / .env) ──────────────────────
def _s(name, default):
    return getattr(settings, name, default)

SESSION_HOURLY = int(_s("AI_SESSION_HOURLY_LIMIT", 25))     # per browser session / hour
IP_HOURLY = int(_s("AI_IP_HOURLY_LIMIT", 40))                # per IP address / hour
DAILY_QUESTIONS = int(_s("AI_DAILY_LIMIT", 400))             # whole site / day
DAILY_TOKENS = int(_s("AI_DAILY_TOKEN_LIMIT", 4_000_000))    # whole site / day (0 = off)
DAILY_BUDGET_USD = float(_s("AI_DAILY_BUDGET_USD", 0) or 0)  # whole site / day (0 = off)
# USD per million tokens for AI_MODEL — copy from Anthropic's pricing page.
PRICE_IN = float(_s("AI_PRICE_INPUT_PER_MTOK", 0) or 0)
PRICE_OUT = float(_s("AI_PRICE_OUTPUT_PER_MTOK", 0) or 0)
CACHE_WRITE_X = 1.25        # prompt-cache write = 1.25 x input price
CACHE_READ_X = 0.10         # prompt-cache read  = 0.10 x input price

HISTORY_TURNS = 16          # stored per chat (8 user + 8 assistant)
HISTORY_CHARS = 4000        # per stored turn
HISTORY_TTL = 60 * 60 * 24 * 14   # keep a chat's server history 14 days


def _cache():
    try:
        return caches["ai"]
    except InvalidCacheBackendError:     # settings not updated yet → still works per worker
        return caches["default"]


def _hash(value):
    salt = settings.SECRET_KEY[:16]
    return hashlib.sha256((salt + str(value or "")).encode()).hexdigest()[:24]


# ── who is asking ────────────────────────────────────────────────────────────
_LOOPBACK = {"", "127.0.0.1", "::1", "localhost", "unix"}

def client_ip(request):
    """Real client IP behind Nginx. Uses X-Real-IP (set by nginx), else the LAST
    X-Forwarded-For hop (the one nginx appended), else REMOTE_ADDR."""
    ip = request.META.get("HTTP_X_REAL_IP", "").strip()
    if not ip:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            ip = xff.split(",")[-1].strip()
    if not ip:
        ip = request.META.get("REMOTE_ADDR", "").strip()
    return ip


def session_id(request):
    if not request.session.session_key:
        request.session["ai"] = 1            # make sure a session exists
        request.session.save()
    return request.session.session_key


# ── limits ───────────────────────────────────────────────────────────────────
def _bump(key, ttl):
    c = _cache()
    if c.add(key, 1, ttl):
        return 1
    try:
        return c.incr(key)
    except ValueError:                       # expired between add and incr
        c.set(key, 1, ttl)
        return 1


def _today():
    return time.strftime("%Y%m%d")


def check_limits(request):
    """Return None if the request may go ahead, else a user-facing message.
    Counts this request against the hourly and daily question limits."""
    c = _cache()
    hour = time.strftime("%Y%m%d%H")
    sid = _hash(session_id(request))
    if _bump(f"ai:s:{sid}:{hour}", 3700) > SESSION_HOURLY:
        return "You've reached the hourly limit. Please try again later."
    ip = client_ip(request)
    if ip in _LOOPBACK:
        logger.warning("AI guard: no client IP (nginx must send X-Real-IP); IP limit skipped")
    elif _bump(f"ai:ip:{_hash(ip)}:{hour}", 3700) > IP_HOURLY:
        return "Too many questions from your network this hour. Please try again later."
    day = _today()
    if DAILY_TOKENS and (c.get(f"ai:tok:{day}") or 0) >= DAILY_TOKENS:
        return "The AI assistant is busy today. Please try again tomorrow."
    if DAILY_BUDGET_USD and (c.get(f"ai:usd_micro:{day}") or 0) >= DAILY_BUDGET_USD * 1_000_000:
        return "The AI assistant is busy today. Please try again tomorrow."
    if _bump(f"ai:q:{day}", 60 * 60 * 26) > DAILY_QUESTIONS:
        return "The AI assistant is busy today. Please try again tomorrow."
    return None


# ── usage + cost ─────────────────────────────────────────────────────────────
class Usage:
    """Adds up token usage over every Claude call in one answer."""
    def __init__(self, model):
        self.model = model
        self.input = self.output = self.cache_write = self.cache_read = 0
        self.calls = 0
        self.tools = []
        self.t0 = time.time()

    def add(self, usage):
        if usage is None:
            return
        self.calls += 1
        self.input += getattr(usage, "input_tokens", 0) or 0
        self.output += getattr(usage, "output_tokens", 0) or 0
        self.cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0

    @property
    def tokens(self):
        return self.input + self.output + self.cache_write + self.cache_read

    @property
    def cost_usd(self):
        if not PRICE_IN:
            return 0.0
        return (self.input * PRICE_IN + self.output * PRICE_OUT
                + self.cache_write * PRICE_IN * CACHE_WRITE_X
                + self.cache_read * PRICE_IN * CACHE_READ_X) / 1_000_000


def record(request, endpoint, usage, status="ok", question=""):
    """Save one AIUsage row and update today's shared token / cost counters.
    Never raises — logging must not break the chat."""
    try:
        c = _cache()
        day = _today()
        ttl = 60 * 60 * 26
        if not c.add(f"ai:tok:{day}", usage.tokens, ttl):
            try:
                c.incr(f"ai:tok:{day}", usage.tokens)
            except ValueError:
                c.set(f"ai:tok:{day}", usage.tokens, ttl)
        micro = int(round(usage.cost_usd * 1_000_000))
        if micro and not c.add(f"ai:usd_micro:{day}", micro, ttl):
            try:
                c.incr(f"ai:usd_micro:{day}", micro)
            except ValueError:
                c.set(f"ai:usd_micro:{day}", micro, ttl)

        from .models import AIUsage
        AIUsage.objects.create(
            endpoint=endpoint,
            model=usage.model[:60],
            session_hash=_hash(request.session.session_key) if request.session.session_key else "",
            ip_hash=_hash(client_ip(request)),
            question_chars=len(question or ""),
            input_tokens=usage.input,
            output_tokens=usage.output,
            cache_write_tokens=usage.cache_write,
            cache_read_tokens=usage.cache_read,
            api_calls=usage.calls,
            cost_usd=round(usage.cost_usd, 6),
            tools=",".join(usage.tools)[:500],
            latency_ms=int((time.time() - usage.t0) * 1000),
            status=status[:20],
        )
    except Exception:
        logger.exception("AI usage logging failed")


# ── server-side conversation history ─────────────────────────────────────────
_CID = re.compile(r"^[a-z0-9]{6,40}$")

def _hist_key(request, cid):
    return f"ai:h:{_hash(session_id(request))}:{cid}"


def clean_cid(value):
    value = str(value or "").strip().lower()
    return value if _CID.match(value) else ""


def load_history(request, cid):
    if not cid:
        return []
    turns = _cache().get(_hist_key(request, cid)) or []
    return [t for t in turns if t.get("role") in ("user", "assistant") and t.get("content")]


def save_turns(request, cid, user_text, answer_text):
    """Append one finished exchange to the chat's server history."""
    if not cid or not answer_text.strip():
        return
    turns = load_history(request, cid)
    turns += [{"role": "user", "content": user_text[:HISTORY_CHARS]},
              {"role": "assistant", "content": answer_text[:HISTORY_CHARS]}]
    _cache().set(_hist_key(request, cid), turns[-HISTORY_TURNS:], HISTORY_TTL)


def drop_last_exchange(request, cid, user_text):
    """Regenerate: remove the last stored exchange if it answered the same question."""
    turns = load_history(request, cid)
    if len(turns) >= 2 and turns[-2]["role"] == "user" and turns[-2]["content"] == user_text[:HISTORY_CHARS]:
        _cache().set(_hist_key(request, cid), turns[:-2], HISTORY_TTL)


def build_messages(request, data, max_input_chars):
    """Return (cid, user_msg, messages) for Claude.

    History comes from the SERVER store for this chat. If the server has none
    (a chat started before this upgrade), only the user's own earlier questions
    are taken from the browser — never 'assistant' turns, which a user could forge.
    """
    user_msg = (data.get("message") or "").strip()[:max_input_chars]
    cid = clean_cid(data.get("cid"))
    if cid and data.get("regen"):
        drop_last_exchange(request, cid, user_msg)
    turns = load_history(request, cid)
    if not turns:
        for t in (data.get("history") or [])[-HISTORY_TURNS:]:
            if isinstance(t, dict) and t.get("role") == "user" and t.get("content"):
                turns.append({"role": "user", "content": str(t["content"])[:max_input_chars]})
    msgs = []
    for t in turns:
        if msgs and msgs[-1]["role"] == t["role"]:          # API needs alternating roles
            msgs[-1]["content"] += "\n\n" + t["content"]
        else:
            msgs.append({"role": t["role"], "content": t["content"]})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if msgs and msgs[-1]["role"] == "user" and user_msg:      # earlier unanswered question
        msgs[-1]["content"] += "\n\n" + user_msg
    elif user_msg:
        msgs.append({"role": "user", "content": user_msg})
    return cid, user_msg, msgs
