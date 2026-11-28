"""
TaxBuddyApp/tax_engine.py — Phase 2 of the TaxBuddy Umair AI upgrade.

One Python function per calculator. Each returns a plain dict:

    result      the headline number(s)
    working     step-by-step lines a person can check
    law         the sections / Schedule entries the numbers come from
    tax_nature  final / minimum / adjustable / separate block / exempt, with the reason
    notes       conditions and caveats
    calculator  link to the matching page on taxbuddyumair.com

Every rate below was checked against the Income Tax Ordinance, 2001 as amended
up to 30 June 2026 (Finance Act 2026) in law_texts/ito_2001.txt. Slab tax still
reads the site's own slab tables, so the AI and the calculator pages agree.

No Django import at module level: the pure functions can be unit-tested alone.
"""
from datetime import date

CURRENT_TAX_YEAR = "2026-2027"
SURCHARGE_THRESHOLD = 10_000_000

LINKS = {
    "salary": "/SalaryCalculator/",
    "business": "/BusinessCalculator/",
    "aop": "/AOPCalculator/",
    "rental": "/PropertyCalculator/",
    "super_tax": "/TaxCalculator4C/",
    "advance_tax": "/advance-tax-calculator/",
    "cgt": "/capital-gains-tax-calculator/",
    "property": "/karachi-fmv-calculator/",
    "vehicle": "/motor-vehicle-tax-calculator/",
    "fmv": "/karachi-fmv-calculator/",
    "wht": "/Withholding-Tax-Card/",
}


class EngineError(ValueError):
    """Bad input — the message is safe to show to the user."""


# ───────────────────────── helpers ─────────────────────────
def _num(value, name, allow_zero=True):
    try:
        v = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        raise EngineError(f"{name} must be a number.")
    if v < 0 or (v == 0 and not allow_zero):
        raise EngineError(f"{name} must be more than zero." if not allow_zero else f"{name} cannot be negative.")
    return v


def _date(value, name):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise EngineError(f"{name} must be a date like 2024-08-15.")


