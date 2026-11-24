"""
Tools for the TaxBuddy AI agent.

Every number the agent gives comes from one of these functions, which read the
site's own database (slabs, WHT rates, ATL, SROs, blogs) or the statute books
in law_texts/. The agent is told never to compute tax from memory.

TOOLS     - the JSON schemas sent to Claude
run_tool  - runs one tool call and returns a JSON-safe dict
"""
from django.db.models import Q

from . import law_search
from .models import (ATLRecord, Blog, Business_AOP_Slab, Instrument,
                     Property_Business_AOP_Slab, TaxBracket, WHTRate)

DEFAULT_YEAR = "2026-2027"
SURCHARGE_THRESHOLD = 10_000_000

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


# ───────────────────────── income tax (slabs) ─────────────────────────
def _surcharge_rate(year, kind):
    """Section 4AB surcharge where taxable income exceeds Rs 10 million."""
    salaried = kind == "salary"
    return {
        "2024-2025": 0.10,
        "2025-2026": 0.09 if salaried else 0.10,
        "2026-2027": 0.0 if salaried else 0.10,
    }.get(year, 0.0)


def calculate_income_tax(income_type, annual_taxable_income, tax_year=DEFAULT_YEAR):
    model = {"salary": TaxBracket, "business": Business_AOP_Slab, "aop": Business_AOP_Slab,
             "rental": Property_Business_AOP_Slab}.get(income_type)
    if model is None:
        return {"error": "income_type must be salary, business, aop or rental"}
    income = float(annual_taxable_income)
    if income < 0:
        return {"error": "Income cannot be negative."}
    slabs = list(model.objects.filter(year=tax_year).order_by("income_min"))
    if not slabs:
        years = sorted(set(model.objects.values_list("year", flat=True)))
        return {"error": f"No slabs in the database for {tax_year}.", "available_years": years}
    slab = None
    for s in slabs:
        hi = float(s.income_max) if s.income_max is not None else float("inf")
        if float(s.income_min) <= income <= hi:
            slab = s
            break
    if slab is None:   # gap between slabs (e.g. 600,000.50) -> nearest lower slab
        slab = [s for s in slabs if float(s.income_min) <= income][-1]
    rate = float(slab.rate)
    base_income = float(slab.base_income)
    base_tax = float(slab.base_tax)
    tax = 0.0 if rate == 0 else base_tax + (income - base_income) * rate
    tax = round(tax)
    sr = _surcharge_rate(tax_year, income_type)
    surcharge = round(tax * sr) if income > SURCHARGE_THRESHOLD else 0
    total = tax + surcharge
    return {
        "source": f"TaxBuddy database slabs ({model._meta.verbose_name}), tax year {tax_year}",
        "income_type": income_type,
        "annual_taxable_income": round(income),
        "slab": {"from": float(slab.income_min),
                 "to": float(slab.income_max) if slab.income_max is not None else None,
                 "fixed_tax": base_tax, "rate_percent": round(rate * 100, 2),
                 "on_income_above": base_income},
        "tax_before_surcharge": tax,
        "surcharge_rate_percent": round(sr * 100, 2) if income > SURCHARGE_THRESHOLD else 0,
        "surcharge": surcharge,
        "total_annual_tax": total,
        "monthly_tax": round(total / 12),
        "effective_rate_percent": round(total / income * 100, 2) if income else 0,
        "calculator_link": CALCULATOR_LINKS["salary"] if income_type == "salary" else None,
        "notes": "Tax on taxable income before tax credits, exempt income and adjustable tax already deducted.",
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
def find_blog(query, limit=4):
    qs = Blog.objects.filter(status="published", is_deleted=False)
    generic = {"tax", "taxes", "pakistan", "fbr", "the", "and", "for", "how", "what", "rate", "rates", "2026", "2027"}
    words = [w for w in query.split() if len(w) > 2 and w.lower() not in generic][:6]
    cond = Q()
    for w in words:
        cond |= Q(title__icontains=w) | Q(tag__icontains=w) | Q(meta_description__icontains=w)
    rows = list(qs.filter(cond)[:40]) if words else []
    rows.sort(key=lambda b: -sum(w.lower() in f"{b.title} {b.tag}".lower() for w in words))
    rows = [b for b in rows if any(w.lower() in f"{b.title} {b.tag}".lower() for w in words)]
    return {"source": "TaxBuddy blog database",
            "results": [{"title": b.title, "url": f"/articles/{b.slug}/",
                         "summary": (b.meta_description or "")[:250]} for b in rows[:limit]]}


# ───────────────────────── law books ─────────────────────────
def search_law(query, book=None):
    res = law_search.search_law(query, book=book, k=3)
    return {"results": res} if res else {"results": [], "message": "Nothing found. Try other words."}


def get_law_section(book, number):
    res = law_search.get_section(book, number)
    return res or {"error": f"Section/rule {number} not found in {book}."}


# ───────────────────────── schemas ─────────────────────────
BOOK_ENUM = list(law_search.BOOKS)
TOOLS = [
    {"name": "calculate_income_tax",
     "description": "Calculate annual income tax from the site's database slabs. Use for salary, business individual, AOP or rental income. Returns slab, tax, surcharge, monthly tax.",
     "input_schema": {"type": "object", "properties": {
         "income_type": {"type": "string", "enum": ["salary", "business", "aop", "rental"]},
         "annual_taxable_income": {"type": "number", "description": "Yearly amount in PKR. Multiply monthly by 12."},
         "tax_year": {"type": "string", "description": "e.g. 2026-2027 (default), 2025-2026"}},
         "required": ["income_type", "annual_taxable_income"]}},
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
    {"name": "search_law",
     "description": "Search the statute books for passages. Books: ito = Income Tax Ordinance 2001, it_rules = Income Tax Rules 2002, sta = Sales Tax Act 1990, st_rules = Sales Tax Rules 2006. Use English legal words.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "book": {"type": "string", "enum": BOOK_ENUM}}, "required": ["query"]}},
    {"name": "get_law_section",
     "description": "Get the full text of one section or rule, e.g. book=ito number=147A, book=it_rules number=38B, book=sta number=8.",
     "input_schema": {"type": "object", "properties": {
         "book": {"type": "string", "enum": BOOK_ENUM}, "number": {"type": "string"}},
         "required": ["book", "number"]}},
]

_FUNCS = {"calculate_income_tax": calculate_income_tax, "find_wht_rates": find_wht_rates,
          "calculate_wht": calculate_wht, "check_atl": check_atl, "find_sro": find_sro,
          "find_blog": find_blog, "search_law": search_law, "get_law_section": get_law_section}


def run_tool(name, args):
    fn = _FUNCS.get(name)
    if fn is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return fn(**(args or {}))
    except TypeError as e:
        return {"error": f"Bad arguments: {e}"}
    except Exception as e:   # never crash the chat on a tool error
        return {"error": f"Tool failed: {e.__class__.__name__}"}