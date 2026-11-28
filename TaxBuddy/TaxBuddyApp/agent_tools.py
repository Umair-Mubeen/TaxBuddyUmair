"""
Tools for the TaxBuddy AI agent.

Every number the agent gives comes from one of these functions, which read the
site's own database (slabs, WHT rates, ATL, SROs, blogs) or the statute books
in law_texts/. The agent is told never to compute tax from memory.

TOOLS     - the JSON schemas sent to Claude
run_tool  - runs one tool call and returns a JSON-safe dict
"""
from django.db.models import Q

from . import law_search, tax_engine
from .models import ATLRecord, Blog, Instrument, WHTRate

DEFAULT_YEAR = "2026-2027"

CALCULATOR_LINKS = {
    "salary": "/SalaryCalculator/",
    "wht": "/Withholding-Tax-Card/",
    "153": "/section-153-withholding-tax-calculator/",
    "cgt": "/capital-gains-tax-calculator/",
    "fmv": "/karachi-fmv-calculator/",
    "vehicle": "/motor-vehicle-tax-calculator/",
    "freelancer": "/freelancer-tax-calculator/",
    "advance": "/advance-tax-calculator/",
    "atl": "/atl-check/",
}


# ───────────────────────── withholding (WHTRate) ─────────────────────────
def _wht_row(r):
    return {"uid": r.uid, "section": r.section, "name": r.name, "detail": r.sub,
            "rate_kind": r.rate_kind, "filer": float(r.filer), "non_filer": float(r.non_filer),
            "nature": r.nature, "tax_type": r.tax_type,
            "slab_min": r.slab_min, "slab_max": r.slab_max,
            "base_tax": float(r.base_tax) if r.base_tax is not None else None}


def find_wht_rates(query, tax_year=DEFAULT_YEAR):
    words = [w for w in query.replace(",", " ").split() if len(w) > 1][:6]
    qs = WHTRate.objects.filter(tax_year=tax_year, is_active=True)
    cond = Q()
    for w in words:
        cond |= Q(section__icontains=w) | Q(name__icontains=w) | Q(sub__icontains=w)
    rows = list(qs.filter(cond)[:60]) if words else []

    def score(r):   # rows matching more words first
        hay = f"{r.section} {r.name} {r.sub}".lower()
        return -sum(w.lower() in hay for w in words)
    rows.sort(key=score)
    return {"source": f"TaxBuddy WHT rate card database, tax year {tax_year}",
            "rates_are_percent_unless_rate_kind_is_fixed": True,
            "matches": [_wht_row(r) for r in rows[:12]],
            "calculator_link": CALCULATOR_LINKS["wht"]}


def calculate_wht(uid, amount, status="filer", tax_year=DEFAULT_YEAR):
    status = "non_filer" if str(status).lower().replace("-", "_").replace(" ", "_") in (
        "non_filer", "nonfiler", "non_atl", "not_on_atl") else "filer"
    try:
        r = WHTRate.objects.get(uid=uid, tax_year=tax_year, is_active=True)
    except WHTRate.DoesNotExist:
        return {"error": f"No WHT rate with uid '{uid}'. Call find_wht_rates first."}
    amount = float(amount)
    rate = float(r.non_filer if status == "non_filer" else r.filer)
    if r.rate_kind == "fixed":
        tax = rate
        how = f"Fixed amount Rs {rate:,.0f}"
    elif r.rate_kind == "slab":
        # find the right slab row of the same section
        rows = WHTRate.objects.filter(tax_year=tax_year, is_active=True, section=r.section,
                                      rate_kind="slab").order_by("slab_min")
        row = r
        for s in rows:
            lo = s.slab_min or 0
            hi = s.slab_max if s.slab_max is not None else float("inf")
            if lo <= amount <= hi:
                row = s
                break
        rate = float(row.non_filer if status == "non_filer" else row.filer)
        filer_rate = float(row.filer) or 0
        mult = rate / filer_rate if (status == "non_filer" and filer_rate) else 1
        base = float(row.base_tax or 0) * mult
        start = float(row.slab_min or 0)
        if start % 10 == 1:
            start -= 1
        tax = base + max(amount - start, 0) * rate / 100
        how = f"Rs {base:,.0f} + {rate}% of amount above Rs {start:,.0f} ({row.name})"
        r = row
    else:
        tax = amount * rate / 100
        how = f"{rate}% of Rs {amount:,.0f}"
    return {"source": f"TaxBuddy WHT rate card database, tax year {tax_year}",
            "section": r.section, "transaction": r.name, "status": status,
            "amount": round(amount), "working": how, "tax": round(tax),
            "nature": r.nature, "tax_type": r.tax_type,
            "calculator_link": CALCULATOR_LINKS["wht"]}


