"""
Template tags for the homepage components.

Read-only helpers: they only query existing models, so no view or backend
logic changes. Use in a template with {% load home_tags %}.
"""
from django import template

from ..models import Blog, Instrument

register = template.Library()


@register.simple_tag
def latest_instruments(limit=3):
    """Newest active SROs / circulars / notifications from the SRO tracker."""
    try:
        return list(Instrument.objects.filter(is_active=True)
                    .order_by("-issue_date", "-id")[:int(limit)])
    except Exception:
        return []


@register.simple_tag
def featured_guides(limit=2):
    """Newest published blog posts, used as 'Featured Tax Guides'."""
    try:
        return list(Blog.objects.filter(status="published", is_deleted=False)
                    .order_by("-created_at")[:int(limit)])
    except Exception:
        return []


@register.inclusion_tag("partials/home/calc_card.html")
def calc_card(url, icon, title, desc, variant="tile"):
    """One calculator card. variant: 'tile' (desktop grid) or 'row' (mobile list)."""
    return {"url": url, "icon": icon, "title": title, "desc": desc, "variant": variant}


# Tax Year 2027 (2026-27) slabs from Finance Act 2026, First Schedule Part I
# Division I — used only if the database has no rows for the year.
# Each row: [income_min, income_max (None = no limit), rate, base_income, base_tax]
_FALLBACK_SLABS = {
    "salary": [[0, 600000, 0, 0, 0], [600001, 1200000, .01, 600000, 0],
               [1200001, 2200000, .11, 1200000, 6000], [2200001, 3200000, .20, 2200000, 116000],
               [3200001, 4100000, .25, 3200000, 316000], [4100001, 5600000, .29, 4100000, 541000],
               [5600001, 7000000, .32, 5600000, 976000], [7000001, None, .35, 7000000, 1424000]],
    "business": [[0, 600000, 0, 0, 0], [600001, 1200000, .15, 600000, 0],
                 [1200001, 1600000, .20, 1200000, 90000], [1600001, 3200000, .30, 1600000, 170000],
                 [3200001, 5600000, .40, 3200000, 650000], [5600001, None, .45, 5600000, 1610000]],
}


# Tax Year 2026 (2025-26) salaried slabs, Finance Act 2025 — used only if the DB has no rows.
_FALLBACK_BY_YEAR = {
    "2025-2026": {"salary": [[0, 600000, 0, 0, 0], [600001, 1200000, .01, 600000, 0],
                             [1200001, 2200000, .11, 1200000, 6000], [2200001, 3200000, .23, 2200000, 116000],
                             [3200001, 4100000, .30, 3200000, 346000], [4100001, None, .35, 4100000, 616000]]},
}


@register.simple_tag
def income_slabs(year="2026-2027"):
    """Salary and business/AOP slabs for the homepage quick tax check.

    Read from the same tables the calculators use (TaxBracket, Business_AOP_Slab),
    so the homepage and the calculators always show the same figures.
    """
    from ..models import Business_AOP_Slab, TaxBracket

    def rows(model, key):
        try:
            qs = model.objects.filter(year=year).order_by("income_min")
            out = [[float(s.income_min), float(s.income_max) if s.income_max is not None else None,
                    float(s.rate), float(s.base_income), float(s.base_tax)] for s in qs]
        except Exception:
            out = []
        if out:
            return out
        fb = _FALLBACK_BY_YEAR.get(year, {})
        return fb.get(key) or (_FALLBACK_SLABS[key] if year == "2026-2027" else [])

    return {"year": year,
            "salary": rows(TaxBracket, "salary"),
            "business": rows(Business_AOP_Slab, "business")}


# ───────────────────────── Tax rate tabs ─────────────────────────
def _lakh(n):
    """1200000 -> '12 lakh', 15000000 -> '1.5 crore'."""
    n = float(n)
    if n >= 10_000_000:
        v, unit = n / 10_000_000, "crore"
    elif n >= 100_000:
        v, unit = n / 100_000, "lakh"
    else:
        return f"{n:,.0f}"
    return f"{v:.2f}".rstrip("0").rstrip(".") + " " + unit