def _add_years(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:                      # 29 February
        return d.replace(year=d.year + n, day=28)


def _holding_band(acq, disp):
    """Return n where the holding period exceeds n-1 years but does not exceed n years."""
    n = 1
    while disp > _add_years(acq, n):
        n += 1
    return n


def _holding_years(acq, disp):
    return round((disp - acq).days / 365.25, 2)


def _tax_year_of(d):
    """Pakistan tax year ends 30 June: 15 Aug 2026 -> 2026-2027."""
    end = d.year + 1 if d.month >= 7 else d.year
    return f"{end - 1}-{end}"


def _year_end(tax_year):
    """'2026-2027' or 2027 -> 2027."""
    s = str(tax_year).strip()
    try:
        return int(s.split("-")[-1]) if "-" in s else int(s)
    except ValueError:
        raise EngineError("tax_year must look like 2026-2027.")


def _on_atl(value):
    v = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return v not in ("false", "0", "no", "non_filer", "nonfiler", "non_atl", "not_on_atl")


def _rs(x):
    return f"Rs {round(x):,}"


def _out(result, working, law, nature, notes, link, **extra):
    d = {"result": result, "working": working, "law": law, "tax_nature": nature,
         "notes": notes, "calculator": LINKS.get(link)}
    d.update(extra)
    return d


# ═════════════════════ 1. income tax on slabs (+ s.63 VPS credit) ═════════════════════
def surcharge_rate(tax_year, income_type):
    """Section 4AB surcharge (taxable income above Rs 10 million)."""
    salaried = income_type == "salary"
    return {"2024-2025": 0.10,
            "2025-2026": 0.09 if salaried else 0.10,
            "2026-2027": 0.0 if salaried else 0.10}.get(tax_year, 0.0)


def slab_tax(income, slabs):
    """slabs: list of (income_min, income_max|None, rate, base_income, base_tax).
    Same maths as views.calculate_tax used by the calculator pages."""
    pick = None
    for lo, hi, rate, base_income, base_tax in slabs:
        if lo <= income <= (hi if hi is not None else float("inf")):
            pick = (lo, hi, rate, base_income, base_tax)
            break
    if pick is None:                     # gap such as 600,000.50 → nearest lower slab
        lower = [s for s in slabs if s[0] <= income]
        if not lower:
            return 0, None
        pick = lower[-1]
    lo, hi, rate, base_income, base_tax = pick
    tax = 0 if rate == 0 else round(base_tax + (income - base_income) * rate)
    return tax, pick


def vps_credit(tax, income, contribution):
    """Section 63: credit = (A / B) x C, where C is the contribution up to 20% of taxable income."""
    if contribution <= 0 or income <= 0 or tax <= 0:
        return 0, 0
    allowed = min(contribution, 0.20 * income)
    return min(round(tax / income * allowed), tax), round(allowed)


def _load_slabs(income_type, tax_year):
    from .models import Business_AOP_Slab, Property_Business_AOP_Slab, TaxBracket
    model = {"salary": TaxBracket, "business": Business_AOP_Slab, "aop": Business_AOP_Slab,
             "rental": Property_Business_AOP_Slab}[income_type]
    rows = list(model.objects.filter(year=tax_year).order_by("income_min"))
    if not rows:
        years = sorted(set(model.objects.values_list("year", flat=True)))
        raise EngineError(f"No {income_type} slabs saved for {tax_year}. Years available: {', '.join(years)}.")
    return [(float(s.income_min), float(s.income_max) if s.income_max is not None else None,
             float(s.rate), float(s.base_income), float(s.base_tax)) for s in rows]


def income_tax(income_type, annual_taxable_income, tax_year=CURRENT_TAX_YEAR,
               vps_contribution=0, slabs=None):
    if income_type not in ("salary", "business", "aop", "rental"):
        raise EngineError("income_type must be salary, business, aop or rental.")
    income = _num(annual_taxable_income, "Annual taxable income")
    vps = _num(vps_contribution or 0, "VPS contribution")
    slabs = slabs if slabs is not None else _load_slabs(income_type, tax_year)
    tax, slab = slab_tax(income, slabs)

    working = []
    if slab:
        lo, hi, rate, base_income, base_tax = slab
        band = f"{_rs(lo)} – {_rs(hi)}" if hi is not None else f"above {_rs(lo)}"
        if rate == 0:
            working.append(f"Slab {band}: 0% → tax Rs 0")
        else:
            working.append(f"Slab {band}: {_rs(base_tax)} + {rate * 100:g}% of income above {_rs(base_income)}")
            working.append(f"{_rs(base_tax)} + {rate * 100:g}% × {_rs(income - base_income)} = {_rs(tax)}")

    credit = allowed = 0
    if income_type in ("salary", "business") and vps:
        credit, allowed = vps_credit(tax, income, vps)
        if credit:
            working.append(f"VPS credit s.63: ({_rs(tax)} ÷ {_rs(income)}) × {_rs(allowed)} = {_rs(credit)}")
    net = tax - credit

    sr = surcharge_rate(tax_year, income_type)
    surcharge = round(net * sr) if income > SURCHARGE_THRESHOLD else 0
    if surcharge:
        working.append(f"Surcharge s.4AB {sr * 100:g}% of {_rs(net)} = {_rs(surcharge)}")
    total = net + surcharge

    law = ["Division I of Part I of the First Schedule (rates)"]
    if income_type == "salary":
        law = ["Paragraph (1A) of Division I of Part I of the First Schedule (salary rates)", "s.149 (employer deduction)"]
    if income_type == "rental":
        law = ["s.15 (income from property)", "Division VIA of Part I of the First Schedule"]
    if credit:
        law.append("s.63 (VPS pension contribution credit)")
    if surcharge:
        law.append("s.4AB (surcharge)")

    nature = {"type": "normal tax regime",
              "why": "Tax on taxable income at slab rates. Adjustable tax already deducted or collected "
                     "(for example s.149, 231B, 236K) is credited against it in the return."}
    notes = ["Taxable income means income after exempt income and deductible allowances; tax credits other "
             "than VPS (s.61 donations, s.62 shares, s.63A housing loan, s.60D tuition) are not applied here."]
    if income_type == "salary" and income > SURCHARGE_THRESHOLD:
        notes.append(f"No surcharge for salaried individuals in {tax_year}." if not sr else "")
    if vps and income_type not in ("salary", "business"):
        notes.append("The s.63 VPS credit is only for individuals, so it was not applied.")

    return _out(
        {"annual_tax": total, "monthly_tax": round(total / 12), "tax_before_credits": tax,
         "vps_credit": credit, "vps_allowed": allowed, "surcharge": surcharge,
         "effective_rate_percent": round(total / income * 100, 2) if income else 0},
        working, law, nature, [n for n in notes if n], income_type,
        inputs={"income_type": income_type, "annual_taxable_income": round(income),
                "tax_year": tax_year, "vps_contribution": round(vps)},
        source=f"TaxBuddy slab tables ({income_type}), tax year {tax_year}")


# ═════════════════════ 2. super tax — section 4C ═════════════════════
_4C_GENERAL = {   # Division IIB, Part I, First Schedule: (upper limit, rate) — rate applies to the WHOLE income
    2022: [(150e6, 0), (200e6, .01), (250e6, .02), (300e6, .03), (None, .04)],
    2023: [(150e6, 0), (200e6, .01), (250e6, .02), (300e6, .03), (350e6, .04), (400e6, .06), (500e6, .08), (None, .10)],
    2026: [(150e6, 0), (200e6, .01), (250e6, .015), (300e6, .025), (350e6, .035), (400e6, .055), (500e6, .075), (None, .10)],
}
_4C_GENERAL[2024] = _4C_GENERAL[2025] = _4C_GENERAL[2023]
_4C_SECTORS = ("banking", "petroleum_fifth_schedule", "fertilizer")


def super_tax_4c(income_under_4c, tax_year=CURRENT_TAX_YEAR, person="other"):
    income = _num(income_under_4c, "Income under section 4C")
    ty = _year_end(tax_year)
    if person not in _4C_SECTORS + ("other",):
        raise EngineError("person must be other, banking, petroleum_fifth_schedule or fertilizer.")
    notes = ["'Income' for s.4C is the sum of taxable income, final/separate-block income (dividends, profit "
             "on debt, capital gains etc.) and income implied from final tax deducted — see s.4C(2)."]
    if ty >= 2027:
        if person == "other":
            rate = 0.08 if income > 500e6 else 0
            rule = "8% where income exceeds Rs 500 million (persons other than banks, Fifth Schedule petroleum, fertilizer)"
        else:
            rate = 0.10 if income > 150e6 else 0
            rule = f"10% where income exceeds Rs 150 million ({person.replace('_', ' ')})"
        law = ["s.4C", "Division IIB of Part I of the First Schedule (Table substituted by Finance Act 2026)"]
    elif ty in _4C_GENERAL:
        rate = next(r for hi, r in _4C_GENERAL[ty] if hi is None or income <= hi)
        rule = f"Tax year {ty} table"
        law = ["s.4C", "Division IIB of Part I of the First Schedule (table in force for that year)"]
        if person != "other":
            notes.append("Sector rates for banks are in the provisos for that year; this uses the general table.")
    else:
        raise EngineError("Super tax applies from tax year 2022.")
    tax = round(income * rate)
    return _out(
        {"rate_percent": round(rate * 100, 2), "super_tax": tax},
        [rule, f"{rate * 100:g}% × {_rs(income)} = {_rs(tax)}" if rate else "Below the threshold → Rs 0"],
        law,
        {"type": "separate tax", "why": "Super tax is charged in addition to normal income tax on the whole "
                                         "income once it crosses the threshold (not only on the excess)."},
        notes, "super_tax", tax_year=f"{ty - 1}-{ty}")


# ═════════════════════ 3. advance tax — section 147 ═════════════════════
_DUE_INDIVIDUAL = {"sep": "15 September", "dec": "15 December", "mar": "15 March", "jun": "15 June"}
_DUE_COMPANY = {"sep": "25 September", "dec": "25 December", "mar": "25 March", "jun": "15 June"}


def advance_tax_147(taxpayer, quarter="sep", latest_assessed_income=0, latest_tax_assessed=0,
                    quarter_credit=0, quarter_turnover=None, latest_year_turnover=0,
                    tax_4c=0, tax_113=0, tax_113c=0, capital_gain=0, holding="lt6"):
    quarter = str(quarter).lower()[:3]
    if quarter not in _DUE_INDIVIDUAL:
        raise EngineError("quarter must be sep, dec, mar or jun.")
    credit = _num(quarter_credit or 0, "Tax credit for the quarter")
    nature = {"type": "advance tax (adjustable)",
              "why": "Advance tax is a payment towards the final tax for the year and is adjusted in the return (s.147(8))."}

    if taxpayer == "individual":
        income = _num(latest_assessed_income, "Latest assessed taxable income")
        if income < 1_000_000:
            return _out({"payable": 0, "applicable": False},
                        [f"Latest assessed income {_rs(income)} is below Rs 1,000,000"],
                        ["s.147(2)"], nature,
                        ["Income under s.5, 6, 7, s.149 salary and final-tax income is left out when checking the Rs 1 million limit."],
                        "advance_tax")
        a = _num(latest_tax_assessed, "Latest tax assessed")
        share = round(a / 4)
        pay = max(0, share - credit)
        return _out({"payable": pay, "applicable": True, "due_date": _DUE_INDIVIDUAL[quarter]},
                    [f"(A ÷ 4) − B = ({_rs(a)} ÷ 4) − {_rs(credit)} = {_rs(pay)}"],
                    ["s.147(4B)", "s.147(5) due dates"], nature,
                    ["A includes super tax under s.4C. B is tax credited under s.168 in the quarter, "
                     "other than salary tax deducted under s.149."], "advance_tax")

    if taxpayer in ("company", "aop"):
        c = _num(latest_year_turnover, "Turnover of the latest tax year", allow_zero=False)
        extra = sum(_num(x or 0, "4C/113/113C tax") for x in (tax_4c, tax_113, tax_113c))
        b = _num(latest_tax_assessed, "Latest tax assessed") + extra
        working = []
        if quarter_turnover in (None, ""):
            a = round(c * 1.20 / 4)
            working.append(f"Quarter turnover not given: 120% × {_rs(c)} ÷ 4 = {_rs(a)} (s.147(4) proviso)")
        else:
            a = _num(quarter_turnover, "Turnover for the quarter")
        computed = round(a * b / c)
        pay = max(0, computed - credit)
        working.append(f"(A × B ÷ C) − D = ({_rs(a)} × {_rs(b)} ÷ {_rs(c)}) − {_rs(credit)} = {_rs(pay)}")
        return _out({"payable": pay, "due_date": _DUE_COMPANY[quarter]}, working,
                    ["s.147(4)", "s.147(4AA) (4C, 113, 113C included in B)", "s.147(5A) due dates"], nature,
                    ["If tax for the year will be higher, s.147(4A) requires an estimate by the 2nd quarter due date."],
                    "advance_tax")

    if taxpayer == "securities":
        gain = _num(capital_gain, "Capital gain for the quarter")
        rate = 2.0 if holding == "lt6" else 1.5
        tax = round(gain * rate / 100)
        return _out({"payable": tax, "rate_percent": rate},
                    [f"{rate}% × {_rs(gain)} = {_rs(tax)}"], ["s.147(5B)"], nature,
                    ["Payable within 21 days after the quarter ends.", "Does not apply to individual investors."],
                    "advance_tax")
    raise EngineError("taxpayer must be individual, company, aop or securities.")


# ═════════════════════ 4. capital gains — immovable property (s.37(1A)) ═════════════════════
_CGT_OLD = {   # Division VIII, Part I, First Schedule — property acquired on or before 30 June 2024
    "plot":        [15, 12.5, 10, 7.5, 5, 2.5, 0],
    "constructed": [15, 10, 7.5, 5, 0],
    "flat":        [15, 7.5, 0],
}
_CUTOFF = date(2024, 7, 1)


def cgt_property(property_type, acquisition_date, sale_price, cost, disposal_date=None, fmv=0,
                 expenses=0, on_atl=True, cash_purchase=False, forces_or_govt_allottee=False):
    if property_type not in _CGT_OLD:
        raise EngineError("property_type must be plot, constructed or flat.")
    acq = _date(acquisition_date, "Acquisition date")
    disp = _date(disposal_date, "Disposal date") if disposal_date else date.today()
    if disp < acq:
        raise EngineError("Disposal date cannot be before acquisition date.")
    sale = _num(sale_price or 0, "Sale price")
    fmv = _num(fmv or 0, "FBR value")
    cost = _num(cost, "Cost of acquisition")
    exp = _num(expenses or 0, "Expenses")
    atl = _on_atl(on_atl)

    consideration = max(sale, fmv)
    working = [f"Consideration = higher of sale price and fair market value = {_rs(consideration)} (s.77(1))"]
    law = ["s.37(1A)", "s.37(2)", "s.77(1)", "Division VIII of Part I of the First Schedule"]
    notes = []
    property_fmv = max(fmv, sale, cost)
    cost_allowed = cost
    if cash_purchase and property_fmv > 5_000_000:
        cost_allowed = 0
        law.append("s.75A(3)(b)")
        notes.append("Bought outside the banking channel with value above Rs 5 million: the purchase price is not "
                     "allowed as cost (s.75A).")
        working.append("Cost not allowed under s.75A → Rs 0")
    gain = consideration - cost_allowed - exp
    working.append(f"Gain = {_rs(consideration)} − {_rs(cost_allowed)} − {_rs(exp)} = {_rs(gain)}")

    years = _holding_years(acq, disp)
    band = _holding_band(acq, disp)
    if gain <= 0:
        rate, regime = 0, "no gain"
    elif acq >= _CUTOFF:
        regime = "acquired on/after 1 July 2024"
        rate = 15
        working.append(f"Acquired on/after 1 July 2024 → flat 15% {'(on ATL)' if atl else '(minimum 15% for non-ATL)'}")
        if not atl:
            notes.append("Not on the ATL: gain is taxed at normal slab rates with a minimum of 15%; this shows the "
                         "15% minimum, the real rate may be higher.")
    else:
        regime = "acquired on/before 30 June 2024"
        table = _CGT_OLD[property_type]
        rate = table[min(band, len(table)) - 1]
        working.append(f"Holding {years} years ({property_type}) → {rate}%")

    tax = round(max(gain, 0) * rate / 100)
    working.append(f"CGT = {rate}% × {_rs(max(gain, 0))} = {_rs(tax)}")
    if forces_or_govt_allottee and tax:
        cut = 75 if disp > _add_years(acq, 3) else 50
        relief = round(tax * cut / 100)
        tax -= relief
        law.append("Clause (9A) of Part III of the Second Schedule")
        working.append(f"Clause 9A relief −{cut}% = −{_rs(relief)} → {_rs(tax)}")
        notes.append("Clause 9A: first sale by an original allottee (armed forces / government), certified by "
                     "the allotment authority.")

    return _out(
        {"capital_gain": round(max(gain, 0)), "rate_percent": rate, "cgt": tax,
         "holding_years": years, "regime": regime},
        working, law,
        {"type": "separate block",
         "why": "Gain on immovable property is taxed under s.37(1A) at Division VIII rates, separately from "
                "other income. Advance tax collected under s.236C on the sale is adjusted against it."},
        notes, "cgt", tax_year=_tax_year_of(disp))


# ═════════════════════ 5. capital gains — securities (s.37A) ═════════════════════
def cgt_securities(gain, acquisition_date, disposal_date=None, on_atl=True, pmex_futures=False):
    g = _num(gain, "Capital gain")
    acq = _date(acquisition_date, "Acquisition date")
    disp = _date(disposal_date, "Disposal date") if disposal_date else date.today()
    if disp < acq:
        raise EngineError("Disposal date cannot be before acquisition date.")
    atl = _on_atl(on_atl)
    notes = []
    if pmex_futures:
        rate, why = 5, "Future commodity contracts by PMEX members: 5%"
    elif acq >= _CUTOFF:
        rate, why = 15, "Acquired on/after 1 July 2024: 15%"
        if not atl:
            notes.append("Not on the ATL on the dates of acquisition and disposal: slab rates apply with a "
                         "minimum of 15% for individuals/AOPs; this shows the minimum.")
    elif acq >= date(2022, 7, 1):
        rate = [15, 12.5, 10, 7.5, 5, 2.5, 0][min(_holding_band(acq, disp), 7) - 1]
        why = f"Acquired 1 Jul 2022 – 30 Jun 2024, held {_holding_years(acq, disp)} years: {rate}%"
    elif acq >= date(2013, 7, 1):
        rate, why = 12.5, "Acquired 1 Jul 2013 – 30 Jun 2022: 12.5%"
    else:
        rate, why = 0, "Acquired before 1 July 2013: 0%"
    tax = round(g * rate / 100)
    notes.append("Mutual fund / REIT redemptions are taxed by the fund at 15% (25% for companies in non-stock "
                 "funds); debt securities of companies follow Division II.")
    return _out({"rate_percent": rate, "cgt": tax}, [why, f"{rate}% × {_rs(g)} = {_rs(tax)}"],
                ["s.37A", "Division VII of Part I of the First Schedule"],
                {"type": "separate block",
                 "why": "Gain on securities is taxed under s.37A at Division VII rates, usually collected by NCCPL."},
                notes, "cgt", tax_year=_tax_year_of(disp))


# ═════════════════════ 6. property advance tax — 236C / 236K ═════════════════════
def property_advance_tax(side, amount, on_atl=True, tax_year=CURRENT_TAX_YEAR,
                         same_year_sale=False, overseas_fcva=False):
    if _year_end(tax_year) != 2027:
        raise EngineError("Property advance-tax rates are only stored for tax year 2026-2027.")
    amt = _num(amount, "Amount", allow_zero=False)
    atl = _on_atl(on_atl)
    if side == "sale":
        rate = 2.75 if atl else 11.5
        law = ["s.236C", "Division X of Part IV of the First Schedule"] + ([] if atl else ["Tenth Schedule, rule 1"])
        base = "gross amount of consideration received"
        nature = {"type": "adjustable", "why": "s.236C(2): adjustable against the seller's tax for the year (CGT)."}
        if same_year_sale:
            nature = {"type": "minimum", "why": "s.236C(2) proviso: property bought and sold in the same tax year → minimum tax."}
        if overseas_fcva:
            nature = {"type": "final", "why": "s.236C(1) proviso: non-resident with POC/NICOP/CNIC who bought through "
                                              "FCVA/NRVA — final discharge in lieu of CGT."}
    elif side == "purchase":
        if atl:
            rate = 1.25
        else:
            rate = 10.5 if amt <= 50e6 else (14.5 if amt <= 100e6 else 18.5)
        law = ["s.236K", "Division XVIII of Part IV of the First Schedule"] + ([] if atl else ["Tenth Schedule, rule 1, proviso"])
        base = "fair market value"
        nature = {"type": "adjustable", "why": "s.236K(2): adjustable against the buyer's tax for the year."}
        if overseas_fcva:
            nature = {"type": "final", "why": "s.236K(2) proviso: non-resident with POC/NICOP/CNIC buying through "
                                              "FCVA/NRVA — final discharge."}
    else:
        raise EngineError("side must be sale (236C) or purchase (236K).")
    tax = round(amt * rate / 100)
    return _out({"rate_percent": rate, "advance_tax": tax},
                [f"{rate}% of {base} {_rs(amt)} = {_rs(tax)} ({'on ATL' if atl else 'not on ATL'})"],
                law, nature,
                ["Fair market value is the higher of the FBR valuation table (s.68) and the DC/stamp-duty value."],
                "property", tax_year="2026-2027")


# ═════════════════════ 7. motor vehicles — 231B / 234 ═════════════════════
_CC = [850, 1000, 1300, 1600, 1800, 2000, 2500, 3000, None]
_REG_PCT = [0.5, 1, 1.5, 2, 3, 5, 7, 9, 12]                              # 231B(1)/(3), % of value
_TRANSFER = [0, 5000, 7500, 12500, 18750, 25000, 37500, 50000, 62500]    # 231B(2), Rs
_TOKEN_CC = [1000, 1199, 1299, 1499, 1599, 1999, None]
_TOKEN = [800, 1500, 1750, 2500, 3750, 4500, 10000]                       # 234, annual Rs
_TOKEN_LUMP = [10000, 18000, 20000, 30000, 45000, 60000, 120000]          # 234, lump sum Rs


def _band(limits, cc):
    for i, hi in enumerate(limits):
        if hi is None or cc <= hi:
            return i
    return len(limits) - 1


def vehicle_tax(kind, engine_cc, value=0, on_atl=True, years_since_first_registration=0,
                tax_year=CURRENT_TAX_YEAR):
    if _year_end(tax_year) != 2027:
        raise EngineError("Vehicle rates are only stored for tax year 2026-2027.")
    cc = _num(engine_cc, "Engine capacity (cc)", allow_zero=False)
    atl = _on_atl(on_atl)
    status = "on ATL" if atl else "not on ATL"
    if kind == "registration":
        val = _num(value, "Vehicle value", allow_zero=False)
        rate = _REG_PCT[_band(_CC, cc)] * (1 if atl else 3)
        tax = round(val * rate / 100)
        return _out({"rate_percent": rate, "advance_tax": tax},
                    [f"{int(cc)}cc → {rate:g}% of value ({status}) × {_rs(val)} = {_rs(tax)}"],
                    ["s.231B(1)/(3)", "Division VII of Part IV of the First Schedule"] + ([] if atl else ["Tenth Schedule, rule 1, proviso (+200%)"]),
                    {"type": "adjustable", "why": "s.231B(5): adjustable against tax for the year."},
                    ["Value = invoice value incl. duties (local), customs value + duties/taxes (imported) or auction value.",
                     "No collection after five years from first registration."], "vehicle")
    if kind == "transfer":
        yrs = int(_num(years_since_first_registration or 0, "Years since first registration"))
        base = _TRANSFER[_band(_CC, cc)] * (1 if atl else 3)
        working = [f"{int(cc)}cc → {_rs(base)} ({status})"]
        if base and yrs >= 5:
            tax = 0
            working.append("More than five years since first registration → nil")
        else:
            tax = round(base * (1 - 0.10 * yrs))
            if yrs:
                working.append(f"Reduced 10% per year × {yrs} → {_rs(tax)}")
        return _out({"advance_tax": tax}, working,
                    ["s.231B(2)", "Division VII(2) of Part IV of the First Schedule"],
                    {"type": "adjustable", "why": "s.231B(5): adjustable against tax for the year."},
                    ["Nil up to 850cc."], "vehicle")
    if kind in ("token", "token_lump_sum"):
        i = _band(_TOKEN_CC, cc)
        base = (_TOKEN if kind == "token" else _TOKEN_LUMP)[i]
        tax = base * (1 if atl else 2)
        return _out({"advance_tax": tax, "period": "per year" if kind == "token" else "lump sum"},
                    [f"{int(cc)}cc → {_rs(base)}{'' if atl else ' × 2 (not on ATL)'} = {_rs(tax)}"],
                    ["s.234", "Division III(3)/(4) of Part IV of the First Schedule"] + ([] if atl else ["Tenth Schedule, rule 1 (+100%)"]),
                    {"type": "adjustable", "why": "s.234(5): adjustable against tax for the year."},
                    ["Not collected for cars used more than 10 years in Pakistan (s.234(2A))."], "vehicle")
    raise EngineError("kind must be registration, transfer, token or token_lump_sum.")


# ═════════════════════ 8. Karachi FBR fair market value ═════════════════════
def karachi_fmv(area, property_type, plot_size=0, plot_size_unit="sqyd", covered_area=0,
                covered_area_unit="sqft", construction_year=None, **extra):
    from .fmv_engine import FMVError, calculate_fmv
    from .models import PropertyFMVRateVersion
    version = (PropertyFMVRateVersion.objects.filter(city="Karachi", status="active", is_active=True)
               .order_by("-effective_from").first())
    if not version:
        raise EngineError("The Karachi FMV table is not loaded.")
    name = str(area or "").strip()
    qs = version.areas.filter(area_name__iexact=name) or version.areas.filter(area_name__icontains=name)
    matches = list(qs[:6])
    if not matches:
        raise EngineError(f"No Karachi area matching '{name}'. Ask the user for the exact society/area name.")
    if len(matches) > 1 and not any(m.area_name.lower() == name.lower() for m in matches):
        return {"choose_area": [m.area_name for m in matches],
                "message": "Several areas match. Ask the user which one."}
    a = next((m for m in matches if m.area_name.lower() == name.lower()), matches[0])
    payload = {"property_type": property_type, "plot_size": plot_size, "plot_size_unit": plot_size_unit,
               "ground_covered": extra.get("ground_covered") or covered_area,
               "ground_covered_unit": covered_area_unit, "covered_area": covered_area,
               "covered_area_unit": covered_area_unit, "construction_year": construction_year,
               "additional_qualifying_storeys": extra.get("additional_storeys") or 0,
               "special_category": extra.get("special_category"),
               "dha_khayaban": bool(extra.get("dha_khayaban")) and a.is_dha, "purposes": []}
    try:
        r = calculate_fmv(payload, a.rates_dict())
    except FMVError as e:
        raise EngineError(str(e))
    fmv = int(r["final_fmv"])
    return _out({"fmv": fmv, "area": a.area_name},
                [f"{s['label']}: {s['detail']}" for s in r.get("calculation_steps", [])],
                ["s.68(4) (FBR valuation)", version.legal_basis or r.get("notification", "")],
                {"type": "valuation", "why": "FMV is the base for 236K (purchase), 236C and CGT consideration (s.77)."},
                ["FMV for tax is the higher of this FBR value and the DC/stamp-duty value."] +
                (["This area is flagged in the FBR table — verify the rate."] if a.is_flagged else []),
                "fmv", available_types=a.available_types())


# ═════════════════════ tool registry (for agent_tools) ═════════════════════
FUNCTIONS = {
    "calculate_income_tax": income_tax,
    "calculate_super_tax": super_tax_4c,
    "calculate_advance_tax_147": advance_tax_147,
    "calculate_cgt_property": cgt_property,
    "calculate_cgt_securities": cgt_securities,
    "calculate_property_advance_tax": property_advance_tax,
    "calculate_vehicle_tax": vehicle_tax,
    "calculate_karachi_fmv": karachi_fmv,
}

_DATE = {"type": "string", "description": "YYYY-MM-DD"}
_ATL = {"type": "boolean", "description": "true if on the Active Taxpayers List (filer). Default true."}
_TY = {"type": "string", "description": "e.g. 2026-2027 (default)"}

SCHEMAS = [
    {"name": "calculate_income_tax",
     "description": "Annual income tax on slab rates for salary, business individual, AOP or rental income, with the s.63 VPS pension credit and s.4AB surcharge. Returns working, law and tax nature.",
     "input_schema": {"type": "object", "properties": {
         "income_type": {"type": "string", "enum": ["salary", "business", "aop", "rental"]},
         "annual_taxable_income": {"type": "number", "description": "Yearly PKR. Multiply monthly by 12."},
         "tax_year": _TY,
         "vps_contribution": {"type": "number", "description": "Yearly VPS pension contribution, if any (individuals)."}},
         "required": ["income_type", "annual_taxable_income"]}},
    {"name": "calculate_super_tax",
     "description": "Super tax under s.4C on high earning persons.",
     "input_schema": {"type": "object", "properties": {
         "income_under_4c": {"type": "number"}, "tax_year": _TY,
         "person": {"type": "string", "enum": ["other", "banking", "petroleum_fifth_schedule", "fertilizer"]}},
         "required": ["income_under_4c"]}},
    {"name": "calculate_advance_tax_147",
     "description": "Quarterly advance tax under s.147 for an individual (A/4 − B), company or AOP ((A×B/C) − D), or capital gain on securities (s.147(5B)).",
     "input_schema": {"type": "object", "properties": {
         "taxpayer": {"type": "string", "enum": ["individual", "company", "aop", "securities"]},
         "quarter": {"type": "string", "enum": ["sep", "dec", "mar", "jun"]},
         "latest_assessed_income": {"type": "number", "description": "Individuals: latest assessed taxable income"},
         "latest_tax_assessed": {"type": "number"},
         "quarter_credit": {"type": "number", "description": "Tax credited under s.168 in the quarter (not s.149)"},
         "quarter_turnover": {"type": "number"}, "latest_year_turnover": {"type": "number"},
         "tax_4c": {"type": "number"}, "tax_113": {"type": "number"}, "tax_113c": {"type": "number"},
         "capital_gain": {"type": "number"},
         "holding": {"type": "string", "enum": ["lt6", "6to12"]}},
         "required": ["taxpayer"]}},
    {"name": "calculate_cgt_property",
     "description": "Capital gains tax on sale of immovable property (s.37(1A), Division VIII): holding-period table for property acquired up to 30 June 2024, 15% after. Handles s.75A cash purchase and clause 9A allottee relief.",
     "input_schema": {"type": "object", "properties": {
         "property_type": {"type": "string", "enum": ["plot", "constructed", "flat"]},
         "acquisition_date": _DATE, "disposal_date": _DATE,
         "sale_price": {"type": "number"}, "fmv": {"type": "number", "description": "FBR/DC value at sale, if known"},
         "cost": {"type": "number"}, "expenses": {"type": "number"}, "on_atl": _ATL,
         "cash_purchase": {"type": "boolean"}, "forces_or_govt_allottee": {"type": "boolean"}},
         "required": ["property_type", "acquisition_date", "sale_price", "cost"]}},
    {"name": "calculate_cgt_securities",
     "description": "Capital gains tax on listed securities (s.37A, Division VII) from the gain and dates.",
     "input_schema": {"type": "object", "properties": {
         "gain": {"type": "number"}, "acquisition_date": _DATE, "disposal_date": _DATE,
         "on_atl": _ATL, "pmex_futures": {"type": "boolean"}},
         "required": ["gain", "acquisition_date"]}},
    {"name": "calculate_property_advance_tax",
     "description": "Advance tax on property: side=sale → s.236C on gross consideration; side=purchase → s.236K on fair market value. Tax year 2026-27.",
     "input_schema": {"type": "object", "properties": {
         "side": {"type": "string", "enum": ["sale", "purchase"]},
         "amount": {"type": "number"}, "on_atl": _ATL,
         "same_year_sale": {"type": "boolean", "description": "Bought and sold in the same tax year"},
         "overseas_fcva": {"type": "boolean", "description": "Non-resident POC/NICOP who paid via FCVA/NRVA"}},
         "required": ["side", "amount"]}},
    {"name": "calculate_vehicle_tax",
     "description": "Motor vehicle advance tax: registration (s.231B, % of value), transfer (s.231B(2)), annual token tax or lump sum (s.234). Tax year 2026-27.",
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": ["registration", "transfer", "token", "token_lump_sum"]},
         "engine_cc": {"type": "number"}, "value": {"type": "number", "description": "Registration only"},
         "on_atl": _ATL, "years_since_first_registration": {"type": "integer"}},
         "required": ["kind", "engine_cc"]}},
    {"name": "calculate_karachi_fmv",
     "description": "FBR fair market value of a Karachi property from the FBR valuation table.",
     "input_schema": {"type": "object", "properties": {
         "area": {"type": "string", "description": "Society/area name, e.g. 'DHA Phase VI'"},
         "property_type": {"type": "string", "enum": ["residential_open", "residential_builtup", "flat",
                                                       "commercial_open", "commercial_builtup",
                                                       "industrial_open", "industrial_builtup", "amenity"]},
         "plot_size": {"type": "number"}, "plot_size_unit": {"type": "string", "enum": ["sqyd", "sqft", "marla", "kanal", "acre"]},
         "covered_area": {"type": "number"}, "covered_area_unit": {"type": "string", "enum": ["sqft", "sqyd"]},
         "construction_year": {"type": "integer"}},
         "required": ["area", "property_type"]}},
]


def run(name, args):
    """Run one engine tool. Bad input comes back as {'error': ...}, never an exception."""
    fn = FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return fn(**(args or {}))
    except EngineError as e:
        return {"error": str(e)}
    except TypeError as e:
        return {"error": f"Bad arguments: {e}"}
