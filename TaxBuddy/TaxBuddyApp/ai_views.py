# ════════════════════════════════════════════════════════════════
#  AI FEATURES — add to TaxBuddyApp (new file: TaxBuddyApp/ai_views.py)
#  1) AI Pakistan Tax Assistant (chatbot)   → /ai-chat/  + /api/ai-chat/
#  2) AI Smart Tax Calculator               → /ai-tax-calculator/ + /api/ai-smart-calc/
#
#  Backend: Anthropic Claude API (key stays server-side, never exposed).
#
#  SETUP (one-time):
#    pip install anthropic
#    # settings.py:
#    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")   # put the key in env, NOT in code
#    AI_MODEL          = os.environ.get("AI_MODEL", "claude-haiku-5-5")
#    AI_DAILY_LIMIT    = 400   # optional: max AI questions per day for the whole site
#    # ^ set AI_MODEL to a model your API key can use. See docs.claude.com for current model IDs.
#    #   Haiku = cheapest/fast (good here). Switch to a Sonnet model for deeper reasoning.
# ════════════════════════════════════════════════════════════════
import json
import logging
import time

from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

logger = logging.getLogger(__name__)

from . import agent_tools

# ── Agent instructions ──
SYSTEM_PROMPT = """You are "TaxBuddy Umair AI", the Pakistan tax assistant on taxbuddyumair.com, a free tax-education platform by Umair Mubeen (a Pakistani tax educator).

YOU HAVE TOOLS. USE THEM — never answer from memory:
- Any tax amount -> calculate_income_tax (salary / business / AOP / rental slabs from the site database) or find_wht_rates then calculate_wht (withholding & advance tax: property 236C/236K, vehicles, bank profit, rent, contracts, etc.).
- Any rate -> find_wht_rates or calculate_income_tax. Quote the rate the tool returns.
- "Am I / is this NTN a filer?" -> check_atl.
- Latest SROs, circulars, notifications -> find_sro.
- Legal questions (what the law says, conditions, definitions, penalties, procedures) -> search_law, then get_law_section for the exact section. Cite the book and section, e.g. "Section 147A, Income Tax Ordinance 2001".
- After answering, call find_blog once and add the most relevant article link if one exists.
- If a tool returns nothing or an error, say you could not verify it. Do NOT guess numbers, sections or dates.

HOW TO ANSWER:
- Reply in the user's language: English, or Roman Urdu if they write Roman Urdu.
- Start with the bottom line (the amount, rate or yes/no), then a short breakdown. Keep it short.
- Show the working for calculations (slab, fixed tax, rate on the excess, surcharge).
- Give site links as relative paths, e.g. /articles/slug/ or /SalaryCalculator/.
- If key information is missing (monthly vs yearly, filer or not), ask one short question or state the assumption.

LIMITS:
- Educational information only, not professional tax, legal or financial advice. For complex cases suggest a qualified tax practitioner, or WhatsApp TaxBuddy Umair at +92 333 248 2742.
- TaxBuddy Umair is an independent educator, not affiliated with FBR.
- Only Pakistan tax topics. Never ask for passwords, card numbers or bank details. An NTN or CNIC may be used only for the ATL check and must not be repeated back in full."""

CHAT_PAGE_PROMPT = SYSTEM_PROMPT + """

THIS IS THE FULL-PAGE TAXBUDDY AI CHAT.
- TAX ONLY: answer questions on Pakistan income tax, sales tax, withholding / advance tax, FBR procedures (NTN, IRIS, ATL, returns, notices), FED and customs basics, and the TaxBuddy site's own tools. For anything else (coding, general knowledge, homework in other subjects, chit-chat beyond a greeting), reply in one friendly line that you only help with Pakistan tax, and suggest one tax question they could ask.
- Do not write any text before calling tools; call the tools first, then write the answer once.
- Use markdown: a short bold bottom line, then bullets or a small table where it helps. No headings larger than ###.
- When you used a law section, end with a line "**Reference:** Section X, <book>"."""

# Friendly progress labels shown in the chat while a tool runs
_BOOK_NAMES = {"ito": "Income Tax Ordinance 2001", "it_rules": "Income Tax Rules 2002",
               "sta": "Sales Tax Act 1990", "st_rules": "Sales Tax Rules 2006"}