def _pct(x):
    return f"{float(x):.2f}".rstrip("0").rstrip(".") + "%"


def _fbr_slab_text(i, row):
    """Wording as in the First Schedule, Part I, Division I table."""
    lo, hi, rate, base_inc, base_tax = row
    lo_disp = lo - 1 if lo % 10 == 1 else lo
    if i == 0 and hi is not None:
        cond = f"Where taxable income does not exceed Rs. {hi:,.0f}"
    elif hi is None:
        cond = f"Where taxable income exceeds Rs. {lo_disp:,.0f}"
    else:
        cond = f"Where taxable income exceeds Rs. {lo_disp:,.0f} but does not exceed Rs. {hi:,.0f}"
    if not rate:
        tax = "0%"
    else:
        tax = (f"Rs. {base_tax:,.0f} + " if base_tax else "") + f"{_pct(rate * 100)} of the amount exceeding Rs. {base_inc:,.0f}"
    return cond, tax


def _slab_rows(rows):
    out = []
    for i, row in enumerate(rows):
        cond, tax = _fbr_slab_text(i, row)
        out.append({"no": i + 1, "range": cond, "tax": tax, "rate": _pct(row[2] * 100)})
    return out


WHT_GROUPS = [
    ("banking", "Bank profit & cash"), ("dividends", "Dividends"),
    ("goods", "Supply of goods"), ("services", "Services"), ("contracts", "Contracts"),
    ("rent", "Rent (s.155)"), ("vehicles", "Vehicles"), ("imports", "Imports"),
    ("exports", "Exports"), ("prizes", "Prizes"), ("other", "Other"),
]

# Capital gains — First Schedule, Part I, Division VII (securities) and Division VIII
# (immovable property), Income Tax Ordinance 2001 as amended by Finance Act 2026.
CGT_PROPERTY_OLD = [   # acquired before 1 July 2024: rate by holding period (years)
    ("Up to 1 year", "15%", "15%", "15%"),
    ("1 – 2 years", "12.5%", "10%", "7.5%"),
    ("2 – 3 years", "10%", "7.5%", "0%"),
    ("3 – 4 years", "7.5%", "5%", "0%"),
    ("4 – 5 years", "5%", "0%", "0%"),
    ("5 – 6 years", "2.5%", "0%", "0%"),
    ("Above 6 years", "0%", "0%", "0%"),
]
CGT_SECURITIES_2022 = [  # acquired 1 July 2022 – 30 June 2024
    ("Up to 1 year", "15%"), ("1 – 2 years", "12.5%"), ("2 – 3 years", "10%"),
    ("3 – 4 years", "7.5%"), ("4 – 5 years", "5%"), ("5 – 6 years", "2.5%"), ("Above 6 years", "0%"),
]


