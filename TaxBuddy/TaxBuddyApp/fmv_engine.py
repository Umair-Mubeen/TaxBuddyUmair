# -*- coding: utf-8 -*-
"""
Karachi FBR Fair Market Value — calculation engine.

Pure-Python + Decimal. No Django imports here so the engine is
deterministic and unit-testable in isolation. The Django view builds
`area_rates` from PropertyFMVArea and (optionally) a RuleSet from
PropertyFMVRule, then calls calculate_fmv().

Legal basis: FBR S.R.O. 1724(I)/2024 (rate table, eff. 01-Nov-2024)
as amended by S.R.O. 144(I)/2025 (valuation rules, 11-Feb-2025).

All monetary math uses Decimal. Values are per square foot unless a
rule states otherwise.
"""

from decimal import Decimal, ROUND_HALF_UP, getcontext
from datetime import date

getcontext().prec = 28

D = lambda x: Decimal(str(x))
ZERO = Decimal('0')

# ── unit conversion ─────────────────────────────────────────────
SQYD_TO_SQFT = D(9)          # 1 sq. yard = 9 sq. ft (Karachi)
MARLA_TO_SQFT = D(225)       # 1 Marla = 25 sq.yd = 225 sq.ft  (configurable — see FLAGS)

UNIT_FACTORS = {
    'sqft':  D(1),
    'sqyd':  SQYD_TO_SQFT,
    'marla': MARLA_TO_SQFT,
}

# ── default rules (mirror S.R.O. 144(I)/2025) ───────────────────
# Age bands: (max_age_inclusive, action). Ordered ascending.
#   age <= max_age  ->  action applies (first match wins).
#   'OPEN_PLOT' = value replaced by open-plot valuation.
RES_BUILTUP_AGE = [(5, '0'), (10, '5'), (15, '7.5'), (25, '10'), (None, 'OPEN_PLOT')]   # rule (m)
FLAT_AGE        = [(5, '0'), (10, '10'), (20, '20'), (30, '30'), (None, '50')]           # rule (n)
COMM_BUILTUP_AGE = [(10, '0'), (15, '5'), (25, '8'), (None, '10')]                       # rule (o)

SPECIAL_RES_PLOT_REDUCTION = D(20)   # rule (r): nala/commercial/school/mosque/graveyard/rear/triangle
AMENITY_FACTOR             = D(50)   # rule (c): 50% of residential plot rate
DHA_KHAYABAN_INCREASE      = D(15)   # rule (p)
COMM_BASEMENT_FACTOR       = D(20)   # rule (k): 20% of ground-floor value
COMM_ADDL_FLOOR_FACTOR     = D(75)   # rule (q): excluding ground floor -> -25%  => 75%
RES_ADDL_STOREY_FACTOR     = D(25)   # rule (f): each addl storey = 25% of ground-floor value
HIGH_RISE_MIN_STOREYS      = 6       # rule (l): "above ground plus five" (G+5)

NOTIFICATION_LINE = ("Valuation based on FBR S.R.O. 1724(I)/2024 dated 29 October 2024, "
                     "as amended by S.R.O. 144(I)/2025 dated 11 February 2025.")


# ── helpers ─────────────────────────────────────────────────────
def to_sqft(size, unit):
    factor = UNIT_FACTORS.get(unit)
    if factor is None:
        raise ValueError(f"Unknown unit '{unit}'")
    return D(size) * factor


def money(x):
    """Round a rupee amount to whole rupees (final presentation only)."""
    return D(x).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def building_age(construction_year, as_of=None):
    if construction_year in (None, '', 0):
        return None
    ref = (as_of or date.today()).year
    return max(0, ref - int(construction_year))


def age_action(age, bands):
    """Return the action string for an age against ordered bands."""
    if age is None:
        return '0'
    for max_age, action in bands:
        if max_age is None or age <= max_age:
            return action
    return bands[-1][1]


class FMVError(ValueError):
    pass


def _need(rate, label):
    if rate is None:
        raise FMVError(
            f"Rate not available for '{label}' in this area under the current FBR "
            f"notification. Cannot value this property type here. (Per FBR rule (g), a "
            f"property not falling in any listed category is deemed to fall in the adjacent "
            f"highest category — confirm the correct category with FBR for this transaction.)"
        )
    return D(rate)