# ───────────────────────── ATL ─────────────────────────
def check_atl(ntn_or_cnic):
    q = "".join(ch for ch in str(ntn_or_cnic) if ch.isdigit())
    if len(q) not in (7, 8, 9, 13):
        return {"error": "Give a 7-digit NTN or a 13-digit CNIC (digits only)."}
    rec = ATLRecord.objects.filter(ntn=q).first() or ATLRecord.objects.filter(ntn=q.lstrip("0")).first()
    if not rec and len(q) < 13:
        for pad in (7, 8, 9):
            rec = ATLRecord.objects.filter(ntn=q.zfill(pad)).first()
            if rec:
                break
    last = ATLRecord.objects.order_by("-updated_at").values_list("updated_at", flat=True).first()
    base = {"source": "TaxBuddy copy of FBR Active Taxpayers List",
            "list_last_updated": last.date().isoformat() if last else None,
            "check_page": CALCULATOR_LINKS["atl"]}
    if not rec:
        return {**base, "found": False,
                "message": "Not found in our copy of the ATL. The person may be a non-filer, or the list "
                           "may not be updated yet. Confirm on FBR's official ATL service (SMS ATL "
                           "<space> 13-digit CNIC to 9966)."}
    return {**base, "found": True, "ntn": rec.ntn, "name": rec.display_name, "tax_year": rec.tax_year}


# ───────────────────────── SRO tracker ─────────────────────────
def find_sro(query="", statute=None, limit=5):
    qs = Instrument.objects.filter(is_active=True)
    if statute in ("income_tax", "sales_tax", "fed", "customs"):
        qs = qs.filter(statute=statute)
    if query:
        cond = Q()
        for w in [w for w in query.split() if len(w) > 2][:6] or [query]:
            cond |= (Q(number__icontains=w) | Q(subject__icontains=w) |
                     Q(related_sections__icontains=w) | Q(summary__icontains=w))
        qs = qs.filter(cond)
    items = []
    for i in qs.order_by("-issue_date")[:limit]:
        items.append({"number": i.number, "type": i.get_instrument_type_display(),
                      "statute": i.get_statute_display(), "issue_date": i.issue_date.isoformat(),
                      "subject": i.subject, "summary": i.summary[:700],
                      "related_sections": i.related_sections,
                      "url": f"/sros/{i.slug}/"})
    return {"source": "TaxBuddy SRO tracker database", "results": items}


# ───────────────────────── blogs ─────────────────────────
_RU_STOP = set("""par pe ka ki ke ko se mein me main hai hain kya kitna kitni kitne aur ya bhi to
jo woh yeh ye hota hoti hote karein karna karte kar liye lye kaise kab kahan agar phir sirf
mera meri mere apna apni apne hum aap tax""".split())


