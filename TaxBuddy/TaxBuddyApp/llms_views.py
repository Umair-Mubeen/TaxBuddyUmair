"""
TaxBuddyApp/llms_views.py — /llms-full.txt

Plain-Markdown copy of the site's core numbers (salary, business, AOP and rental
slabs + the withholding tax rate card) so AI assistants can read and cite them
without parsing HTML tables. Built live from the database, so it updates itself
whenever the slabs / rate card are re-seeded. Cached for 6 hours.

urls.py (next to the llms.txt line):
    path('llms-full.txt', llms_views.llms_full_txt, name='llms_full_txt'),
and at the top of urls.py:
    from . import llms_views
"""
from django.core.cache import cache
from django.http import HttpResponse

from .models import Business_AOP_Slab, Property_Business_AOP_Slab, TaxBracket, WHTRate

SITE = "https://www.taxbuddyumair.com"
YEAR = "2026-2027"          # Tax Year 2027 (1 July 2026 – 30 June 2027)
PREV = "2025-2026"
CACHE_KEY = "llms_full_txt_v1"


def _rs(x):
    return f"Rs {float(x):,.0f}"


def _slab_table(model, year):
    rows = list(model.objects.filter(year=year).order_by("income_min"))
    if not rows:
        return ["_(see the calculator page for this table)_", ""]
    out = ["| Taxable income (annual) | Tax |", "|---|---|"]
    for s in rows:
        lo, hi = float(s.income_min), s.income_max
        band = f"Above {_rs(s.base_income or lo)}" if hi is None else (
            f"Up to {_rs(hi)}" if lo <= 1 else f"{_rs(lo)} – {_rs(hi)}")
        rate = float(s.rate) * 100
        if rate == 0:
            tax = "0%"
        elif float(s.base_tax):
            tax = f"{_rs(s.base_tax)} + {rate:g}% of income above {_rs(s.base_income)}"
        else:
            tax = f"{rate:g}% of income above {_rs(s.base_income)}"
        out.append(f"| {band} | {tax} |")
    return out + [""]


def _rate(r, v):
    v = float(v)
    if r.rate_kind == "fixed":
        return _rs(v)
    if r.rate_kind == "per_unit":
        return f"Rs {v:g}/unit"
    return f"{v:g}%"


def _wht_section():
    qs = WHTRate.objects.filter(tax_year=YEAR, is_active=True).order_by("cat", "sort_order", "section")
    rows = list(qs)
    if not rows:
        return ["_(rate card not available)_", ""]
    out, cats = [], dict(WHTRate.CAT_CHOICES)
    current = None
    for r in rows:
        if r.cat != current:
            current = r.cat
            out += ["", f"### {cats.get(r.cat, r.cat)}", "",
                    "| Section | Transaction | Filer (ATL) | Non-ATL | Nature |", "|---|---|---|---|---|"]
        name = r.name + (f" — {r.sub}" if r.sub else "")
        if r.rate_kind == "slab" and r.slab_min is not None:
            hi = "and above" if r.slab_max is None else f"to {_rs(r.slab_max)}"
            name += f" ({_rs(r.slab_min)} {hi})"
            if r.base_tax:
                name += f" — fixed {_rs(r.base_tax)} +"
        name = name.replace("|", "/")
        out.append(f"| {r.section} | {name} | {_rate(r, r.filer)} | {_rate(r, r.non_filer)} | "
                   f"{r.tax_type} ({r.nature}) |")
    return out + [""]