# ── main entry ──────────────────────────────────────────────────
def calculate_fmv(payload, area_rates, as_of=None, ruleset=None):
    """
    payload      : dict of user inputs (see each property type below)
    area_rates   : dict with keys residential_open, residential_builtup,
                   commercial_open, commercial_builtup, flats,
                   industrial_open, industrial_builtup  (Decimal or None)
    Returns a structured, JSON-serialisable dict.
    """
    ptype = payload.get('property_type')
    handler = _HANDLERS.get(ptype)
    if handler is None:
        raise FMVError(f"Unknown property_type '{ptype}'")

    steps = []
    adjustments = []
    result = handler(payload, area_rates, steps, adjustments, as_of)

    result.update({
        'property_type': ptype,
        'adjustments': adjustments,
        'calculation_steps': steps,
        'notification': NOTIFICATION_LINE,
        'final_fmv': money(result['final_fmv']),
        'final_fmv_display': f"Rs. {money(result['final_fmv']):,}",
    })
    return result


# ── size normaliser ─────────────────────────────────────────────
def _norm_size(payload, key, steps, label):
    size = payload.get(key)
    unit = payload.get(key + '_unit', 'sqft')
    if size in (None, ''):
        raise FMVError(f"{label} is required.")
    sqft = to_sqft(size, unit)
    if unit != 'sqft':
        steps.append({'label': f"{label} conversion",
                      'detail': f"{D(size):,} {unit} × {UNIT_FACTORS[unit]} = {sqft:,} sq.ft"})
    return sqft


# ── RESIDENTIAL OPEN PLOT ───────────────────────────────────────
def _residential_open(payload, rates, steps, adj, as_of):
    rate = _need(rates.get('residential_open'), 'Residential Open Plot')
    area = _norm_size(payload, 'plot_size', steps, 'Plot size')
    base = rate * area
    steps.append({'label': 'Base value', 'detail': f"{area:,} sq.ft × Rs.{rate:,} = Rs.{money(base):,}"})

    final = base
    # rule (r) — single 20% special-category reduction (never stacked)
    if payload.get('special_category'):
        cut = base * SPECIAL_RES_PLOT_REDUCTION / D(100)
        final = base - cut
        adj.append({'label': f"Special plot category ({payload.get('special_category')})",
                    'type': 'reduction', 'percent': str(SPECIAL_RES_PLOT_REDUCTION),
                    'amount': f"-{money(cut):,}"})
        steps.append({'label': 'Special-category reduction (rule r)',
                      'detail': f"-20% (applied once) = -Rs.{money(cut):,}"})

    return {'rate': str(rate), 'area_sqft': str(area), 'base_value': money(base),
            'final_fmv': final}


# ── AMENITY PLOT (rule c) ───────────────────────────────────────
def _amenity(payload, rates, steps, adj, as_of):
    res = _need(rates.get('residential_open'), 'Residential Open Plot (for amenity)')
    rate = res * AMENITY_FACTOR / D(100)
    area = _norm_size(payload, 'plot_size', steps, 'Plot size')
    steps.append({'label': 'Amenity rate (rule c)',
                  'detail': f"50% of residential open rate Rs.{res:,} = Rs.{rate:,}/sq.ft"})
    base = rate * area
    steps.append({'label': 'Base value', 'detail': f"{area:,} sq.ft × Rs.{rate:,} = Rs.{money(base):,}"})
    return {'rate': str(rate), 'area_sqft': str(area), 'base_value': money(base),
            'final_fmv': base}


# ── RESIDENTIAL BUILT-UP ────────────────────────────────────────
def _residential_builtup(payload, rates, steps, adj, as_of):
    rate = _need(rates.get('residential_builtup'), 'Residential Built-up')
    ground = _norm_size(payload, 'ground_covered', steps, 'Ground-floor covered area')
    ground_val = rate * ground
    steps.append({'label': 'Ground floor', 'detail': f"{ground:,} sq.ft × Rs.{rate:,} = Rs.{money(ground_val):,}"})

    age = building_age(payload.get('construction_year'), as_of)

    # >25 years -> value equal to OPEN PLOT (rule m, last band)
    action = age_action(age, RES_BUILTUP_AGE)
    if action == 'OPEN_PLOT':
        open_rate = _need(rates.get('residential_open'), 'Residential Open Plot (age>25 fallback)')
        plot = _norm_size(payload, 'plot_size', steps, 'Plot size')
        final = open_rate * plot
        adj.append({'label': 'Age > 25 years (rule m)', 'type': 'set_to_open_plot',
                    'amount': f"= Rs.{money(final):,}"})
        steps.append({'label': 'Age > 25 years',
                      'detail': f"Value set equal to open plot: {plot:,} sq.ft × Rs.{open_rate:,} = Rs.{money(final):,}"})
        return {'rate': str(rate), 'area_sqft': str(ground), 'base_value': money(ground_val),
                'age': age, 'final_fmv': final}

    # additional storeys — each qualifying storey = 25% of ground-floor value (rule f + j)
    addl_storeys = int(payload.get('additional_qualifying_storeys', 0) or 0)
    addl_val = ZERO
    if addl_storeys > 0:
        per = ground_val * RES_ADDL_STOREY_FACTOR / D(100)
        addl_val = per * addl_storeys
        adj.append({'label': f"Additional storeys ×{addl_storeys} (rule f)", 'type': 'addition',
                    'amount': f"+{money(addl_val):,}"})
        steps.append({'label': 'Additional storeys',
                      'detail': f"{addl_storeys} × 25% of ground value (Rs.{money(per):,} each) = +Rs.{money(addl_val):,}"})

    structure = ground_val + addl_val

    # age reduction %
    final = structure
    if action not in ('0', 'OPEN_PLOT'):
        pct = D(action)
        cut = structure * pct / D(100)
        final = structure - cut
        adj.append({'label': f"Age depreciation ({age} yrs, rule m)", 'type': 'reduction',
                    'percent': action, 'amount': f"-{money(cut):,}"})
        steps.append({'label': 'Age depreciation',
                      'detail': f"-{action}% on Rs.{money(structure):,} = -Rs.{money(cut):,}"})

    total_storeys = 1 + addl_storeys
    return {'rate': str(rate), 'area_sqft': str(ground), 'base_value': money(ground_val),
            'additional_floors_value': money(addl_val), 'age': age,
            'is_high_rise': total_storeys >= HIGH_RISE_MIN_STOREYS,
            'final_fmv': final}


