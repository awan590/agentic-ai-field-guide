"""Tests for Chapter 23: cost per task, break-even, sensitivity,
and the business case solution.

Run from code/:  python -m unittest tests.test_ch23
"""
import io
import unittest
from contextlib import redirect_stdout

from ch23 import roi_model as roi
from ch23 import solution_case as sol

LOGS = roi.HERE.parent.parent / "logs"
X = roi.inputs()


def run(main, argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def month(**change):
    return roi.break_even(roi.months(dict(X, **change)))


class InputTest(unittest.TestCase):
    def test_measured_numbers_come_from_ch17_and_ch20(self):
        self.assertEqual(X["tickets_week"], 640)
        self.assertAlmostEqual(X["tickets_month"], 640 * 52 / 12)
        self.assertEqual(X["pilot_tickets"], 639)
        self.assertAlmostEqual(
            X["person_minutes"] - X["agent_minutes"], 1.5755, 4)

    def test_model_cost_is_the_ch03_refund_task(self):
        self.assertAlmostEqual(X["model_per_task"], 0.0042284, 7)

    def test_unknown_or_text_inputs_are_refused(self):
        self.assertEqual(run(roi.main, ["bogus=1"])[0], 2)
        self.assertEqual(run(roi.main, ["model=1"])[0], 2)


class CostTest(unittest.TestCase):
    def test_both_sides_match_a_hand_calculation(self):
        rate = X["cost_per_hour"] / 60
        loss = X["wrong_refund_cost"] / 100
        person = (X["person_minutes"] * rate
                  * (1 + X["person_reopen"] / 100)
                  + X["person_wrong"] * loss)
        agent = (X["agent_minutes"] * rate
                 * (1 + X["agent_reopen"] / 100)
                 + X["review_share"] * X["review_minutes"] * rate
                 + X["agent_wrong"] * loss + X["model_per_task"])
        sides = roi.cost_per_task(X)
        self.assertAlmostEqual(sum(sides["person"].values()), person)
        self.assertAlmostEqual(sum(sides["agent"].values()), agent)

    def test_an_agent_no_better_than_the_desk_loses_money(self):
        same = dict(X, agent_minutes=X["person_minutes"],
                    agent_reopen=X["person_reopen"],
                    agent_wrong=X["person_wrong"])
        self.assertLess(roi.saving_per_task(same), 0)

    def test_error_scale_doubles_only_the_agent_error_costs(self):
        one = roi.cost_per_task(X)
        two = roi.cost_per_task(dict(X, error_scale=2.0))
        self.assertEqual(one["person"], two["person"])
        for part in ("repeat contacts", "wrong refunds"):
            self.assertAlmostEqual(two["agent"][part],
                                   2 * one["agent"][part])


class BreakEvenTest(unittest.TestCase):
    def test_base_case_breaks_even_in_month_9(self):
        rows = roi.months(X)
        self.assertEqual(roi.break_even(rows), 9)
        self.assertLess(rows[7][3], 0)
        self.assertGreaterEqual(rows[8][3], 0)

    def test_cumulative_total_matches_a_closed_form(self):
        per_month = X["tickets_month"] * roi.saving_per_task(X)
        shares = sum(X["ramp"]) + 24 - len(X["ramp"])
        want = -X["build"] + per_month * shares - 24 * X["run_month"]
        self.assertAlmostEqual(roi.months(X)[23][3], want, 6)

    def test_doubling_the_error_rate_moves_break_even_to_month_21(self):
        self.assertEqual(month(error_scale=2.0), 21)

    def test_break_even_passes_month_24_between_scales_2_and_2_1(self):
        self.assertEqual(month(error_scale=2.1), 25)
        self.assertIsNone(month(error_scale=2.3))

    def test_a_loss_every_month_never_breaks_even(self):
        self.assertIsNone(month(run_month=1e6))

    def test_zero_counts_as_break_even_and_a_cent_more_does_not(self):
        at9 = roi.months(dict(X, build=0))[8][3]
        self.assertEqual(month(build=at9), 9)
        self.assertEqual(month(build=at9 + 0.01), 10)


class SensitivityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = roi.sensitivity(X)

    def test_base_month_lies_between_the_good_and_bad_ends(self):
        for key, _, good, bad, swing in self.table:
            self.assertLessEqual(good, 9, key)
            self.assertGreaterEqual(bad, 9, key)
            self.assertEqual(swing, bad - good, key)

    def test_rows_are_sorted_widest_first(self):
        swings = [row[4] for row in self.table]
        self.assertEqual(swings, sorted(swings, reverse=True))
        self.assertEqual(self.table[0][0], "run_month")

    def test_measured_rows_use_the_pilot_interval(self):
        ends = {row[0]: row[1] for row in self.table}
        self.assertAlmostEqual(ends["agent_minutes"][0], 7.10, 2)
        self.assertAlmostEqual(ends["agent_minutes"][1], 7.78, 2)
        self.assertEqual(ends["agent_wrong"][0], 0.0)

    def test_tenfold_model_price_leaves_the_month_alone(self):
        self.assertEqual(month(model_per_task=10 * X["model_per_task"]),
                         9)


class CaseTest(unittest.TestCase):
    def test_solution_page_passes_its_own_check(self):
        self.assertEqual(sol.check(sol.page(X), X), [])

    def test_check_catches_numbers_headings_and_signers(self):
        page = (sol.page(X).replace("$5.30", "$5.03")
                .replace("## Risks", "## Risk")
                .replace("Finance:", ""))
        problems = sol.check(page, X)
        self.assertIn("Agent cost per task: page says $5.03, "
                      "model says $5.30", problems)
        self.assertIn("missing heading: ## Risks", problems)
        self.assertIn("no Finance line under ## Sign-off", problems)

    def test_an_old_page_fails_after_an_assumption_changes(self):
        old = sol.page(X)
        self.assertNotEqual(sol.check(old, dict(X, cost_per_hour=40)),
                            [])


class LogTest(unittest.TestCase):
    def test_printed_runs_match_their_logs(self):
        runs = [("ch23-model", roi.main, []),
                ("ch23-errors", roi.main, ["error_scale=2"]),
                ("ch23-sensitivity", roi.main, ["--sensitivity"]),
                ("ch23-fte", roi.main, ["--fte"]),
                ("ch23-case", sol.main, [])]
        for name, main, argv in runs:
            code, out = run(main, argv)
            self.assertEqual(code, 0, name)
            self.assertEqual(out, (LOGS / f"{name}.txt").read_text(),
                             name)


if __name__ == "__main__":
    unittest.main()