def _build():
    L = [
        "# TaxBuddy Umair — Pakistan tax rates and slabs (full data)",
        "",
        f"> Machine-readable copy of the numbers used by the calculators on {SITE}. "
        "Tax Year 2027 = income from 1 July 2026 to 30 June 2027 (Finance Act 2026). "
        "Source law: Income Tax Ordinance 2001 (First Schedule, Tenth Schedule) and Sales Tax Act 1990. "
        "Educational information, not professional advice. Not affiliated with FBR.",
        "",
        f"Summary index: {SITE}/llms.txt",
        "",
        "## 1. Salary income — tax slabs",
        "",
        f"### Tax Year 2027 ({YEAR}) — Finance Act 2026",
        "",
        *_slab_table(TaxBracket, YEAR),
        f"### Tax Year 2026 ({PREV}) — for comparison",
        "",
        *_slab_table(TaxBracket, PREV),
        "Surcharge (section 4AB): nil for salaried individuals from Tax Year 2027 "
        "(it was 9% in Tax Year 2026 where taxable income exceeded Rs 10 million).",
        f"Calculator: {SITE}/SalaryCalculator/",
        "",
        "## 2. Business individuals and AOPs — tax slabs",
        "",
        f"### Tax Year 2027 ({YEAR})",
        "",
        *_slab_table(Business_AOP_Slab, YEAR),
        "Surcharge (section 4AB): 10% of tax where taxable income exceeds Rs 10 million (non-salaried).",
        f"Calculators: {SITE}/BusinessCalculator/ · {SITE}/AOPCalculator/",
        "",
        "## 3. Rental income (income from property, section 15)",
        "",
        "Gross rent less allowable deductions (one-fifth repair allowance and others under section 15A) "
        "is taxed with other income at the normal slab rates. The separate property-income rate table "
        "(Division VIA) was omitted by the Finance Act 2021.",
        "",
        *([f"### Rental slab table in our calculator ({YEAR})", "",
           *_slab_table(Property_Business_AOP_Slab, YEAR)]
          if Property_Business_AOP_Slab.objects.filter(year=YEAR).exists() else []),
        f"Calculator: {SITE}/PropertyCalculator/",
        "",
        "## 4. Key rules (Tax Year 2027)",
        "",
        "- Active Taxpayers List (ATL): updated daily by FBR (SRO 1638(I)/2024). Persons not on the ATL "
        "pay higher withholding rates under the Tenth Schedule.",
        "- Late return: a late filer joins the ATL only after paying the section 182A surcharge "
        "(Rs 25,000 / 50,000 / 100,000 by category); individuals may also file Form ATL-U. "
        "Separate 'late filer' withholding rates (Tenth Schedule rule 1A) were omitted by the Finance Act 2026.",
        "- Purchase of immovable property (236K): 1.25% of fair market value for ATL persons; "
        "non-ATL 10.5% (up to Rs 50M), 14.5% (Rs 50–100M), 18.5% (above Rs 100M).",
        "- Sale of immovable property (236C): 2.75% of gross consideration (Finance Act 2026).",
        "- Section 7E (deemed income on immovable property) was omitted by the Finance Act 2026.",
        "- Cash withdrawal (231AB): 0.8% for persons not on the ATL on withdrawals above Rs 50,000 a day.",
        "- Export of IT services (154A): 0.25% for PSEB-registered exporters (up to Tax Year 2029), 1% otherwise.",
        "- Advance tax (147): individuals pay on 15 September, 15 December, 15 March and 15 June; "
        "companies and AOPs on 25 September, 25 December, 25 March and 15 June.",
        "- Withholding tax deposit (Income Tax Rules 2002, rule 43): within 7 days from the end of each week "
        "ending on Sunday (same day for Government).",
        "- Return due date (section 118): 30 September for individuals and AOPs; 31 December for companies "
        "whose tax year ends between 1 January and 30 June.",
        "",
        f"## 5. Withholding and advance tax rate card ({YEAR})",
        "",
        "Percent rates unless shown in rupees. 'Non-ATL' = person not on the Active Taxpayers List.",
        *_wht_section(),
        f"Full interactive card: {SITE}/Withholding-Tax-Card/ · Section 153 calculator: "
        f"{SITE}/section-153-withholding-tax-calculator/",
        "",
    ]
    return "\n".join(L) + "\n"


def llms_full_txt(request):
    body = cache.get(CACHE_KEY)
    if body is None:
        body = _build()
        cache.set(CACHE_KEY, body, 60 * 60 * 6)
    return HttpResponse(body, content_type="text/plain; charset=utf-8")