# ── FLATS / APARTMENTS (rule n) ─────────────────────────────────
def _flat(payload, rates, steps, adj, as_of):
    rate = _need(rates.get('flats'), 'Flats / Apartments')
    covered = _norm_size(payload, 'covered_area', steps, 'Covered area')
    base = rate * covered
    steps.append({'label': 'Base value', 'detail': f"{covered:,} sq.ft × Rs.{rate:,} = Rs.{money(base):,}"})

    age = building_age(payload.get('construction_year'), as_of)
    action = age_action(age, FLAT_AGE)
    final = base
    if action != '0':
        pct = D(action)
        cut = base * pct / D(100)
        final = base - cut
        adj.append({'label': f"Age depreciation ({age} yrs, rule n)", 'type': 'reduction',
                    'percent': action, 'amount': f"-{money(cut):,}"})
        steps.append({'label': 'Age depreciation',
                      'detail': f"-{action}% on Rs.{money(base):,} = -Rs.{money(cut):,}"})
    return {'rate': str(rate), 'area_sqft': str(covered), 'base_value': money(base),
            'age': age, 'final_fmv': final}


# ── COMMERCIAL OPEN PLOT ────────────────────────────────────────
def _commercial_open(payload, rates, steps, adj, as_of):
    rate = _need(rates.get('commercial_open'), 'Commercial Open Plot')
    area = _norm_size(payload, 'plot_size', steps, 'Plot size')
    base = rate * area
    steps.append({'label': 'Base value', 'detail': f"{area:,} sq.ft × Rs.{rate:,} = Rs.{money(base):,}"})
    final = base
    # rule (p) — DHA Khayaban +15% (gated to DHA areas by caller)
    if payload.get('dha_khayaban'):
        add = base * DHA_KHAYABAN_INCREASE / D(100)
        final = base + add
        adj.append({'label': 'DHA Khayaban-facing (rule p)', 'type': 'addition',
                    'percent': str(DHA_KHAYABAN_INCREASE), 'amount': f"+{money(add):,}"})
        steps.append({'label': 'DHA Khayaban increase', 'detail': f"+15% = +Rs.{money(add):,}"})
    return {'rate': str(rate), 'area_sqft': str(area), 'base_value': money(base),
            'final_fmv': final}


