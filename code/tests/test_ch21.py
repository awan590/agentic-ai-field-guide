"""Tests for Chapter 21: the handover pack check and the adoption
report.

Run from code/:  python -m unittest tests.test_ch21
"""
import io
import unittest
from contextlib import redirect_stdout

from ch20.pilot_vs_control import arm_for
from ch21 import adoption as ad
from ch21 import handover_check as hc

SAMPLE = hc.HERE / "sample_pack"
SOLUTION = hc.HERE / "solution_pack"
GOOD = [(area, "returns desk lead", "head of customer service")
        for area in hc.AREAS]


def quiet(argv):
    with redirect_stdout(io.StringIO()):
        return hc.main(argv)


class PackTest(unittest.TestCase):
    def test_solution_pack_passes(self):
        self.assertEqual(hc.check_pack(SOLUTION), [])

    def test_sample_pack_fails_with_the_planted_gaps(self):
        self.assertEqual(hc.check_pack(SAMPLE), [
            "owners.md: answers to shoppers: no owner (TBD)",
            "owners.md: kill switch: outside owner 'FDE'",
            "rollback.md: file missing",
            "contacts.md: missing 'L3'",
            "README.md: broken link rollback.md",
            "alerts.md: broken link ../../ch14/alert.py",
            "runbook.md: no module ch16.rollback"])

    def test_an_empty_folder_misses_every_part(self):
        problems = hc.check_pack(hc.HERE / "no_such_pack")
        self.assertEqual(len(problems), len(hc.PARTS))

    def test_exit_codes(self):
        self.assertEqual(quiet([str(SOLUTION)]), 0)
        self.assertEqual(quiet([str(SAMPLE)]), 1)
        self.assertEqual(quiet([str(SAMPLE), "--warn"]), 0)
        self.assertEqual(quiet(["--replay"]), 1)


class OwnerTest(unittest.TestCase):
    def test_table_rows_skip_header_and_rule(self):
        text = ("| Area | Owner | Backup |\n|---|---|---|\n"
                "| data map | data protection lead | IT lead |\n")
        self.assertEqual(hc.owner_rows(text),
                         [("data map", "data protection lead",
                           "IT lead")])

    def test_customer_roles_pass(self):
        self.assertEqual(hc.owner_problems(GOOD), [])

    def test_every_area_needs_a_row(self):
        self.assertEqual(len(hc.owner_problems([])), len(hc.AREAS))

    def test_blank_owner_and_backup_fail(self):
        rows = [(a, "TBD" if a == "rollback" else o,
                 "" if a == "data map" else b) for a, o, b in GOOD]
        self.assertEqual(hc.owner_problems(rows),
                         ["rollback: no owner (TBD)",
                          "data map: no backup"])

    def test_outside_owners_fail(self):
        for who in ("the chatbot", "returns agent", "Vendor team",
                    "FDE"):
            rows = [(a, who if a == "answers to shoppers" else o, b)
                    for a, o, b in GOOD]
            self.assertEqual(hc.owner_problems(rows),
                             [f"answers to shoppers: outside owner "
                              f"{who!r}"])

    def test_replay_puts_the_answers_outside_the_customer(self):
        self.assertEqual(hc.replay(), [
            "owners.md: answers to shoppers: outside owner "
            "'the chatbot'",
            "owners.md: answers to shoppers: no backup"])


class LinkTest(unittest.TestCase):
    def test_only_relative_links_are_checked(self):
        text = ("[a](https://example.com/x) [b](mailto:x@example.com) "
                "[c](#top) [d](runbook.md#kill-switch) [e](gone.md)")
        self.assertEqual(hc.broken_links(text, SOLUTION), ["gone.md"])

    def test_links_into_earlier_chapters_resolve(self):
        text = "[gate](../../ch12/gate.py) [x](../../ch14/alert.py)"
        self.assertEqual(hc.broken_links(text, SOLUTION),
                         ["../../ch14/alert.py"])

    def test_named_commands_must_exist(self):
        text = "Run `python -m ch12.gate` or `python -m ch16.rollback`."
        self.assertEqual(hc.missing_modules(text), ["ch16.rollback"])


def rows(*items):
    return [{"week": w, "ticket": f"T{k}", "staff": s, "outcome": o}
            for k, (w, s, o) in enumerate(items)]


class AdoptionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = ad.make_log()

    def test_same_seed_same_log(self):
        self.assertEqual(self.log, ad.make_log())
        self.assertNotEqual(self.log, ad.make_log(seed=22))

    def test_wau_and_share_by_hand(self):
        log = rows((1, "S01", "used"), (1, "S01", "none"),
                   (1, "S02", "opened"), (1, "S03", "holdout"))
        honest = ad.weekly(log)[0]
        self.assertEqual((honest["eligible"], honest["holdout"]),
                         (3, 1))
        self.assertEqual((honest["active"], honest["wau"],
                          honest["share"]), (1, 6, 33))
        loose = ad.weekly(log, ("used", "opened"))[0]
        self.assertEqual((loose["active"], loose["share"]), (2, 67))

    def test_holdout_is_the_hash_and_only_weeks_1_to_4(self):
        for r in self.log:
            held = r["week"] <= 4 and arm_for(r["ticket"], 95) == \
                "control"
            self.assertEqual(r["outcome"] == "holdout", held)
        first = [w["holdout"] for w in ad.weekly(self.log)][:4]
        self.assertAlmostEqual(sum(first) / (4 * ad.PER_WEEK), 0.05,
                               delta=0.015)

    def test_holdout_leaves_the_denominator(self):
        for w in ad.weekly(self.log):
            self.assertEqual(w["eligible"] + w["holdout"], ad.PER_WEEK)

    def test_loose_count_is_never_lower(self):
        honest = ad.weekly(self.log)
        loose = ad.weekly(self.log, ("used", "opened"))
        for h, lo in zip(honest, loose):
            self.assertGreaterEqual(lo["wau"], h["wau"])
            self.assertGreaterEqual(lo["share"], h["share"])

    def test_staff_with_no_draft_are_named(self):
        quiet_staff = ad.not_active(self.log, [7, 8])
        self.assertEqual(len(quiet_staff), 3)
        for s in quiet_staff:
            self.assertFalse(any(r["staff"] == s and
                                 r["outcome"] == "used"
                                 for r in self.log))

    def test_goals_ramp_then_hold(self):
        self.assertEqual(ad.goals(1), (50, 20))
        self.assertEqual(ad.goals(4), (80, 55))
        self.assertEqual(ad.goals(8), (80, 60))


if __name__ == "__main__":
    unittest.main()