def _tool_status(name, args):
    args = args or {}
    book = _BOOK_NAMES.get(args.get("book"), "the law books")
    return {
        "calculate_income_tax": "Calculating tax from the slab table…",
        "find_wht_rates": "Looking up the withholding tax rate card…",
        "calculate_wht": "Calculating withholding tax…",
        "check_atl": "Checking the Active Taxpayers List…",
        "find_sro": "Searching SROs and notifications…",
        "find_blog": "Finding a related TaxBuddy guide…",
        "search_law": f"Searching {book}…",
        "get_law_section": f"Reading Section {args.get('number', '')} — {book}…",
    }.get(name, "Working…")


def _tool_sources(name, args, result):
    """Turn one tool call into source chips for the UI: [{label, url}]."""
    out = []
    if not isinstance(result, dict) or result.get("error"):
        return out
    if name == "get_law_section":
        out.append({"label": f"Section {result.get('section')}, {result.get('book')}", "url": None})
    elif name == "search_law":
        for r in (result.get("results") or [])[:2]:
            out.append({"label": f"{r.get('book')} — {r.get('near')}", "url": None})
    elif name == "calculate_income_tax":
        yr = (args or {}).get("tax_year") or agent_tools.DEFAULT_YEAR
        out.append({"label": f"TaxBuddy {result.get('income_type', '')} slab table {yr}".replace("  ", " "),
                    "url": result.get("calculator_link")})
    elif name in ("calculate_wht", "find_wht_rates"):
        yr = (args or {}).get("tax_year") or agent_tools.DEFAULT_YEAR
        out.append({"label": f"FBR withholding tax rate card {yr}", "url": result.get("calculator_link")})
    elif name == "check_atl":
        out.append({"label": result.get("source"), "url": result.get("check_page")})
    elif name == "find_sro":
        for r in (result.get("results") or [])[:2]:
            out.append({"label": f"{r.get('number')} — {r.get('subject', '')[:60]}", "url": r.get("url")})
    elif name == "find_blog":
        for r in (result.get("results") or [])[:1]:
            out.append({"label": r.get("title"), "url": r.get("url")})
    return [s for s in out if s.get("label")]

SMART_CALC_PROMPT = SYSTEM_PROMPT + """

THIS REQUEST COMES FROM THE AI SMART TAX CALCULATOR PAGE. The user describes their income. Work out each income type with the tools (salary with salary slabs; business/rent with their slabs), then answer in markdown:
1. **Bottom line**: estimated annual and monthly tax.
2. **Breakdown**: slab, fixed tax + rate on the excess, surcharge if any.
3. One or two notes (e.g. filer vs non-filer effect, what is not included).
End with: "This is an estimate — use the free calculators for detail, and consult a tax professional for filing.\""""

# ── Config ──
def _client():
    import anthropic
    key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in settings/env.")
    return anthropic.Anthropic(api_key=key)

AI_MODEL = getattr(settings, "AI_MODEL", "") or "claude-haiku-5-5"
MAX_AGENT_STEPS = 6            # tool rounds per question (cost guard)
MAX_TOOL_RESULT_CHARS = 7000
DAILY_LIMIT = int(getattr(settings, "AI_DAILY_LIMIT", 400))   # whole-site questions per day
MAX_INPUT_CHARS = 1500          # cap user input length
MAX_HISTORY_TURNS = 8           # cap conversation memory sent to API
RATE_LIMIT_MAX = 25             # max AI requests
RATE_LIMIT_WINDOW = 3600        # per this many seconds (1 hour), per session


# ── Simple per-session rate limit (protects your API cost) ──
def _rate_limited(request):
    now = time.time()
    hits = request.session.get("ai_hits", [])
    hits = [t for t in hits if now - t < RATE_LIMIT_WINDOW]
    if len(hits) >= RATE_LIMIT_MAX:
        return True
    hits.append(now)
    request.session["ai_hits"] = hits
    return False


def _daily_limit_hit():
    """Site-wide cap so a traffic spike cannot burn the API budget."""
    from django.core.cache import cache
    key = "ai_calls_" + time.strftime("%Y%m%d")
    n = cache.get(key, 0)
    if n >= DAILY_LIMIT:
        return True
    cache.set(key, n + 1, 60 * 60 * 26)
    return False


