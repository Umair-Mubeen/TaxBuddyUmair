"""
TaxBuddyApp/ai_chats.py — Phase 1 of the TaxBuddy Umair AI upgrade.

Server-side chats with no login: each browser gets a random id in a long-lived,
HttpOnly cookie (`tbai_uid`); only its salted hash is stored as the owner.

  • chat history for Claude comes from the database, never from the browser
  • sidebar list + search, rename, delete, read-only share links
  • 👍 / 👎 feedback on answers (reviewed in admin, can become VerifiedAnswer)
  • one-time import of chats that older versions kept in localStorage
    (imported assistant text is shown, but never sent to Claude)
  • CNIC / NTN numbers are masked before anything is stored

URLs (add to TaxBuddyApp/urls.py):
    path('api/ai/chats/', ai_chats.chats_list, name='ai_chats_list'),
    path('api/ai/chats/import/', ai_chats.chats_import, name='ai_chats_import'),
    path('api/ai/chats/<str:cid>/', ai_chats.chat_detail, name='ai_chat_detail'),
    path('api/ai/chats/<str:cid>/rename/', ai_chats.chat_rename, name='ai_chat_rename'),
    path('api/ai/chats/<str:cid>/delete/', ai_chats.chat_delete, name='ai_chat_delete'),
    path('api/ai/chats/<str:cid>/share/', ai_chats.chat_share, name='ai_chat_share'),
    path('api/ai/messages/<int:mid>/feedback/', ai_chats.message_feedback, name='ai_message_feedback'),
    path('ai-chat/s/<str:token>/', ai_chats.shared_chat, name='ai_shared_chat'),
"""
import json
import re
import secrets

from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from . import ai_guard
from .models import AIConversation, AIMessage

COOKIE = "tbai_uid"
COOKIE_AGE = 60 * 60 * 24 * 365 * 2          # 2 years
HISTORY_TURNS = 16                            # messages sent to Claude (8 exchanges)
HISTORY_CHARS = 4000                          # per message sent to Claude
MAX_CHATS_LISTED = 60
_CID = re.compile(r"^[a-z0-9]{6,40}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,32}$")


# ── owner (browser) identity ─────────────────────────────────────────────────
def owner_id(request):
    """Hashed browser id. Creates one if missing; `attach_cookie` then sets it."""
    raw = request.COOKIES.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", raw or ""):
        raw = getattr(request, "_tbai_new_uid", None) or secrets.token_urlsafe(24)
        request._tbai_new_uid = raw
    return ai_guard._hash("uid:" + raw)


def attach_cookie(request, response):
    raw = getattr(request, "_tbai_new_uid", None)
    if raw:
        response.set_cookie(COOKIE, raw, max_age=COOKIE_AGE, httponly=True,
                            samesite="Lax", secure=request.is_secure())
    return response


# ── privacy ──────────────────────────────────────────────────────────────────
_CNIC = re.compile(r"\b\d{5}-?\d{7}-?\d\b")
_NTN = re.compile(r"\b\d{7}-?\d\b")

def mask_pii(text):
    """Mask CNIC (13 digits) and NTN (7+1 digits) before storing."""
    text = _CNIC.sub(lambda m: "*****-*******-" + m.group()[-1], text or "")
    return _NTN.sub(lambda m: "*******-" + m.group()[-1], text)


def clean_cid(value):
    value = str(value or "").strip().lower()
    return value if _CID.match(value) else ""


def _title(text):
    t = re.sub(r"\s+", " ", mask_pii(text or "")).strip()
    return (t[:60] + "…") if len(t) > 60 else (t or "New chat")


def _json(data, status=200, request=None):
    resp = JsonResponse(data, status=status)
    return attach_cookie(request, resp) if request is not None else resp


def _get_conv(request, cid):
    cid = clean_cid(cid)
    if not cid:
        raise Http404
    try:
        return AIConversation.objects.get(owner=owner_id(request), cid=cid, is_deleted=False)
    except AIConversation.DoesNotExist:
        raise Http404