def _blog_words(text):
    import re
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def find_blog(query, limit=4):
    """Related TaxBuddy articles. A post must match at least two of the query's
    key words as whole words (or the only one, for one-word queries), so a vehicle
    question never links an unrelated 'card payments' article."""
    qs = Blog.objects.filter(status="published", is_deleted=False)
    generic = {"tax", "taxes", "pakistan", "fbr", "the", "and", "for", "how", "what", "rate", "rates",
               "2025", "2026", "2027", "income", "section", "under", "with", "from", "ordinance", "law",
               "advance", "withholding", "transfer", "sale", "purchase", "filer", "non", "payment", "collection",
               "minimum", "return", "guide", "explained", "complete"} | _RU_STOP
    words = []
    for w in _blog_words(query):
        if len(w) > 2 and w not in generic and w not in words:
            words.append(w)
    words = words[:8]
    if not words:
        return {"source": "TaxBuddy blog database", "results": []}
    cond = Q()
    for w in words:
        cond |= Q(title__icontains=w) | Q(tag__icontains=w)
    need = 1 if len(words) == 1 else 2
    scored = []
    for b in qs.filter(cond)[:80]:
        toks = set(_blog_words(f"{b.title} {b.tag}"))
        hits = sum(1 for w in words if w in toks or (len(w) >= 5 and any(t.startswith(w) for t in toks)))
        if hits >= need:
            scored.append((hits / len(words), b))
    scored.sort(key=lambda x: -x[0])
    return {"source": "TaxBuddy blog database",
            "results": [{"title": b.title, "url": f"/articles/{b.slug}/", "match": round(sc, 2),
                         "summary": (b.meta_description or "")[:250]} for sc, b in scored[:limit]]}


# ───────────────────────── verified answers (Umair-checked) ─────────────────────────
_VA_CACHE = {"key": None, "rows": []}


def _va_tokens(text):
    return {t for t in law_search._tokens(text) if t not in _RU_STOP}


def _va_rows():
    """Verified answers, re-read only when the table changes."""
    from django.db.models import Count, Max
    from .models import VerifiedAnswer
    qs = VerifiedAnswer.objects.filter(status="verified")
    key = tuple(qs.aggregate(n=Count("id"), t=Max("updated_at")).values())
    if key != _VA_CACHE["key"]:
        rows = []
        for v in qs:
            toks = _va_tokens(v.question)
            rows.append((v, toks))
        _VA_CACHE.update(key=key, rows=rows)
    return _VA_CACHE["rows"]


def find_verified_answer(query, limit=2):
    try:
        rows = _va_rows()
    except Exception:            # table not migrated yet
        return {"results": [], "message": "No verified answers available."}
    q = _va_tokens(query)
    if not q or not rows:
        return {"results": []}
    scored = []
    for v, toks in rows:
        if not toks:
            continue
        overlap = len(q & toks)
        score = overlap / max(len(q), len(toks))   # 0..1, share of words in common
        if overlap >= 2 and score >= 0.3:
            scored.append((score, overlap, v))
    scored.sort(key=lambda x: -x[0])
    out = [{"question": v.question, "answer": v.answer, "section": v.section_ref,
            "match_score": round(s, 2)} for s, o, v in scored[:limit]]
    return {"source": "TaxBuddy verified answers (checked by Umair Mubeen)",
            "note": "Use an answer only if its question really matches the user's question. "
                    "Rates or amounts still come from the calculators / rate card.",
            "results": out}


# ───────────────────────── law books ─────────────────────────
def search_law(query, book=None):
    res = law_search.search_law(query, book=book, k=3)
    return {"results": res} if res else {"results": [], "message": "Nothing found. Try other words."}


def get_law_section(book, number, focus=None):
    res = law_search.get_section(book, number, focus=focus)
    return res or {"error": f"Section/rule {number} not found in {book}. It may be omitted or the number is wrong."}


def get_law_schedule(book, schedule, part=None, division=None, clause=None, focus=None):
    res = law_search.get_schedule(book, schedule, part, division, clause, focus)
    return res or {"error": "That schedule entry was not found. Check the schedule / part / clause, or use search_law."}


