"""Tests for Chapter 22: the obligations table, the sheet, and the
audit trail.

Run from code/:  python -m unittest tests.test_ch22
"""
import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date

from ch22 import audit
from ch22 import obligations as ob
from ch22 import solution_sheet as ss

TABLE = ob.load(ob.TABLE)
PROFILE = ob.load(ob.PROFILE)


def said(profile=PROFILE, on=ob.TODAY):
    return {r["id"]: ob.status(r, profile, on) for r in TABLE["rules"]}


def quiet(fn, argv):
    with redirect_stdout(io.StringIO()):
        return fn(argv)


class TableTest(unittest.TestCase):
    def test_every_rule_has_dates_and_a_source(self):
        self.assertEqual(ob.problems(TABLE), [])

    def test_a_missing_field_or_bad_date_is_named(self):
        table = copy.deepcopy(TABLE)
        del table["rules"][0]["applies"]
        table["rules"][1]["read"] = "2026-13-01"
        self.assertEqual(ob.problems(table), [
            "EU-BAN: no applies", "EU-GPAI: bad read 2026-13-01"])

    def test_privacy_rows_are_guidance_with_a_counsel_note(self):
        rows = {r["id"]: r for r in TABLE["rules"]
                if r["id"] in ("EU-DPIA", "EU-EDPB", "EU-DPF")}
        self.assertEqual(sorted(rows), ["EU-DPF", "EU-DPIA", "EU-EDPB"])
        got = said()
        for rid, row in rows.items():
            self.assertEqual(got[rid], "guidance")
            self.assertTrue(row["check"])
        self.assertEqual(rows["EU-DPIA"]["source"], ["S1393", "S1111"])
        self.assertEqual(rows["EU-DPF"]["source"], ["S1394", "S1444"])

    def test_privacy_rows_join_the_report_on_their_dates(self):
        early = said(on=date(2024, 12, 16))
        self.assertEqual(early["EU-DPIA"], "coming")
        self.assertEqual(early["EU-DPF"], "guidance")
        lines = ob.report(TABLE, dict(PROFILE, regions=["EU"]))
        self.assertIn("  EU-EDPB     2024-12-17  any: governance lead  "
                      "S1393", lines)

    def test_no_saudi_rows_until_a_page_is_read(self):
        regions = {r["region"] for r in TABLE["rules"]}
        self.assertNotIn("SA", regions)


class StatusTest(unittest.TestCase):
    def test_default_profile(self):
        got = said()
        self.assertEqual(sorted(k for k, v in got.items()
                                if v == "in force"),
                         ["EU-ART50", "EU-GDPR30", "EU-GDPR33"])
        self.assertEqual(list(got.values()).count("guidance"), 9)
        self.assertEqual(got["EU-GPAI"], "other role")
        self.assertEqual(got["EU-BAN"], "other tier")

    def test_high_tier_brings_dated_rows(self):
        got = said(dict(PROFILE, tier="high"))
        coming = sorted(k for k, v in got.items() if v == "coming")
        self.assertEqual(coming, ["CO-ADVERSE", "CO-NOTICE",
                                  "CO-RECORDS", "EU-HR-HUMAN",
                                  "EU-HR-LOG", "EU-HR-RISK"])

    def test_the_date_a_rule_applies_decides(self):
        got = said(on=date(2024, 12, 20))
        self.assertEqual(got["EU-ART50"], "coming")
        self.assertEqual(got["EU-GDPR33"], "in force")
        self.assertEqual(said(on=date(2026, 8, 2))["EU-ART50"],
                         "in force")

    def test_region_filter(self):
        got = said(dict(PROFILE, regions=["UK"]))
        self.assertEqual(got["UK-PRINC"], "guidance")
        self.assertEqual(got["EU-ART50"], "other region")


class ReportTest(unittest.TestCase):
    def test_gap_line_and_skip_count(self):
        lines = ob.report(TABLE, PROFILE)
        self.assertIn("  SA: no rows on file; check the regulator's "
                      "current page", lines)
        self.assertEqual(lines[-1], "Skipped 8 of 20 rules: "
                                    "other role 1, other tier 7.")

    def test_every_line_fits_the_page(self):
        for tier in ("transparency", "high", "minimal"):
            lines = ob.report(TABLE, dict(PROFILE, tier=tier))
            self.assertLessEqual(max(map(len, lines)), 72)

    def test_rows_go_stale_after_ninety_days(self):
        lines = ob.report(TABLE, PROFILE, date(2027, 2, 2))
        self.assertNotIn("  EU-ART50    read 2026-11-04", lines)
        lines = ob.report(TABLE, PROFILE, date(2027, 2, 3))
        self.assertIn("  EU-ART50    read 2026-11-04", lines)

    def test_unknown_option_prints_usage(self):
        self.assertEqual(quiet(ob.main, ["tier"]), 2)
        self.assertEqual(quiet(ob.main, ["colour", "red"]), 2)
        self.assertEqual(quiet(ob.main, ["tier", "high"]), 0)


class SheetTest(unittest.TestCase):
    def test_solution_sheet_passes_its_check(self):
        text = "\n".join(ss.sheet(TABLE, PROFILE))
        self.assertEqual(ss.check(text, TABLE, PROFILE), [])
        self.assertLessEqual(max(map(len, text.splitlines())), 72)

    def test_a_missing_row_fails(self):
        lines = [x for x in ss.sheet(TABLE, PROFILE)
                 if not x.startswith("| CO-RECORDS")]
        self.assertEqual(ss.check("\n".join(lines), TABLE, PROFILE),
                         ["CO-RECORDS: no line with its date and "
                          "source"])

    def test_a_missing_sign_off_fails(self):
        lines = ss.sheet(TABLE, PROFILE)[:-1]
        self.assertEqual(ss.check("\n".join(lines), TABLE, PROFILE),
                         ["missing 'Sign-off:'"])

    def test_an_empty_sheet_fails_on_everything(self):
        found = ss.check("", TABLE, PROFILE)
        self.assertEqual(len(found), 12 + 1 + 3)


class AuditTest(unittest.TestCase):
    def test_chain_verifies(self):
        records = audit.trail()
        self.assertEqual(len(records), 7)
        self.assertIsNone(audit.verify(records))

    def test_a_changed_record_breaks_the_chain_there(self):
        records = audit.trail()
        records[5]["verdict"] = "ALLOW"
        self.assertEqual(audit.verify(records), 5)
        records = audit.trail()
        del records[3]
        self.assertEqual(audit.verify(records), 4)

    def test_money_has_an_approver(self):
        asks = [r for r in audit.trail() if r.get("verdict") == "ASK"]
        self.assertEqual([(r["tool"], r["approver"]) for r in asks],
                         [("issue_refund", audit.APPROVER)])

    def test_no_raw_email_in_the_trail(self):
        raw = json.dumps(audit.trail())
        self.assertNotIn("priya.nair@", raw)
        self.assertNotIn("audit@", raw)

    def test_tamper_run_exits_zero_only_when_caught(self):
        self.assertEqual(quiet(audit.main, []), 0)
        self.assertEqual(quiet(audit.main, ["tamper", "5"]), 0)
        self.assertEqual(quiet(audit.main, ["tamper", "9"]), 2)


if __name__ == "__main__":
    unittest.main()
