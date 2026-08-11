# -*- coding: utf-8 -*-
"""
Karachi FMV engine tests.  Run:  python manage.py test TaxBuddyApp.tests_fmv
Place this file at TaxBuddyApp/tests_fmv.py
"""
from datetime import date
from decimal import Decimal
from django.test import TestCase

from .fmv_engine import calculate_fmv, FMVError

AS_OF = date(2026, 1, 1)
D = lambda x: Decimal(str(x))

AHR = dict(residential_open=D(5000), residential_builtup=D(7000),
           commercial_open=D(20000), commercial_builtup=D(12000),
           flats=D(6200), industrial_open=D(1350), industrial_builtup=D(3150))
NORE = dict(residential_open=D(8200), residential_builtup=D(10200),
            commercial_open=D(20000), commercial_builtup=D(12000),
            flats=D(7350), industrial_open=None, industrial_builtup=None)


class FMVEngineTests(TestCase):
    def _fmv(self, payload, rates=AHR):
        return int(calculate_fmv(payload, rates, as_of=AS_OF)['final_fmv'])

    def test_01_residential_open(self):
        self.assertEqual(self._fmv(dict(property_type='residential_open',
            plot_size=120, plot_size_unit='sqyd')), 5_400_000)

    def test_02_residential_builtup_new(self):
        self.assertEqual(self._fmv(dict(property_type='residential_builtup',
            ground_covered=1500, construction_year=2025)), 10_500_000)

    def test_03_res_builtup_age_5_10(self):
        self.assertEqual(self._fmv(dict(property_type='residential_builtup',
            ground_covered=1500, construction_year=2018)), 9_975_000)

    def test_04_res_builtup_age_10_15(self):
        self.assertEqual(self._fmv(dict(property_type='residential_builtup',
            ground_covered=1500, construction_year=2013)), 9_712_500)

    def test_05_res_builtup_over_25_open_plot(self):
        self.assertEqual(self._fmv(dict(property_type='residential_builtup',
            ground_covered=1500, construction_year=1990,
            plot_size=240, plot_size_unit='sqyd')), 10_800_000)

    def test_06_flat_new(self):
        self.assertEqual(self._fmv(dict(property_type='flat',
            covered_area=1200, construction_year=2024)), 7_440_000)

    def test_07_flat_10_20(self):
        self.assertEqual(self._fmv(dict(property_type='flat',
            covered_area=1200, construction_year=2012)), 5_952_000)

    def test_08_flat_over_30(self):
        self.assertEqual(self._fmv(dict(property_type='flat',
            covered_area=1200, construction_year=1990)), 3_720_000)

    def test_09_commercial_open(self):
        self.assertEqual(self._fmv(dict(property_type='commercial_open',
            plot_size=200, plot_size_unit='sqyd')), 36_000_000)

    def test_10_commercial_open_dha_khayaban(self):
        self.assertEqual(self._fmv(dict(property_type='commercial_open',
            plot_size=200, plot_size_unit='sqyd', dha_khayaban=True)), 41_400_000)

    def test_11_commercial_builtup(self):
        self.assertEqual(self._fmv(dict(property_type='commercial_builtup',
            ground_covered=1000, construction_year=2025)), 12_000_000)

    def test_12_commercial_basement(self):
        self.assertEqual(self._fmv(dict(property_type='commercial_builtup',
            ground_covered=1000, basement_area=500, construction_year=2025)), 13_200_000)

    def test_13_commercial_additional_floor(self):
        self.assertEqual(self._fmv(dict(property_type='commercial_builtup',
            ground_covered=1000, additional_covered=1000, construction_year=2025)), 21_000_000)

    def test_14_industrial_open(self):
        self.assertEqual(self._fmv(dict(property_type='industrial_open',
            plot_size=300, plot_size_unit='sqyd')), 3_645_000)

    def test_15_industrial_builtup(self):
        self.assertEqual(self._fmv(dict(property_type='industrial_builtup',
            plot_size=300, plot_size_unit='sqyd', covered_area=1000)), 11_655_000)

    def test_16_amenity(self):
        self.assertEqual(self._fmv(dict(property_type='amenity',
            plot_size=100, plot_size_unit='sqyd')), 2_250_000)

    def test_17_special_category_20pc(self):
        self.assertEqual(self._fmv(dict(property_type='residential_open',
            plot_size=120, plot_size_unit='sqyd', special_category='Nala-facing')), 4_320_000)

    def test_18_na_rate_raises(self):
        with self.assertRaises(FMVError):
            calculate_fmv(dict(property_type='industrial_builtup', plot_size=100,
                               covered_area=100), NORE, as_of=AS_OF)

    def test_19_mixed_purpose_mean(self):
        self.assertEqual(self._fmv(dict(property_type='mixed', plot_size=120,
            plot_size_unit='sqyd',
            purposes=['residential_open', 'commercial_open', 'industrial_open'])), 9_486_000)

    def test_20_multi_storey(self):
        r = calculate_fmv(dict(property_type='residential_builtup', ground_covered=1500,
            construction_year=2025, additional_qualifying_storeys=2), AHR, as_of=AS_OF)
        self.assertEqual(int(r['final_fmv']), 15_750_000)
        self.assertFalse(r['is_high_rise'])

    def test_21_high_rise_flag(self):
        r = calculate_fmv(dict(property_type='residential_builtup', ground_covered=1000,
            construction_year=2025, additional_qualifying_storeys=5), AHR, as_of=AS_OF)
        self.assertTrue(r['is_high_rise'])