@register.simple_tag
def rate_tables(year="2026-2027"):
    """Everything the 'Tax Rates' tabs show. Salary, business and withholding rates
    come from the database (same tables as the calculators); capital gains rates
    are the statutory tables quoted above."""
    from ..models import WHTRate

    slabs = income_slabs(year)
    try:
        wht = list(WHTRate.objects.filter(tax_year=year, is_active=True).order_by("sort_order", "id"))
    except Exception:
        wht = []

    def rate(r, which):
        v = getattr(r, which)
        if r.rate_kind == "fixed":
            return f"Rs {float(v):,.0f}"
        return _pct(v)

    def slab_text(r, which):
        """'Rs 15,000 + 10% over 600,000'. Non-filer: rate and fixed amount scale together."""
        f, v = float(r.filer), float(getattr(r, which))
        if not v:
            return "0%"
        start = (r.slab_min or 0) - 1 if (r.slab_min or 0) % 10 == 1 else (r.slab_min or 0)
        base = float(r.base_tax or 0) * (v / f if f else 1)
        return (f"Rs {base:,.0f} + " if base else "") + f"{_pct(v)} over {start:,.0f}"

    def row(r):
        slab = r.rate_kind == "slab" and r.slab_min is not None
        return {"section": r.section, "name": r.name, "detail": r.sub,
                "filer": slab_text(r, "filer") if slab else rate(r, "filer"),
                "non_filer": slab_text(r, "non_filer") if slab else rate(r, "non_filer"),
                "nature": r.tax_type}

    prop = [row(r) for r in wht if r.section in ("236C", "236K")]
    rent = [row(r) for r in wht if r.cat == "rent"]
    groups = []
    for key, label in WHT_GROUPS:
        items = [row(r) for r in wht if r.cat == key and r.section not in ("149",)]
        if items:
            groups.append({"key": key, "label": label, "rows": items})

    return {
        "year": year,
        "salary": _slab_rows(slabs["salary"]),
        "business": _slab_rows(slabs["business"]),
        "property": prop, "rent": rent, "wht_groups": groups,
        "cgt_property_old": CGT_PROPERTY_OLD, "cgt_securities_2022": CGT_SECURITIES_2022,
    }


# ───────────────────────── Blog pages ─────────────────────────
@register.simple_tag
def blog_categories(limit=12):
    """Published categories with article counts, most used first, for the blog filter chips."""
    from django.db.models import Count
    from django.utils.text import slugify
    try:
        rows = (Blog.objects.filter(status="published", is_deleted=False)
                .exclude(category="").values("category")
                .annotate(n=Count("id")).order_by("-n")[:limit])
        return [{"label": r["category"], "slug": slugify(r["category"]), "count": r["n"]} for r in rows]
    except Exception:
        return []


@register.filter
def read_minutes(html):
    """Approximate reading time in minutes (200 words a minute)."""
    import re
    words = len(re.sub(r"<[^>]+>", " ", html or "").split())
    return max(1, round(words / 200))


@register.simple_tag
def salary_compare(new_year="2026-2027", old_year="2025-2026"):
    """Rows for the salary calculator's slab table: this year's slabs from the DB,
    with last year's rate at the same income level for comparison."""
    new = income_slabs(new_year)["salary"]
    old = income_slabs(old_year)["salary"]

    def old_rate(x):
        for lo, hi, rate, *_ in old:
            if hi is None or x <= hi:
                return rate
        return old[-1][2] if old else None

    rows = []
    for i, (lo, hi, rate, base_inc, base_tax) in enumerate(new):
        lo_disp = lo - 1 if lo % 10 == 1 else lo
        o = old_rate(lo_disp + 1) if old else None
        if hi is None:
            rng, mrng = f"Above {lo_disp:,.0f}", f"Above {lo_disp / 12:,.0f}"
        elif i == 0:
            rng, mrng = f"Up to {hi:,.0f}", f"Up to {hi / 12:,.0f}"
        else:
            rng, mrng = f"{lo:,.0f} – {hi:,.0f}", f"{lo / 12:,.0f} – {hi / 12:,.0f}"
        if not rate:
            formula = "No tax"
        else:
            formula = (f"{base_tax:,.0f} + " if base_tax else "") + f"{_pct(rate * 100)} above {base_inc:,.0f}"
        rows.append({"lo": int(lo), "hi": int(hi) if hi is not None else 999999999999,
                     "range": rng, "monthly": mrng,
                     "old": _pct(o * 100) if o is not None else "—", "new": _pct(rate * 100),
                     "changed": o is not None and abs(o - rate) > 1e-9, "formula": formula})
    return rows