# ───────────────────────── schemas ─────────────────────────
BOOK_ENUM = list(law_search.BOOKS)
TOOLS = tax_engine.SCHEMAS + [
    {"name": "find_wht_rates",
     "description": "Search the withholding / advance tax rate card in the database (e.g. '236C property sale', 'bank profit 151', 'vehicle 1300', 'rent 155', 'contracts 153'). Returns rows with uid, filer and non-filer rates.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "tax_year": {"type": "string"}}, "required": ["query"]}},
    {"name": "calculate_wht",
     "description": "Calculate withholding / advance tax for one rate-card row (uid from find_wht_rates) on an amount.",
     "input_schema": {"type": "object", "properties": {
         "uid": {"type": "string"}, "amount": {"type": "number"},
         "status": {"type": "string", "enum": ["filer", "non_filer"]},
         "tax_year": {"type": "string"}}, "required": ["uid", "amount"]}},
    {"name": "check_atl",
     "description": "Check if an NTN or CNIC is on the Active Taxpayers List (site's copy of FBR ATL).",
     "input_schema": {"type": "object", "properties": {
         "ntn_or_cnic": {"type": "string"}}, "required": ["ntn_or_cnic"]}},
    {"name": "find_sro",
     "description": "Search the site's SRO / circular / notification tracker. Empty query returns the latest.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "statute": {"type": "string", "enum": ["income_tax", "sales_tax", "fed", "customs"]}}}},
    {"name": "find_blog",
     "description": "Find published TaxBuddy articles on a topic, to link the user to a detailed guide.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "find_verified_answer",
     "description": "Search answers checked by TaxBuddy's tax expert. Call this FIRST for every tax question. If a result clearly matches the user's question, base your answer on it and keep its section reference.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "search_law",
     "description": "Search the statute books for passages. Books: ito = Income Tax Ordinance 2001, it_rules = Income Tax Rules 2002, sta = Sales Tax Act 1990, st_rules = Sales Tax Rules 2006. Use English legal words.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "book": {"type": "string", "enum": BOOK_ENUM}}, "required": ["query"]}},
    {"name": "get_law_section",
     "description": "Get the current text of one section or rule, e.g. book=ito number=147A, book=it_rules number=81B, book=sta number=8. For a long section (e.g. ito 182 penalties table, ito 2 definitions, sta 33) pass focus with a few words to get the right part.",
     "input_schema": {"type": "object", "properties": {
         "book": {"type": "string", "enum": BOOK_ENUM}, "number": {"type": "string"},
         "focus": {"type": "string", "description": "Optional words to find inside a long section"}},
         "required": ["book", "number"]}},
    {"name": "get_law_schedule",
     "description": "Get text from a Schedule: a Part/Division (e.g. ito First Schedule Part I Division VIII = CGT property rates; Part IV Division VII = vehicles) or one clause (e.g. ito Second Schedule Part I clause 139 = medical allowance exemption).",
     "input_schema": {"type": "object", "properties": {
         "book": {"type": "string", "enum": BOOK_ENUM},
         "schedule": {"type": "string", "description": "First, Second, ... Tenth"},
         "part": {"type": "string", "description": "I, II, III, IV"},
         "division": {"type": "string", "description": "e.g. VIII, IIB"},
         "clause": {"type": "string", "description": "e.g. 139, 9A"},
         "focus": {"type": "string"}},
         "required": ["book", "schedule"]}},
]

_FUNCS = {"find_wht_rates": find_wht_rates,
          "calculate_wht": calculate_wht, "check_atl": check_atl, "find_sro": find_sro,
          "find_blog": find_blog, "find_verified_answer": find_verified_answer, "search_law": search_law, "get_law_section": get_law_section,
          "get_law_schedule": get_law_schedule}


def run_tool(name, args):
    if name in tax_engine.FUNCTIONS:
        try:
            return tax_engine.run(name, args)
        except Exception as e:   # e.g. database not reachable
            return {"error": f"Tool failed: {e.__class__.__name__}"}
    fn = _FUNCS.get(name)
    if fn is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return fn(**(args or {}))
    except TypeError as e:
        return {"error": f"Bad arguments: {e}"}
    except Exception as e:   # never crash the chat on a tool error
        return {"error": f"Tool failed: {e.__class__.__name__}"}