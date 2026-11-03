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
#    AI_MODEL          = os.environ.get("AI_MODEL", "claude-3-5-haiku-latest")
#    # ^ set AI_MODEL to a model your API key can use. See docs.claude.com for current model IDs.
#    #   Haiku = cheapest/fast (good here). Switch to a Sonnet model for deeper reasoning.
# ════════════════════════════════════════════════════════════════
import time
import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect


# ── Verified FBR Tax Year 2026-27 facts the assistant is grounded on ──
TAX_FACTS_2026_27 = """
PAKISTAN TAX — VERIFIED FACTS FOR TAX YEAR 2026-27 (Finance Act 2026):

SALARY INCOME TAX SLABS (annual taxable salary):
- Up to Rs 600,000: 0%
- 600,001–1,200,000: 1% of amount over 600,000
- 1,200,001–2,200,000: Rs 6,000 + 11% of amount over 1,200,000
- 2,200,001–3,200,000: Rs 116,000 + 20% of amount over 2,200,000
- 3,200,001–4,100,000: Rs 316,000 + 25% of amount over 3,200,000
- 4,100,001–5,600,000: Rs 541,000 + 29% of amount over 4,100,000
- 5,600,001–7,000,000: Rs 976,000 + 32% of amount over 5,600,000
- Above 7,000,000: Rs 1,424,000 + 35% of amount over 7,000,000
(Surcharge 9% on tax if taxable income exceeds Rs 10 million.)

PROPERTY:
- 236C (sale/transfer): filer 2.75%, non-filer 11.5% of gross consideration.
- 236K (purchase): filer 1.25%; non-filer 10.5% (FMV up to 50M), 14.5% (50–100M), 18.5% (above 100M).

OTHER WITHHOLDING (filer / non-filer):
- 151 profit on bank deposits: 20% / 40%.
- 150 dividend (general): 15% / 30%.
- 236Y foreign card payments: 0.5% / 1%.
- 231AB cash withdrawal over Rs 50,000/day (non-filer only): 0.8%.
- 149 salary: per slab (no extra non-filer surcharge on salary).

SALES TAX: standard GST 18%; further tax on supplies to unregistered persons 4%.

FILER vs NON-FILER: a filer is on FBR's Active Taxpayer List (ATL) by filing the annual return.
Non-filers pay much higher withholding on property, bank profit, dividends and card payments.
Return filing deadline for individuals/AOPs is 30 September (for the tax year ending 30 June).
""".strip()

SYSTEM_PROMPT = f"""You are "TaxBuddy AI", the Pakistan tax assistant on taxbuddyumair.com, a free tax-education platform by Umair Mubeen (a Pakistani tax educator).

YOUR ROLE:
- Answer questions about Pakistan income tax, sales tax, property tax, withholding tax, filer/non-filer status and FBR filing, in simple language.
- Be accurate, concise and practical. Use the verified rates below. Prefer short answers with a clear bottom line, then detail if needed.
- When a user wants an exact number, do the math using the slabs below AND point them to the relevant free calculator on the site (Salary Tax Calculator, Property Calculator, WHT Calculator, Capital Gain Calculator, PTA Mobile Tax, Zakat Calculator).
- You may answer in English or Roman Urdu depending on how the user writes.

{TAX_FACTS_2026_27}

STRICT RULES:
- This is educational information, NOT professional tax, legal or financial advice. For complex cases, advise consulting a qualified tax practitioner.
- TaxBuddy Umair is an independent educator and is NOT affiliated with, or representing, the FBR.
- If you are unsure or the question is outside Pakistan tax, say so briefly instead of guessing. Never invent sections or rates.
- Do not give rates for years other than 2026-27 unless the user asks and you clearly label the year as approximate/historical.
- Keep answers focused on Pakistan tax. Decline unrelated requests politely.
- Never ask for or store sensitive personal data (CNIC, passwords, card numbers)."""

SMART_CALC_PROMPT = f"""You are the "AI Smart Tax Calculator" on taxbuddyumair.com. The user describes their income situation in plain language (salary, business, rent, etc.) and you compute an ESTIMATE of their Pakistan income tax for Tax Year 2026-27 and explain it simply.

{TAX_FACTS_2026_27}

HOW TO RESPOND (use clean markdown):
1. A one-line **bottom line**: estimated annual tax and monthly tax.
2. A short **breakdown**: which slab applies, base tax + rate on the excess, and the arithmetic.
3. One or two **plain-language notes** (e.g. filer vs non-filer impact, what's not included).
4. End with: "This is an estimate for Tax Year 2026-27 — use the free calculators for a detailed result, and consult a tax professional for filing."

RULES:
- Only compute what the user gives you. If key info is missing (e.g. monthly vs annual), state the assumption you made.
- Salaried individuals use the salary slabs. Be clear this is tax on taxable income before credits/allowances.
- Do NOT fabricate deductions or numbers. Keep it an estimate. Educational only, not advice."""

# ── Config ──
def _client():
    import anthropic
    key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in settings/env.")
    return anthropic.Anthropic(api_key=key)

AI_MODEL = getattr(settings, "AI_MODEL", "claude-3-5-haiku-latest")
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


def _call_claude(system_prompt, messages, max_tokens=900):
    client = _client()
    resp = client.messages.create(
        model=AI_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    )
    # concatenate text blocks
    return "".join(getattr(b, "text", "") for b in resp.content).strip()


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

    try:
        answer = _call_claude(SYSTEM_PROMPT, msgs, max_tokens=900)
    except Exception as e:
        return JsonResponse({"status": "error",
                             "message": "The AI assistant is unavailable right now. Please try again shortly."},
                            status=503)
    return JsonResponse({"status": "ok", "reply": answer})


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

    try:
        result = _call_claude(SMART_CALC_PROMPT,
                              [{"role": "user", "content": situation}],
                              max_tokens=1100)
    except Exception:
        return JsonResponse({"status": "error",
                             "message": "The AI calculator is unavailable right now. Please try again shortly."},
                            status=503)
    return JsonResponse({"status": "ok", "result": result})