# ── COMMERCIAL BUILT-UP (rules d, k, o, q) ──────────────────────
def _commercial_builtup(payload, rates, steps, adj, as_of):
    rate = _need(rates.get('commercial_builtup'), 'Commercial Built-up')
    ground = _norm_size(payload, 'ground_covered', steps, 'Ground-floor covered area')
    ground_val = rate * ground
    steps.append({'label': 'Ground floor', 'detail': f"{ground:,} sq.ft × Rs.{rate:,} = Rs.{money(ground_val):,}"})

    # additional floors @ 75% of ground rate (rule q)
    addl = payload.get('additional_covered', 0) or 0
    addl_val = ZERO
    if addl:
        addl_sqft = _norm_size(payload, 'additional_covered', steps, 'Additional floors covered area')
        addl_rate = rate * COMM_ADDL_FLOOR_FACTOR / D(100)
        addl_val = addl_rate * addl_sqft
        adj.append({'label': 'Additional floors -25% (rule q)', 'type': 'addition',
                    'amount': f"+{money(addl_val):,}"})
        steps.append({'label': 'Additional floors',
                      'detail': f"{addl_sqft:,} sq.ft × Rs.{addl_rate:,} (75% of ground rate) = +Rs.{money(addl_val):,}"})

    # basement @ 20% of ground-floor value (rule k)
    base_area = payload.get('basement_area', 0) or 0
    basement_val = ZERO
    if base_area:
        b_sqft = _norm_size(payload, 'basement_area', steps, 'Basement area')
        b_rate = rate * COMM_BASEMENT_FACTOR / D(100)
        basement_val = b_rate * b_sqft
        adj.append({'label': 'Basement 20% of ground (rule k)', 'type': 'addition',
                    'amount': f"+{money(basement_val):,}"})
        steps.append({'label': 'Basement',
                      'detail': f"{b_sqft:,} sq.ft × Rs.{b_rate:,} (20% of ground rate) = +Rs.{money(basement_val):,}"})

    structure = ground_val + addl_val + basement_val

    # age depreciation (rule o)
    age = building_age(payload.get('construction_year'), as_of)
    action = age_action(age, COMM_BUILTUP_AGE)
    final = structure
    if action != '0':
        pct = D(action)
        cut = structure * pct / D(100)
        final = structure - cut
        adj.append({'label': f"Age depreciation ({age} yrs, rule o)", 'type': 'reduction',
                    'percent': action, 'amount': f"-{money(cut):,}"})
        steps.append({'label': 'Age depreciation',
                      'detail': f"-{action}% on Rs.{money(structure):,} = -Rs.{money(cut):,}"})

    return {'rate': str(rate), 'area_sqft': str(ground), 'base_value': money(ground_val),
            'additional_floors_value': money(addl_val), 'basement_value': money(basement_val),
            'age': age, 'final_fmv': final}


# ── INDUSTRIAL OPEN PLOT ────────────────────────────────────────
def _industrial_open(payload, rates, steps, adj, as_of):
    rate = _need(rates.get('industrial_open'), 'Industrial Open Plot')
    area = _norm_size(payload, 'plot_size', steps, 'Plot size')
    base = rate * area
    steps.append({'label': 'Base value', 'detail': f"{area:,} sq.ft × Rs.{rate:,} = Rs.{money(base):,}"})
    return {'rate': str(rate), 'area_sqft': str(area), 'base_value': money(base), 'final_fmv': base}


# ── INDUSTRIAL BUILT-UP (rule e) ────────────────────────────────
def _industrial_builtup(payload, rates, steps, adj, as_of):
    # rule (e): value per sq.ft of ENTIRE PLOT AREA + covered area of the plot
    rate = _need(rates.get('industrial_builtup'), 'Industrial Built-up')
    plot = _norm_size(payload, 'plot_size', steps, 'Entire plot area')
    covered = _norm_size(payload, 'covered_area', steps, 'Covered area')
    billable = plot + covered
    base = rate * billable
    steps.append({'label': 'Billable area (rule e)',
                  'detail': f"plot {plot:,} + covered {covered:,} = {billable:,} sq.ft"})
    steps.append({'label': 'Base value', 'detail': f"{billable:,} sq.ft × Rs.{rate:,} = Rs.{money(base):,}"})
    return {'rate': str(rate), 'area_sqft': str(billable), 'base_value': money(base), 'final_fmv': base}


# ── MIXED PURPOSE (rule h) ──────────────────────────────────────
def _mixed(payload, rates, steps, adj, as_of):
    purposes = payload.get('purposes') or []   # e.g. ['residential_open','commercial_open']
    picked = []
    for key in purposes:
        r = rates.get(key)
        if r is not None:
            picked.append((key, D(r)))
    if not picked:
        raise FMVError("Select at least one purpose with an available rate for mixed-purpose valuation.")
    mean = sum(v for _, v in picked) / D(len(picked))
    area = _norm_size(payload, 'plot_size', steps, 'Plot size')
    steps.append({'label': 'Mean rate (rule h)',
                  'detail': "avg(" + ", ".join(f"{k}=Rs.{v:,}" for k, v in picked) + f") = Rs.{money(mean):,}/sq.ft"})
    base = mean * area
    steps.append({'label': 'Base value', 'detail': f"{area:,} sq.ft × Rs.{money(mean):,} = Rs.{money(base):,}"})
    return {'rate': str(money(mean)), 'area_sqft': str(area), 'base_value': money(base), 'final_fmv': base}


_HANDLERS = {
    'residential_open':    _residential_open,
    'amenity':             _amenity,
    'residential_builtup': _residential_builtup,
    'flat':                _flat,
    'commercial_open':     _commercial_open,
    'commercial_builtup':  _commercial_builtup,
    'industrial_open':     _industrial_open,
    'industrial_builtup':  _industrial_builtup,
    'mixed':               _mixed,
}