@register.simple_tag
def wht_rate_map(year="2026-2027"):
    """{uid: {f, n, kind, section, base, min, max}} for every active WHT rate-card row.
    Calculator pages mark their options with data-uid; a small script swaps in these
    database rates so every calculator uses the same figures as the WHT Card."""
    from ..models import WHTRate
    out = {}
    try:
        for r in WHTRate.objects.filter(tax_year=year, is_active=True):
            out[r.uid] = {"f": float(r.filer), "n": float(r.non_filer), "kind": r.rate_kind,
                          "section": r.section, "base": float(r.base_tax) if r.base_tax is not None else None,
                          "min": r.slab_min, "max": r.slab_max}
    except Exception:
        pass
    return out


@register.simple_tag
def slab_rows(kind="salary", year="2026-2027"):
    """Slab table rows (range text + tax text) for the calculator pages, from the DB."""
    rows = income_slabs(year).get(kind) or []
    out = []
    for i, row in enumerate(rows):
        cond, tax = _fbr_slab_text(i, row)
        out.append({"no": i + 1, "range": cond, "tax": tax})
    return out


# ───────────────────────── Quick Tax Check (all tabs) ─────────────────────────
# Rental income of individuals / AOPs (s.15, Division VIA, First Schedule) — fallback only.
_FALLBACK_RENTAL = [[0, 300000, 0, 0, 0], [300001, 600000, .05, 300000, 0],
                    [600001, 2000000, .10, 600000, 15000], [2000001, None, .25, 2000000, 155000]]
# Section 4C, Tax Year 2027 (Finance Act 2026), most persons — fallback only.
_FALLBACK_4C = [[0, 500000000, 0], [500000001, None, .08]]
_QTC_SECTIONS = ("153", "231B", "234", "236C", "236K")


@register.simple_tag
def quick_check_data(year="2026-2027"):
    """Everything the homepage Quick Tax Check tabs need, from the same tables as the
    calculators: income slabs, rental slabs, Section 4C rates and the WHT rows for
    153 / 231B / 234 / 236C / 236K. Each part falls back to the Finance Act 2026
    figures only when its table has no rows."""
    from ..models import Property_Business_AOP_Slab, SuperTax4CRate, WHTRate

    data = income_slabs(year)

    try:
        rental = [[float(s.income_min), float(s.income_max) if s.income_max is not None else None,
                   float(s.rate), float(s.base_income), float(s.base_tax)]
                  for s in Property_Business_AOP_Slab.objects.filter(year=year).order_by("income_min")]
    except Exception:
        rental = []
    data["rental"] = rental or _FALLBACK_RENTAL

    # 4C table is keyed on the tax year number: "2026-2027" -> 2027
    ty = int(year.split("-")[-1]) if "-" in year else int(year)
    try:
        sup = [[float(s.income_from), float(s.income_to) if s.income_to is not None else None, float(s.rate)]
               for s in SuperTax4CRate.objects.filter(tax_year=ty).order_by("income_from")]
    except Exception:
        sup = []
    data["super4c"] = sup or (_FALLBACK_4C if ty == 2027 else [])
    data["tax_year"] = ty

    wht = []
    try:
        for r in (WHTRate.objects.filter(tax_year=year, is_active=True, section__in=[
                  "153", "153(1)(a)", "153(1)(b)", "153(1)(c)", "153(2A)", "231B", "231B(2)", "234", "236C", "236K"])
                  .order_by("sort_order", "id")):
            wht.append({"uid": r.uid, "section": r.section, "name": r.name, "sub": r.sub,
                        "kind": r.rate_kind, "f": float(r.filer), "n": float(r.non_filer),
                        "type": r.tax_type, "nature": r.nature})
    except Exception:
        wht = []
    if not wht:
        try:
            from ..management.commands.seed_wht_calc_2026 import ROWS, YEAR
            if YEAR == year:
                wht = [{"uid": t[0], "section": t[1], "name": t[3], "sub": t[4], "kind": t[5],
                        "f": float(t[6]), "n": float(t[8]), "type": t[10], "nature": t[9]}
                       for t in ROWS if t[1].split("(")[0] in _QTC_SECTIONS]
        except Exception:
            wht = []
    data["wht"] = wht
    return data