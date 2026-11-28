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
from . import ai_guard
from . import ai_chats
from . import cite_check

# ── Agent instructions ──
SYSTEM_PROMPT = """You are "TaxBuddy Umair AI", the Pakistan tax assistant on taxbuddyumair.com, a free tax-education platform by Umair Mubeen (a Pakistani tax educator).

YOU HAVE TOOLS. USE THEM — never answer from memory:
- FIRST call find_verified_answer with the user's question. These answers were checked by a tax expert; when one clearly matches, follow it (and still use the calculators for amounts).
- Every amount or rate comes from a calculator tool — never do tax maths yourself:
  - salary / business / AOP / rental slab tax (with VPS credit, surcharge) -> calculate_income_tax
  - super tax s.4C -> calculate_super_tax
  - quarterly advance tax s.147 -> calculate_advance_tax_147
  - capital gain on property -> calculate_cgt_property; on shares -> calculate_cgt_securities
  - property advance tax 236C (sale) / 236K (purchase) -> calculate_property_advance_tax
  - car registration, transfer, token tax (231B / 234) -> calculate_vehicle_tax
  - Karachi FBR property value -> calculate_karachi_fmv
  - any other withholding (bank profit 151, rent 155, contracts 153, dividends, cash withdrawal, export 154A, etc.) -> find_wht_rates then calculate_wht
- Quote the rate and amount the tool returns. Calculator results include "law" (sections) and "tax_nature" (final / minimum / adjustable / separate block): always tell the user the tax nature and the sections from "law".
- "Am I / is this NTN a filer?" -> check_atl.
- Latest SROs, circulars, notifications -> find_sro.
- Legal questions (what the law says, conditions, definitions, penalties, procedures) -> search_law, then get_law_section for the exact section (use focus for long sections such as ito 182 or ito 2). Exemptions, rates and clauses in a Schedule (e.g. Second Schedule clause 139 medical, Division VIII CGT rates) -> get_law_schedule. Cite the book and section, e.g. "Section 147A, Income Tax Ordinance 2001".
- After answering, call find_blog once with 3-5 English key words of the topic (e.g. "vehicle registration advance tax"). Link an article only if its title is clearly about the same topic; otherwise link none.
- When the user is a non-filer, also call the same calculator with on_atl=true and show the filer amount next to it, so they see what filing saves. Do not tell them to contact anyone for the filer figure.
- If a tool returns nothing or an error, say you could not verify it. Do NOT guess numbers, sections or dates.
- Late filing, penalty for not filing, ATL surcharge or Form ATL-U -> ALWAYS read all three: get_law_section ito 182 (Table entry 1), ito 182A and it_rules 81B, and mention the s.182A ATL surcharge (Form ATL-U) as well as the s.182 penalty. The s.182 minimum (Rs 10,000 / Rs 50,000) is a minimum total penalty, not a per-day amount. For the user's own penalty amount, link /late-filing-penalty-calculator/. Who must file a return -> ito 114 and 115, and link /do-i-need-to-file-tax-return/.

HOW TO ANSWER:
- LANGUAGE: reply in the language of the user's LATEST message. Roman Urdu question (e.g. "kitna tax banega", "main filer hoon") -> whole answer in Roman Urdu, including headings and notes; English question -> English; Urdu script -> Urdu script. Section names, numbers and law terms may stay in English.
- Start with the bottom line (the amount, rate or yes/no), then a short breakdown. Keep it short.
- Show the working for calculations using the tool's "working" lines. Do not add explanations of your own about how a credit or rate works beyond what the tool or law text says.
- Give site links as relative paths, e.g. /articles/slug/ or /SalaryCalculator/.
- If key information is missing (monthly vs yearly, filer or not), ask one short question or state the assumption.
- Speak as a tax expert, never about your own workings: do not mention tools, the database, "verified answers", internal notes, matching scores, or earlier drafts, and never write things like "database ke mutabiq", "tool ne bataya" or "not verified". Just state the law and the figures.
- Cite only sections you actually received in this conversation: text read with get_law_section / search_law, or listed in a calculator result's "law". Quote amounts and rates exactly as given. Never cite a section from memory.

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
        "calculate_super_tax": "Calculating super tax (4C)…",
        "calculate_advance_tax_147": "Calculating advance tax (147)…",
        "calculate_cgt_property": "Calculating capital gains tax…",
        "calculate_cgt_securities": "Calculating capital gains tax…",
        "calculate_property_advance_tax": "Calculating property advance tax…",
        "calculate_vehicle_tax": "Calculating vehicle tax…",
        "calculate_karachi_fmv": "Looking up the FBR valuation table…",
        "find_wht_rates": "Looking up the withholding tax rate card…",
        "calculate_wht": "Calculating withholding tax…",
        "check_atl": "Checking the Active Taxpayers List…",
        "find_sro": "Searching SROs and notifications…",
        "find_blog": "Finding a related TaxBuddy guide…",
        "find_verified_answer": "Checking TaxBuddy verified answers…",
        "search_law": f"Searching {book}…",
        "get_law_section": f"Reading Section {args.get('number', '')} — {book}…",
        "get_law_schedule": f"Reading the {args.get('schedule', '')} Schedule — {book}…",
    }.get(name, "Working…")


def _tool_sources(name, args, result):
    """Turn one tool call into source chips for the UI: [{label, url}]."""
    out = []
    if not isinstance(result, dict) or result.get("error"):
        return out
    if name == "get_law_section":
        out.append({"label": f"{result.get('unit', 'Section')} {result.get('section')}, {result.get('book')}", "url": None})
    elif name == "get_law_schedule":
        out.append({"label": f"{result.get('schedule')}, {result.get('book')}", "url": None})
    # search_law passages are not shown as sources: only sections actually read count
    elif name in agent_tools.tax_engine.FUNCTIONS:
        law = result.get("law") or []
        if law:
            out.append({"label": law[0], "url": result.get("calculator")})
    elif name in ("calculate_wht", "find_wht_rates"):
        yr = (args or {}).get("tax_year") or agent_tools.DEFAULT_YEAR
        out.append({"label": f"FBR withholding tax rate card {yr}", "url": result.get("calculator_link")})
    elif name == "check_atl":
        out.append({"label": result.get("source"), "url": result.get("check_page")})
    elif name == "find_sro":
        for r in (result.get("results") or [])[:2]:
            out.append({"label": f"{r.get('number')} — {r.get('subject', '')[:60]}", "url": r.get("url")})
    elif name == "find_verified_answer":
        for r in (result.get("results") or [])[:1]:
            if r.get("match_score", 0) >= 0.35:
                out.append({"label": "TaxBuddy verified answer" + (f" — {r['section']}" if r.get("section") else ""),
                            "url": None})
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
MAX_INPUT_CHARS = 1500          # cap user input length
MAX_HISTORY_TURNS = 8           # cap conversation memory sent to API
# Rate limits, daily caps, usage logging and server-side history: see ai_guard.py


def _run_agent(system_prompt, messages, max_tokens=900, usage=None):
    """Claude tool-use loop. Returns (reply_text, tools_used). Adds token use to `usage`."""
    client = _client()
    tools = [dict(t) for t in agent_tools.TOOLS]
    tools[-1]["cache_control"] = {"type": "ephemeral"}          # cache tools + system
    system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    msgs = list(messages)
    used = []
    tracker = cite_check.Tracker()

    def finish(text):
        clean, bad = cite_check.check(text, tracker)
        if bad and usage is not None:
            usage.tools.append("cite_bad:" + "/".join(n for _b, n, _e in bad))
        return clean, used

    for _ in range(MAX_AGENT_STEPS):
        resp = client.messages.create(model=AI_MODEL, max_tokens=max_tokens,
                                      system=system, tools=tools, messages=msgs)
        if usage is not None:
            usage.add(resp.usage)
        if resp.stop_reason != "tool_use":
            return finish("".join(getattr(b, "text", "") for b in resp.content).strip())
        msgs.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            used.append(b.name)
            if usage is not None:
                usage.tools.append(b.name)
            res = agent_tools.run_tool(b.name, b.input)
            tracker.add_tool(b.name, b.input, res)
            out = json.dumps(res, default=str, ensure_ascii=False)
            results.append({"type": "tool_result", "tool_use_id": b.id,
                            "content": out[:MAX_TOOL_RESULT_CHARS]})
        msgs.append({"role": "user", "content": results})
    # out of steps: ask for a final answer without tools
    msgs.append({"role": "user", "content": "Give your final answer now from what the tools returned."})
    resp = client.messages.create(model=AI_MODEL, max_tokens=max_tokens, system=system,
                                  tools=tools, tool_choice={"type": "none"}, messages=msgs)
    if usage is not None:
        usage.add(resp.usage)
    return finish("".join(getattr(b, "text", "") for b in resp.content).strip())


def _sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _stream_agent(system_prompt, messages, max_tokens=1800, request=None, conv=None, user_msg=""):
    """Same tool loop as _run_agent, but yields SSE events while it works:
    status (tool running), delta (answer text), sources, done / error.
    When it finishes it saves the answer to the conversation and logs usage."""
    usage = ai_guard.Usage(AI_MODEL)
    answer = []
    status = "error"
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
    earlier = []
    if conv is not None:
        try:
            earlier = list(conv.messages.filter(role="assistant", status="ok", imported=False)
                           .order_by("-id").values_list("content", flat=True)[:8])
        except Exception:
            earlier = []
    tracker = cite_check.Tracker(earlier)
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
                        answer.append(text)
                        yield _sse({"t": "delta", "text": text})
                final = stream.get_final_message()
            usage.add(final.usage)
            if final.stop_reason != "tool_use":
                break
            msgs.append({"role": "assistant", "content": final.content})
            results = []
            for b in final.content:
                if b.type != "tool_use":
                    continue
                yield _sse({"t": "status", "text": _tool_status(b.name, b.input)})
                usage.tools.append(b.name)
                res = agent_tools.run_tool(b.name, b.input)
                tracker.add_tool(b.name, b.input, res)
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
        text = "".join(answer)
        clean, bad = cite_check.check(text, tracker)
        if bad:
            usage.tools.append("cite_bad:" + "/".join(n for _b, n, _e in bad))
            yield _sse({"t": "fix", "text": clean})
        if sources:
            yield _sse({"t": "sources", "items": sources[:6]})
        status = "ok"
        mid = ai_chats.finish_turn(conv, clean, sources[:6], "ok")
        yield _sse({"t": "done", "mid": mid})
    except GeneratorExit:      # user pressed Stop / closed the tab
        status = "stopped"
        ai_chats.finish_turn(conv, "".join(answer), [], "stopped")
        return
    except Exception:
        logger.exception("AI stream failed")
        yield _sse({"t": "error", "text": "The AI assistant is unavailable right now. Please try again shortly."})
    finally:
        if request is not None and usage.calls:
            ai_guard.record(request, "chat_stream", usage, status, user_msg)


# ════════════════ PAGES ════════════════
def ai_tax_assistant(request):
    """Full-page AI chat (serves the existing /ai-chat/ route)."""
    ai_chats.owner_id(request)          # give this browser its chat id cookie
    resp = render(request, "partials/ai_tax_assistant.html", {
        "meta_title": "AI Pakistan Tax Assistant | Ask Tax Questions Free | TaxBuddy Umair",
        "meta_description": "Free AI tax assistant for Pakistan. Ask about income tax, sales tax, "
                            "filer status, property tax and FBR filing — instant answers for 2026-27.",
    })
    return ai_chats.attach_cookie(request, resp)


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
    blocked = ai_guard.check_limits(request)
    if blocked:
        return JsonResponse({"status": "error", "message": blocked}, status=429)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)

    cid, user_msg, msgs = ai_guard.build_messages(request, data, MAX_INPUT_CHARS)
    if not user_msg:
        return JsonResponse({"status": "error", "message": "Please type a question."}, status=400)
    usage = ai_guard.Usage(AI_MODEL)
    try:
        answer, used = _run_agent(SYSTEM_PROMPT, msgs, max_tokens=900, usage=usage)
    except Exception:
        logger.exception("AI chat failed")
        ai_guard.record(request, "chat_api", usage, "error", user_msg)
        return JsonResponse({"status": "error",
                             "message": "The AI assistant is unavailable right now. Please try again shortly."},
                            status=503)
    ai_guard.save_turns(request, cid, user_msg, answer)
    ai_guard.record(request, "chat_api", usage, "ok", user_msg)
    return JsonResponse({"status": "ok", "reply": answer, "verified_with": sorted(set(used))})


@require_POST
@csrf_protect
def ai_chat_stream(request):
    """Streaming chat for the full-page TaxBuddy Umair AI (Server-Sent Events over POST)."""
    def fail(msg, code):
        return JsonResponse({"status": "error", "message": msg}, status=code)
    blocked = ai_guard.check_limits(request)
    if blocked:
        return fail(blocked, 429)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return fail("Invalid request.", 400)
    conv, user_msg, msgs = ai_chats.start_turn(request, data, MAX_INPUT_CHARS)
    if not user_msg:
        return fail("Please type a question.", 400)
    resp = StreamingHttpResponse(
        _stream_agent(CHAT_PAGE_PROMPT, msgs, request=request, conv=conv, user_msg=user_msg),
        content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"      # tell nginx not to buffer the stream
    return ai_chats.attach_cookie(request, resp)


@require_POST
@csrf_protect
def ai_smart_calc_api(request):
    blocked = ai_guard.check_limits(request)
    if blocked:
        return JsonResponse({"status": "error", "message": blocked}, status=429)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)

    situation = (data.get("situation") or "").strip()[:MAX_INPUT_CHARS]
    if not situation:
        return JsonResponse({"status": "error", "message": "Please describe your income situation."}, status=400)

    usage = ai_guard.Usage(AI_MODEL)
    try:
        result, used = _run_agent(SMART_CALC_PROMPT,
                                  [{"role": "user", "content": situation}],
                                  max_tokens=1100, usage=usage)
    except Exception:
        logger.exception("AI smart calc failed")
        ai_guard.record(request, "smart_calc", usage, "error", situation)
        return JsonResponse({"status": "error",
                             "message": "The AI calculator is unavailable right now. Please try again shortly."},
                            status=503)
    ai_guard.record(request, "smart_calc", usage, "ok", situation)
    return JsonResponse({"status": "ok", "result": result, "verified_with": sorted(set(used))})