def _run_agent(system_prompt, messages, max_tokens=900):
    """Claude tool-use loop. Returns (reply_text, tools_used)."""
    client = _client()
    tools = [dict(t) for t in agent_tools.TOOLS]
    tools[-1]["cache_control"] = {"type": "ephemeral"}          # cache tools + system
    system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    msgs = list(messages)
    used = []
    for _ in range(MAX_AGENT_STEPS):
        resp = client.messages.create(model=AI_MODEL, max_tokens=max_tokens,
                                      system=system, tools=tools, messages=msgs)
        if resp.stop_reason != "tool_use":
            return "".join(getattr(b, "text", "") for b in resp.content).strip(), used
        msgs.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            used.append(b.name)
            out = json.dumps(agent_tools.run_tool(b.name, b.input), default=str, ensure_ascii=False)
            results.append({"type": "tool_result", "tool_use_id": b.id,
                            "content": out[:MAX_TOOL_RESULT_CHARS]})
        msgs.append({"role": "user", "content": results})
    # out of steps: ask for a final answer without tools
    msgs.append({"role": "user", "content": "Give your final answer now from what the tools returned."})
    resp = client.messages.create(model=AI_MODEL, max_tokens=max_tokens, system=system,
                                  tools=tools, tool_choice={"type": "none"}, messages=msgs)
    return "".join(getattr(b, "text", "") for b in resp.content).strip(), used


def _sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _stream_agent(system_prompt, messages, max_tokens=1200):
    """Same tool loop as _run_agent, but yields SSE events while it works:
    status (tool running), delta (answer text), sources, done / error."""
    try:
        client = _client()
    except Exception:
        logger.exception("AI client setup failed")
        yield _sse({"t": "error", "text": "The AI assistant is unavailable right now. Please try again shortly."})
        return
    tools = [dict(t) for t in agent_tools.TOOLS]
    tools[-1]["cache_control"] = {"type": "ephemeral"}
    system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    msgs = list(messages)
    sources, seen = [], set()
    try:
        for step in range(MAX_AGENT_STEPS + 1):
            last = step == MAX_AGENT_STEPS
            kwargs = dict(model=AI_MODEL, max_tokens=max_tokens, system=system, tools=tools, messages=msgs)
            if last:   # out of tool rounds: force a final answer
                msgs[-1] = {"role": "user", "content": list(msgs[-1]["content"]) + [
                    {"type": "text", "text": "Give your final answer now from what the tools returned."}]}
                kwargs["tool_choice"] = {"type": "none"}
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    if text:
                        yield _sse({"t": "delta", "text": text})
                final = stream.get_final_message()
            if final.stop_reason != "tool_use":
                break
            msgs.append({"role": "assistant", "content": final.content})
            results = []
            for b in final.content:
                if b.type != "tool_use":
                    continue
                yield _sse({"t": "status", "text": _tool_status(b.name, b.input)})
                res = agent_tools.run_tool(b.name, b.input)
                for s in _tool_sources(b.name, b.input, res):
                    k = (s["label"], s.get("url"))
                    if k not in seen:
                        seen.add(k)
                        sources.append(s)
                out = json.dumps(res, default=str, ensure_ascii=False)
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": out[:MAX_TOOL_RESULT_CHARS]})
            msgs.append({"role": "user", "content": results})
            yield _sse({"t": "status", "text": "Writing the answer…"})
        if sources:
            yield _sse({"t": "sources", "items": sources[:6]})
        yield _sse({"t": "done"})
    except GeneratorExit:      # user pressed Stop / closed the tab
        return
    except Exception:
        logger.exception("AI stream failed")
        yield _sse({"t": "error", "text": "The AI assistant is unavailable right now. Please try again shortly."})


def _history_messages(data):
    """Build the Claude message list from the posted history + new message."""
    user_msg = (data.get("message") or "").strip()[:MAX_INPUT_CHARS]
    msgs = []
    for turn in (data.get("history") or [])[-(MAX_HISTORY_TURNS * 2):]:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        content = (turn.get("content") or "")[:MAX_INPUT_CHARS * 2]
        if role in ("user", "assistant") and content:
            if msgs and msgs[-1]["role"] == role:      # API needs alternating roles
                msgs[-1]["content"] += "\n\n" + content
            else:
                msgs.append({"role": role, "content": content})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if msgs and msgs[-1]["role"] == "user":
        msgs.pop()
    return user_msg, msgs + ([{"role": "user", "content": user_msg}] if user_msg else [])


