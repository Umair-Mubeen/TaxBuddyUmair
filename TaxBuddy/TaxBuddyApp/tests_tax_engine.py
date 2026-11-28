"""
Unit tests for tax_engine.py. Run:
    python manage.py test TaxBuddyApp.tests_tax_engine --settings=TaxBuddy.settings.local

Expected figures are worked by hand from the Income Tax Ordinance 2001
(amended to 30 June 2026). No database needed: slab tests pass their own slabs.
"""
from datetime import date

from django.test import SimpleTestCase

from . import agent_tools, tax_engine as T

# Simple 3-slab table for the slab maths tests: 0% to 600k, 5% to 1.2M, 15% above
SLABS = [(0, 600_000, 0, 0, 0), (600_001, 1_200_000, 0.05, 600_000, 0),
         (1_200_001, None, 0.15, 1_200_000, 30_000)]


class IncomeTaxTests(SimpleTestCase):
    def test_slab_and_monthly(self):
        r = T.income_tax("salary", 2_400_000, "2026-2027", slabs=SLABS)["result"]
        self.assertEqual(r["annual_tax"], 30_000 + 180_000)
        self.assertEqual(r["monthly_tax"], 17_500)

    def test_zero_slab(self):
        self.assertEqual(T.income_tax("salary", 500_000, slabs=SLABS)["result"]["annual_tax"], 0)

    def test_gap_between_slabs_uses_lower(self):
        self.assertEqual(T.income_tax("salary", 600_000.5, slabs=SLABS)["result"]["annual_tax"], 0)

    def test_vps_credit_s63(self):
        # tax 210,000 on 2.4M; contribution 600k capped at 20% = 480k; credit = 210k/2.4M x 480k = 42,000
        r = T.income_tax("salary", 2_400_000, slabs=SLABS, vps_contribution=600_000)["result"]
        self.assertEqual((r["vps_allowed"], r["vps_credit"], r["annual_tax"]), (480_000, 42_000, 168_000))

    def test_no_vps_for_aop(self):
        r = T.income_tax("aop", 2_400_000, slabs=SLABS, vps_contribution=600_000)
        self.assertEqual(r["result"]["vps_credit"], 0)

    def test_surcharge_business_not_salary_2027(self):
        biz = T.income_tax("business", 12_000_000, "2026-2027", slabs=SLABS)["result"]
        sal = T.income_tax("salary", 12_000_000, "2026-2027", slabs=SLABS)["result"]
        self.assertEqual(biz["surcharge"], round(biz["tax_before_credits"] * 0.10))
        self.assertEqual(sal["surcharge"], 0)

    def test_salary_surcharge_9pct_2026(self):
        r = T.income_tax("salary", 12_000_000, "2025-2026", slabs=SLABS)["result"]
        self.assertEqual(r["surcharge"], round(r["tax_before_credits"] * 0.09))


class SuperTaxTests(SimpleTestCase):
    def test_2027_other_persons(self):
        self.assertEqual(T.super_tax_4c(500e6, 2027)["result"]["super_tax"], 0)
        self.assertEqual(T.super_tax_4c(500_000_001, 2027)["result"]["rate_percent"], 8)

    def test_2027_bank(self):
        self.assertEqual(T.super_tax_4c(200e6, "2026-2027", "banking")["result"]["super_tax"], 20_000_000)

    def test_2026_table(self):
        self.assertEqual(T.super_tax_4c(260e6, 2026)["result"]["rate_percent"], 2.5)
        self.assertEqual(T.super_tax_4c(600e6, 2026)["result"]["rate_percent"], 10)


class AdvanceTaxTests(SimpleTestCase):
    def test_individual_below_threshold(self):
        self.assertFalse(T.advance_tax_147("individual", latest_assessed_income=999_999,
                                           latest_tax_assessed=50_000)["result"]["applicable"])

    def test_individual_formula(self):
        r = T.advance_tax_147("individual", "dec", 2_000_000, 400_000, 30_000)["result"]
        self.assertEqual((r["payable"], r["due_date"]), (70_000, "15 December"))

    def test_company_unknown_turnover(self):
        # A = 120% x 100M / 4 = 30M; (30M x 5M / 100M) - 0 = 1.5M
        r = T.advance_tax_147("company", "mar", latest_tax_assessed=5_000_000, latest_year_turnover=100_000_000)
        self.assertEqual(r["result"]["payable"], 1_500_000)
        self.assertEqual(r["result"]["due_date"], "25 March")

    def test_securities(self):
        self.assertEqual(T.advance_tax_147("securities", capital_gain=1_000_000, holding="6to12")["result"]["payable"], 15_000)