def _msg_dict(m):
    try:
        sources = json.loads(m.sources) if m.sources else []
    except ValueError:
        sources = []
    return {"id": m.id, "role": m.role, "content": m.content, "sources": sources,
            "status": m.status, "feedback": m.feedback}


# ── used by the chat stream (ai_views.ai_chat_stream) ────────────────────────
def start_turn(request, data, max_input_chars):
    """Save the user's message and build the message list for Claude.

    Returns (conversation, user_msg, messages) or (None, "", []) when the
    message is empty. History is read from the database: only answers that
    finished normally and were produced here (not imported) are sent to Claude.
    """
    user_msg = (data.get("message") or "").strip()[:max_input_chars]
    if not user_msg:
        return None, "", []
    owner = owner_id(request)
    cid = clean_cid(data.get("cid")) or secrets.token_hex(8)
    with transaction.atomic():
        conv, created = AIConversation.objects.get_or_create(
            owner=owner, cid=cid, defaults={"title": _title(user_msg)})
        if conv.is_deleted:                      # a deleted chat id came back: start fresh
            conv.messages.all().delete()
            conv.is_deleted, conv.title, conv.share_token = False, _title(user_msg), None
            conv.save()
        last = list(conv.messages.order_by("-id")[:2])
        if data.get("regen") and last and last[0].role == "assistant":
            # Regenerate: drop the last answer, keep the question it answered
            last[0].delete()
            last = last[1:]
        if not (data.get("regen") and last and last[0].role == "user"
                and last[0].content == mask_pii(user_msg)):
            AIMessage.objects.create(conversation=conv, role="user", content=mask_pii(user_msg))
        conv.save(update_fields=["updated"])

    rows = list(conv.messages.order_by("-id")[:HISTORY_TURNS + 1])[::-1]
    msgs = []
    for m in rows[:-1]:                          # earlier turns
        if m.role == "assistant" and (m.imported or m.status != "ok"):
            continue
        text = m.content[:HISTORY_CHARS]
        if msgs and msgs[-1]["role"] == m.role:
            msgs[-1]["content"] += "\n\n" + text
        else:
            msgs.append({"role": m.role, "content": text})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    # the current question goes in unmasked (the ATL check may need the NTN)
    if msgs and msgs[-1]["role"] == "user":
        msgs[-1]["content"] += "\n\n" + user_msg
    else:
        msgs.append({"role": "user", "content": user_msg})
    return conv, user_msg, msgs


def finish_turn(conv, answer, sources, status):
    """Save the assistant answer. Returns its id (for 👍 / 👎) or None."""
    if conv is None or not (answer or "").strip():
        return None
    m = AIMessage.objects.create(conversation=conv, role="assistant",
                                 content=mask_pii(answer), status=status,
                                 sources=json.dumps(sources or [], ensure_ascii=False))
    AIConversation.objects.filter(pk=conv.pk).update(updated=timezone.now())
    return m.id


# ── sidebar APIs ─────────────────────────────────────────────────────────────
@require_GET
def chats_list(request):
    owner = owner_id(request)
    qs = AIConversation.objects.filter(owner=owner, is_deleted=False)
    q = (request.GET.get("q") or "").strip()[:80]
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(messages__content__icontains=q)).distinct()
    chats = [{"id": c.cid, "title": c.title, "updated": int(c.updated.timestamp() * 1000),
              "shared": bool(c.share_token)} for c in qs[:MAX_CHATS_LISTED]]
    return _json({"chats": chats}, request=request)


@require_GET
def chat_detail(request, cid):
    conv = _get_conv(request, cid)
    msgs = [_msg_dict(m) for m in conv.messages.all()]
    return _json({"id": conv.cid, "title": conv.title, "messages": msgs,
                  "share_url": _share_url(request, conv)}, request=request)


def _body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except ValueError:
        return {}