# ════════════════ PAGES ════════════════
def ai_tax_assistant(request):
    """Full-page AI chat (serves the existing /ai-chat/ route)."""
    return render(request, "partials/ai_tax_assistant.html", {
        "meta_title": "AI Pakistan Tax Assistant | Ask Tax Questions Free | TaxBuddy Umair",
        "meta_description": "Free AI tax assistant for Pakistan. Ask about income tax, sales tax, "
                            "filer status, property tax and FBR filing — instant answers for 2026-27.",
    })


def ai_smart_calculator(request):
    """AI Smart Tax Calculator page."""
    return render(request, "partials/ai_smart_calculator.html", {
        "meta_title": "AI Smart Tax Calculator Pakistan 2026-27 | TaxBuddy Umair",
        "meta_description": "Describe your income in plain language and let AI estimate your Pakistan "
                            "income tax for 2026-27 with a clear breakdown. Free and instant.",
    })


# ════════════════ APIs (POST, JSON) ════════════════
@require_POST
@csrf_protect
def ai_chat_api(request):
    if _rate_limited(request):
        return JsonResponse({"status": "error",
                             "message": "You've reached the hourly limit. Please try again later."}, status=429)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)

    user_msg = (data.get("message") or "").strip()[:MAX_INPUT_CHARS]
    if not user_msg:
        return JsonResponse({"status": "error", "message": "Please type a question."}, status=400)

    # history: list of {role, content}; keep last few turns
    history = data.get("history") or []
    msgs = []
    for turn in history[-(MAX_HISTORY_TURNS * 2):]:
        role = turn.get("role")
        content = (turn.get("content") or "")[:MAX_INPUT_CHARS]
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": user_msg})

    if _daily_limit_hit():
        return JsonResponse({"status": "error",
                             "message": "The AI assistant is busy today. Please try again tomorrow."}, status=429)
    try:
        answer, used = _run_agent(SYSTEM_PROMPT, msgs, max_tokens=900)
    except Exception:
        logger.exception("AI chat failed")
        return JsonResponse({"status": "error",
                             "message": "The AI assistant is unavailable right now. Please try again shortly."},
                            status=503)
    return JsonResponse({"status": "ok", "reply": answer, "verified_with": sorted(set(used))})


@require_POST
@csrf_protect
def ai_chat_stream(request):
    """Streaming chat for the full-page TaxBuddy AI (Server-Sent Events over POST)."""
    def fail(msg, code):
        return JsonResponse({"status": "error", "message": msg}, status=code)
    if _rate_limited(request):
        return fail("You've reached the hourly limit. Please try again later.", 429)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return fail("Invalid request.", 400)
    user_msg, msgs = _history_messages(data)
    if not user_msg:
        return fail("Please type a question.", 400)
    if _daily_limit_hit():
        return fail("The AI assistant is busy today. Please try again tomorrow.", 429)
    resp = StreamingHttpResponse(_stream_agent(CHAT_PAGE_PROMPT, msgs), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"      # tell nginx not to buffer the stream
    return resp


@require_POST
@csrf_protect
def ai_smart_calc_api(request):
    if _rate_limited(request):
        return JsonResponse({"status": "error",
                             "message": "You've reached the hourly limit. Please try again later."}, status=429)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)

    situation = (data.get("situation") or "").strip()[:MAX_INPUT_CHARS]
    if not situation:
        return JsonResponse({"status": "error", "message": "Please describe your income situation."}, status=400)

    if _daily_limit_hit():
        return JsonResponse({"status": "error",
                             "message": "The AI calculator is busy today. Please try again tomorrow."}, status=429)
    try:
        result, used = _run_agent(SMART_CALC_PROMPT,
                                  [{"role": "user", "content": situation}],
                                  max_tokens=1100)
    except Exception:
        logger.exception("AI smart calc failed")
        return JsonResponse({"status": "error",
                             "message": "The AI calculator is unavailable right now. Please try again shortly."},
                            status=503)
    return JsonResponse({"status": "ok", "result": result, "verified_with": sorted(set(used))})