class CGTPropertyTests(SimpleTestCase):
    def test_old_plot_holding_bands(self):
        acq = date(2020, 1, 1)
        rate = lambda d: T.cgt_property("plot", acq, 10e6, 5e6, disposal_date=d)["result"]["rate_percent"]
        self.assertEqual(rate(date(2021, 1, 1)), 15)      # exactly 1 year: "does not exceed one year"
        self.assertEqual(rate(date(2021, 1, 2)), 12.5)
        self.assertEqual(rate(date(2025, 1, 1)), 5)       # exactly 5 years
        self.assertEqual(rate(date(2026, 6, 1)), 0)

    def test_flat_after_two_years_nil(self):
        r = T.cgt_property("flat", "2021-01-01", 10e6, 5e6, disposal_date="2023-06-01")["result"]
        self.assertEqual(r["cgt"], 0)

    def test_new_regime_15(self):
        r = T.cgt_property("constructed", "2024-07-01", 20e6, 15e6, disposal_date="2030-01-01")["result"]
        self.assertEqual((r["rate_percent"], r["cgt"]), (15, 750_000))

    def test_fmv_higher_than_sale(self):
        r = T.cgt_property("plot", "2024-08-01", 10e6, 8e6, disposal_date="2025-01-01", fmv=12e6)["result"]
        self.assertEqual(r["capital_gain"], 4_000_000)

    def test_s75a_cash_purchase(self):
        r = T.cgt_property("plot", "2024-08-01", 10e6, 8e6, disposal_date="2025-01-01", cash_purchase=True)
        self.assertEqual(r["result"]["capital_gain"], 10_000_000)
        self.assertIn("s.75A(3)(b)", r["law"])

    def test_clause_9a(self):
        r = T.cgt_property("constructed", "2024-08-01", 20e6, 10e6, disposal_date="2028-01-01",
                           forces_or_govt_allottee=True)["result"]
        self.assertEqual(r["cgt"], 375_000)     # 15% x 10M = 1.5M, less 75% (held over 3 years)

    def test_bad_dates(self):
        self.assertIn("error", T.run("calculate_cgt_property", {
            "property_type": "plot", "acquisition_date": "2025-01-01", "disposal_date": "2024-01-01",
            "sale_price": 1, "cost": 1}))


class CGTSecuritiesTests(SimpleTestCase):
    def test_bands(self):
        f = lambda a, d: T.cgt_securities(100_000, a, d)["result"]["rate_percent"]
        self.assertEqual(f("2024-07-01", "2030-01-01"), 15)
        self.assertEqual(f("2022-07-01", "2025-01-01"), 10)
        self.assertEqual(f("2015-01-01", "2025-01-01"), 12.5)
        self.assertEqual(f("2012-01-01", "2025-01-01"), 0)


class PropertyAdvanceTaxTests(SimpleTestCase):
    def test_236c(self):
        self.assertEqual(T.property_advance_tax("sale", 10e6)["result"]["advance_tax"], 275_000)
        self.assertEqual(T.property_advance_tax("sale", 10e6, on_atl=False)["result"]["rate_percent"], 11.5)
        self.assertEqual(T.property_advance_tax("sale", 10e6, same_year_sale=True)["tax_nature"]["type"], "minimum")

    def test_236k_non_atl_bands(self):
        rate = lambda v: T.property_advance_tax("purchase", v, on_atl=False)["result"]["rate_percent"]
        self.assertEqual((rate(50e6), rate(50_000_001), rate(100_000_001)), (10.5, 14.5, 18.5))
        self.assertEqual(T.property_advance_tax("purchase", 10e6)["result"]["advance_tax"], 125_000)

    def test_only_2027(self):
        self.assertIn("error", T.run("calculate_property_advance_tax",
                                     {"side": "sale", "amount": 1e6, "tax_year": "2025-2026"}))


class VehicleTests(SimpleTestCase):
    def test_registration(self):
        self.assertEqual(T.vehicle_tax("registration", 1300, 5_000_000)["result"]["advance_tax"], 75_000)
        self.assertEqual(T.vehicle_tax("registration", 1300, 5_000_000, on_atl=False)["result"]["rate_percent"], 4.5)

    def test_transfer(self):
        self.assertEqual(T.vehicle_tax("transfer", 1300, years_since_first_registration=2)["result"]["advance_tax"], 6_000)
        self.assertEqual(T.vehicle_tax("transfer", 1300, years_since_first_registration=5)["result"]["advance_tax"], 0)
        self.assertEqual(T.vehicle_tax("transfer", 800)["result"]["advance_tax"], 0)

    def test_token(self):
        self.assertEqual(T.vehicle_tax("token", 1000)["result"]["advance_tax"], 800)
        self.assertEqual(T.vehicle_tax("token", 2400, on_atl=False)["result"]["advance_tax"], 20_000)
        self.assertEqual(T.vehicle_tax("token_lump_sum", 1300)["result"]["advance_tax"], 30_000)


class ToolWiringTests(SimpleTestCase):
    def test_schemas_unique_and_registered(self):
        names = [t["name"] for t in agent_tools.TOOLS]
        self.assertEqual(len(names), len(set(names)))
        for s in T.SCHEMAS:
            self.assertIn(s["name"], T.FUNCTIONS)

    def test_every_result_has_law_and_nature(self):
        r = agent_tools.run_tool("calculate_vehicle_tax", {"kind": "token", "engine_cc": 1000})
        self.assertTrue(r["law"] and r["tax_nature"]["type"] and r["working"])

    def test_bad_input_is_error_not_exception(self):
        self.assertIn("error", agent_tools.run_tool("calculate_super_tax", {"income_under_4c": "abc"}))
        self.assertIn("error", agent_tools.run_tool("calculate_vehicle_tax", {"kind": "boat", "engine_cc": 1}))