@require_POST
@csrf_protect
def chat_rename(request, cid):
    conv = _get_conv(request, cid)
    title = re.sub(r"\s+", " ", str(_body(request).get("title") or "")).strip()[:120]
    if not title:
        return _json({"status": "error", "message": "Title cannot be empty."}, 400, request)
    conv.title = mask_pii(title)
    conv.save(update_fields=["title", "updated"])
    return _json({"status": "ok", "title": conv.title}, request=request)


@require_POST
@csrf_protect
def chat_delete(request, cid):
    conv = _get_conv(request, cid)
    conv.is_deleted, conv.share_token = True, None
    conv.save(update_fields=["is_deleted", "share_token", "updated"])
    return _json({"status": "ok"}, request=request)


def _share_url(request, conv):
    if not conv.share_token:
        return None
    return request.build_absolute_uri(f"/ai-chat/s/{conv.share_token}/")


@require_POST
@csrf_protect
def chat_share(request, cid):
    """{"on": true} creates a read-only link, {"on": false} switches it off."""
    conv = _get_conv(request, cid)
    if _body(request).get("on", True):
        if not conv.share_token:
            conv.share_token = secrets.token_urlsafe(16)
            conv.save(update_fields=["share_token"])
    elif conv.share_token:
        conv.share_token = None
        conv.save(update_fields=["share_token"])
    return _json({"status": "ok", "share_url": _share_url(request, conv)}, request=request)


@require_POST
@csrf_protect
def message_feedback(request, mid):
    """{"value": 1 | -1 | 0, "note": "..."} on one assistant answer of this browser."""
    data = _body(request)
    try:
        value = int(data.get("value", 0))
    except (TypeError, ValueError):
        value = 0
    if value not in (-1, 0, 1):
        value = 0
    try:
        m = AIMessage.objects.select_related("conversation").get(
            pk=mid, role="assistant", conversation__owner=owner_id(request))
    except AIMessage.DoesNotExist:
        raise Http404
    m.feedback = value
    m.feedback_note = mask_pii(str(data.get("note") or ""))[:500]
    m.feedback_at = timezone.now() if value else None
    m.save(update_fields=["feedback", "feedback_note", "feedback_at"])
    return _json({"status": "ok"}, request=request)


@require_POST
@csrf_protect
def chats_import(request):
    """One-time copy of chats from the browser's old localStorage.
    Imported answers are marked `imported` and never sent to Claude."""
    owner = owner_id(request)
    chats = _body(request).get("chats") or []
    done = 0
    for c in chats[:40]:
        if not isinstance(c, dict):
            continue
        cid = clean_cid(c.get("id"))
        msgs = [m for m in (c.get("messages") or [])[:60]
                if isinstance(m, dict) and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str) and m["content"].strip() and not m.get("error")]
        if not cid or not msgs or AIConversation.objects.filter(owner=owner, cid=cid).exists():
            continue
        with transaction.atomic():
            conv = AIConversation.objects.create(owner=owner, cid=cid,
                                                 title=_title(c.get("title") or msgs[0]["content"]))
            AIMessage.objects.bulk_create([
                AIMessage(conversation=conv, role=m["role"], content=mask_pii(m["content"][:8000]),
                          imported=True,
                          sources=json.dumps([s for s in (m.get("sources") or [])
                                              if isinstance(s, dict)][:6], ensure_ascii=False)[:4000])
                for m in msgs])
        done += 1
    return _json({"status": "ok", "imported": done}, request=request)


# ── read-only shared chat page ───────────────────────────────────────────────
def shared_chat(request, token):
    if not _TOKEN.match(token or ""):
        raise Http404
    try:
        conv = AIConversation.objects.get(share_token=token, is_deleted=False)
    except AIConversation.DoesNotExist:
        raise Http404
    msgs = [_msg_dict(m) for m in conv.messages.all() if m.status == "ok" or m.role == "user"]
    resp = render(request, "partials/ai_shared_chat.html", {
        "conv": conv, "messages_json": msgs,
        "meta_title": f"{conv.title} — shared TaxBuddy Umair AI chat",
    })
    resp["X-Robots-Tag"] = "noindex, nofollow"     # shared chats stay out of Google
    return resp
