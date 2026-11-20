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
        return out or _FALLBACK_SLABS[key]

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


def _slab_rows(rows):
    out = []
    for i, (lo, hi, rate, base_inc, base_tax) in enumerate(rows):
        lo_disp = lo - 1 if lo % 10 == 1 else lo
        if hi is None:
            rng = f"Above {_lakh(lo_disp)}"
        elif i == 0:
            rng = f"Up to {_lakh(hi)}"
        else:
            rng = f"{_lakh(lo_disp)} – {_lakh(hi)}"
        if not rate:
            tax = "0%"
        else:
            tax = (f"Rs {base_tax:,.0f} + " if base_tax else "") + f"{_pct(rate * 100)} of amount above {_lakh(base_inc)}"
        out.append({"range": rng, "tax": tax, "rate": _pct(rate * 100)})
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
