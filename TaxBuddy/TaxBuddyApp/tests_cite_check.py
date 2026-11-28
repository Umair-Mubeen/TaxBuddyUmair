"""Tests for cite_check.py and the Phase 3 law index.
    python manage.py test TaxBuddyApp.tests_cite_check --settings=TaxBuddy.settings.local
"""
from django.test import SimpleTestCase

from . import cite_check as C, law_search as L


class ExtractTests(SimpleTestCase):
    def test_forms(self):
        refs = {(b, n) for b, n, _u, _l in C.extract(
            "Under Section 37(1A) and s.236C, also Sections 114 and 115; Rule 81B. Sales Tax Act section 33.")}
        self.assertEqual(refs, {("ito", "37"), ("ito", "236C"), ("ito", "114"), ("ito", "115"),
                                ("it_rules", "81B"), ("sta", "33")})

    def test_not_money_or_schedule_rule(self):
        self.assertEqual(C.extract("Rs. 500 per day; Tenth Schedule, rule 1; 2026-27 rates."), [])


class CheckTests(SimpleTestCase):
    def tracker(self):
        t = C.Tracker()
        t.add_tool("get_law_section", {"book": "ito", "number": "182"}, {"section": "182", "text": "..."})
        t.add_tool("calculate_vehicle_tax", {}, {"law": ["s.231B(1)/(3)", "Tenth Schedule, rule 1, proviso"]})
        return t

    def test_allowed_passes_untouched(self):
        a = "Penalty under Section 182. Vehicle tax s.231B.\n\n**Reference:** Section 182, Income Tax Ordinance 2001"
        self.assertEqual(C.check(a, self.tracker()), (a, []))

    def test_unread_reference_removed_and_flagged(self):
        a = "Penalty under Section 182 and Section 205.\n\n**Reference:** Section 182, ITO 2001; Section 205, ITO 2001"
        clean, bad = C.check(a, self.tracker())
        self.assertEqual([n for _b, n, _e in bad], ["205"])
        self.assertIn("**Reference:** Section 182, ITO 2001", clean)
        self.assertNotIn("Section 205, ITO 2001", clean.split("**Reference:**")[1].split("\n")[0])
        self.assertIn("Section 205 could not be confirmed", clean)

    def test_earlier_answer_counts(self):
        t = C.Tracker(["Earlier we read Section 149."])
        self.assertEqual(C.check("As said, Section 149 applies.", t)[1], [])


class LawIndexTests(SimpleTestCase):
    def test_current_182_not_repealed_text(self):
        t = L.get_section("ito", "182", focus="fails to furnish a return of income")["text"]
        self.assertIn("0.1% of the tax payable", t)
        self.assertNotIn("two thousand five hundred", t)

    def test_heading_with_footnote_marker(self):
        r = L.get_section("ito", "234")             # "234. 1[Tax on motor vehicles]"
        self.assertIn("motor vehicle tax", r["text"])
        self.assertGreater(len(r["text"]), 500)

    def test_no_other_section_leaks_into_236C(self):
        t = L.get_section("ito", "236C")["text"]
        self.assertNotIn("air ticket", t)
        self.assertIn("2.75%" if "2.75%" in t else "Division X of Part IV", t)

    def test_rules_and_sta(self):
        self.assertIn("Active Taxpayers", L.get_section("it_rules", "81B")["title"])
        self.assertIn("registration", L.get_section("sta", "14")["text"].lower())

    def test_schedule_clause(self):
        r = L.get_schedule("ito", "Second", "III", clause="9A")
        self.assertIn("fifty percent", r["text"])

    def test_roman_urdu_search(self):
        secs = [r["section"] for r in L.search_law("ghar bechne pe advance tax", k=3)]
        self.assertIn("236C", secs)
