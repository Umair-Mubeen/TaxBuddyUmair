# -*- coding: utf-8 -*-
"""
Seed the Karachi FMV rate version, its 235 area rates, and the SRO 144
rules layer.

    python manage.py seed_karachi_fmv          # create / refresh
    python manage.py seed_karachi_fmv --reset  # delete this version first

Idempotent: re-running clears and recreates the SRO-1724 version's areas
and rules so the DB always matches the transcribed source of truth.
Rate data lives in the sibling module `_karachi_fmv_data.py`.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from TaxBuddyApp.models import (
    PropertyFMVRateVersion, PropertyFMVArea, PropertyFMVRule,
)
from ._karachi_fmv_data import ROWS, FLAGGED_AMBIGUOUS

VERSION_NAME = 'Karachi 2024-25 (SRO 1724)'
COLS = ['residential_open', 'residential_builtup', 'commercial_open',
        'commercial_builtup', 'flats', 'industrial_open', 'industrial_builtup']
COL_TO_FIELD = {
    'residential_open': 'residential_open_rate',
    'residential_builtup': 'residential_builtup_rate',
    'commercial_open': 'commercial_open_rate',
    'commercial_builtup': 'commercial_builtup_rate',
    'flats': 'flat_rate',
    'industrial_open': 'industrial_open_rate',
    'industrial_builtup': 'industrial_builtup_rate',
}

DHA_TOKENS = ('defence housing authority', 'dha', 'dohs', 'defence officers',
              'naval housing', 'creek vista', 'emaar defence')


def is_dha_area(name):
    n = name.lower()
    return any(tok in n for tok in DHA_TOKENS)


# SRO 144(I)/2025 rules, made visible/editable in admin.
RULES = [
    # code, ptype, name, min_age, max_age, adj_type, pct, description
    ('c', 'amenity', 'Amenity plot = 50% of residential', None, None, 'factor_pct', 50,
     'Value of amenity plots taken at 50% of the residential open-plot rate of the area.'),
    ('r', 'residential_open', 'Special-category plot reduction', None, None, 'reduction_pct', 20,
     'Residential plot value reduced by 20% if nala-facing, commercial-facing, facing a '
     'school/mosque/graveyard, or a rear/triangular plot. Applied once (not stacked).'),
    ('m', 'residential_builtup', 'Age 5-10 years', 5, 10, 'reduction_pct', 5, 'Built-up residential depreciation.'),
    ('m', 'residential_builtup', 'Age 10-15 years', 10, 15, 'reduction_pct', Decimal('7.5'), 'Built-up residential depreciation.'),
    ('m', 'residential_builtup', 'Age 15-25 years', 15, 25, 'reduction_pct', 10, 'Built-up residential depreciation.'),
    ('m', 'residential_builtup', 'Age over 25 years', 25, None, 'set_open_plot', None,
     'Beyond 25 years the value is taken equal to the open-plot value of the area.'),
    ('f', 'residential_builtup', 'Additional storey', None, None, 'factor_pct', 25,
     'Each additional qualifying storey (with bedroom + bathroom) valued at 25% of the ground-floor value.'),
    ('n', 'flat', 'Age 5-10 years', 5, 10, 'reduction_pct', 10, 'Flat/apartment depreciation.'),
    ('n', 'flat', 'Age 10-20 years', 10, 20, 'reduction_pct', 20, 'Flat/apartment depreciation.'),
    ('n', 'flat', 'Age 20-30 years', 20, 30, 'reduction_pct', 30, 'Flat/apartment depreciation.'),
    ('n', 'flat', 'Age over 30 years', 30, None, 'reduction_pct', 50, 'Flat/apartment depreciation.'),
    ('o', 'commercial_builtup', 'Age 10-15 years', 10, 15, 'reduction_pct', 5, 'Built-up commercial depreciation.'),
    ('o', 'commercial_builtup', 'Age 15-25 years', 15, 25, 'reduction_pct', 8, 'Built-up commercial depreciation.'),
    ('o', 'commercial_builtup', 'Age over 25 years', 25, None, 'reduction_pct', 10, 'Built-up commercial depreciation.'),
    ('k', 'commercial_builtup', 'Basement', None, None, 'factor_pct', 20,
     'Basement of a built-up commercial property valued at 20% of ground-floor value.'),
    ('q', 'commercial_builtup', 'Floors above ground', None, None, 'factor_pct', 75,
     'Built-up commercial value excluding ground floor reduced by 25% (i.e. 75% of ground rate).'),
    ('p', 'commercial_open', 'DHA Khayaban-facing', None, None, 'increase_pct', 15,
     'Commercial plots of DHA facing any Khayaban increased by 15%.'),
    ('e', 'industrial_builtup', 'Built-up industrial base', None, None, 'note', None,
     'Value = rate per sq.ft applied to (entire plot area + covered area).'),
    ('h', 'mixed', 'Mixed purpose', None, None, 'note', None,
     'Land used for more than one purpose valued at the mean of the applicable prescribed rates.'),
    ('l', 'all', 'High-rise definition', None, None, 'note', None,
     'A high-rise is a building with storeys above ground plus five (G+5).'),
]


class Command(BaseCommand):
    help = 'Seed Karachi FMV rate version, area rates, and SRO 144 rules.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete the existing SRO-1724 version before seeding.')

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts['reset']:
            deleted, _ = PropertyFMVRateVersion.objects.filter(version_name=VERSION_NAME).delete()
            self.stdout.write(f'Reset: removed old version ({deleted} rows).')

        # mark any other active Karachi versions superseded
        PropertyFMVRateVersion.objects.filter(city='Karachi', status='active')\
            .exclude(version_name=VERSION_NAME).update(status='superseded', is_active=False)

        version, created = PropertyFMVRateVersion.objects.update_or_create(
            version_name=VERSION_NAME,
            defaults=dict(
                city='Karachi',
                notification_number='S.R.O. 1724(I)/2024',
                amendment_number='S.R.O. 144(I)/2025',
                notification_date=date(2024, 10, 29),
                effective_from=date(2024, 11, 1),
                effective_to=None,
                status='active',
                is_active=True,
                notes='Transcribed from the FBR Karachi valuation table. '
                      'Rows flagged is_flagged have an ambiguous source column mapping.',
            ),
        )
        self.stdout.write(('Created' if created else 'Updated') + f' version: {version.version_name}')

        # rebuild areas
        version.areas.all().delete()
        area_objs, flagged = [], 0
        for row in ROWS:
            fbr_no, name = row[0], row[1]
            values = dict(zip(COLS, row[2:]))
            markers, kwargs = {}, {}
            for col, raw in values.items():
                field = COL_TO_FIELD[col]
                if raw is None:
                    kwargs[field] = None
                    markers[field] = 'blank'
                elif raw == 'NA':
                    kwargs[field] = None
                    markers[field] = 'na'
                else:
                    kwargs[field] = Decimal(str(raw))
            flag = fbr_no in FLAGGED_AMBIGUOUS
            flagged += 1 if flag else 0
            area_objs.append(PropertyFMVArea(
                version=version, fbr_no=fbr_no, city='Karachi', area_name=name,
                rate_markers={k: v for k, v in markers.items() if v != 'value'},
                is_flagged=flag, is_dha=is_dha_area(name), **kwargs,
            ))
        PropertyFMVArea.objects.bulk_create(area_objs, batch_size=500)
        self.stdout.write(self.style.SUCCESS(
            f'  Seeded {len(area_objs)} areas ({flagged} flagged ambiguous, '
            f'{sum(1 for a in area_objs if a.is_dha)} DHA-tagged).'))

        # rebuild rules
        version.rules.all().delete()
        rule_objs = []
        for i, (code, ptype, rname, mn, mx, atype, pct, desc) in enumerate(RULES):
            rule_objs.append(PropertyFMVRule(
                version=version, rule_code=code, property_type=ptype, rule_name=rname,
                min_age=mn, max_age=mx, adjustment_type=atype,
                adjustment_percentage=(Decimal(str(pct)) if pct is not None else None),
                description=desc, effective_from=date(2025, 2, 11), is_active=True, sort_order=i,
            ))
        PropertyFMVRule.objects.bulk_create(rule_objs)
        self.stdout.write(self.style.SUCCESS(f'  Seeded {len(rule_objs)} rules.'))
        self.stdout.write(self.style.SUCCESS('Done. Active version is ready.'))
