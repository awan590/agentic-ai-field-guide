"""Tests for Chapter 17: the returns desk baseline and the one-page
value hypothesis.

Run from code/:  python -m unittest tests.test_ch17
"""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ch17 import baseline as bl
from ch17 import replay
from ch17 import solution_hypothesis as hyp

TINY = ("id,week,type,minutes,error\n"
        "A,1,label,4.0,0\n"
        "B,1,label,6.0,1\n"
        "C,2,damaged,20.0,0\n"
        "D,2,label,14.0,0\n")


def temp_file(text):
    folder = Path(tempfile.mkdtemp())
    path = folder / "file.txt"
    path.write_text(text)
    return path


class BaselineTest(unittest.TestCase):
    def test_sample_log_has_two_weeks_of_640(self):
        s = bl.summary(bl.load())
        self.assertEqual(s["weeks"], 2)
        self.assertEqual(s["all"]["tickets"], 1280)
        self.assertEqual(s["all"]["per_week"], 640)
        self.assertEqual(sum(v["tickets"] for v in
                             s["types"].values()), 1280)

    def test_numbers_by_hand_on_a_tiny_log(self):
        s = bl.summary(bl.load(temp_file(TINY)))
        label = s["types"]["label"]
        self.assertEqual(label["tickets"], 3)
        self.assertEqual(label["mean"], 8.0)
        self.assertEqual(label["median"], 6.0)
        self.assertEqual(label["error"], 33.3)
        self.assertEqual(label["hours"], 0.2)    # 24 min / 2 weeks
        self.assertEqual(label["share"], 75)
        self.assertEqual(s["all"]["mean"], 11.0)
        self.assertEqual(s["all"]["error"], 25.0)

    def test_types_sorted_by_desk_hours(self):
        hours = [v["hours"] for v in
                 bl.summary(bl.load())["types"].values()]
        self.assertEqual(hours, sorted(hours, reverse=True))

    def test_report_is_the_same_every_run(self):
        first = bl.report(bl.summary(bl.load()))
        again = bl.report(bl.summary(bl.load()))
        self.assertEqual(first, again)
        self.assertTrue(first[0].startswith("Returns desk baseline"))
        self.assertTrue(all(len(x) <= 72 for x in first))

    def test_log_without_a_column_is_refused(self):
        bad = temp_file("id,week,type,minutes\nA,1,label,4.0\n")
        with self.assertRaises(ValueError) as e:
            bl.load(bad)
        self.assertIn("error", str(e.exception))

    def test_empty_log_is_refused(self):
        with self.assertRaises(ValueError):
            bl.load(temp_file("id,week,type,minutes,error\n"))


class HypothesisTest(unittest.TestCase):
    def setUp(self):
        self.s = bl.summary(bl.load())

    def test_page_numbers_match_the_baseline_table(self):
        page = hyp.page(self.s)
        table = "\n".join(bl.report(self.s))
        self.assertEqual(hyp.check(page, self.s), [])
        for label, value in hyp.numbers(self.s).items():
            self.assertIn(f"- {label}: {value}", page)
        every = self.s["all"]
        self.assertIn(f"{every['per_week']:>8}", table)
        self.assertIn(f"{every['error']:>7.1f}%", table)

    def test_candidate_numbers_add_up_from_the_rows(self):
        n = hyp.numbers(self.s)
        rows = [self.s["types"][t] for t in hyp.CANDIDATES]
        self.assertEqual(int(n["Candidate tickets per week"]),
                         sum(r["per_week"] for r in rows))
        self.assertLess(float(n["Candidate hours per week"]),
                        self.s["all"]["hours"])

    def test_wrong_number_is_caught(self):
        page = hyp.page(self.s).replace("- Tickets per week: 640",
                                        "- Tickets per week: 700")
        self.assertEqual(hyp.check(page, self.s),
                         ["Tickets per week: page says 700, "
                          "baseline says 640"])

    def test_missing_heading_and_sponsor_are_caught(self):
        page = hyp.page(self.s).replace("## Stop if\n", "")
        page = page.replace("Sponsor (head of customer service):", "")
        problems = hyp.check(page, self.s)
        self.assertIn("missing heading: ## Stop if", problems)
        self.assertIn("no Sponsor line under ## Sign-off", problems)

    def test_check_command_on_a_saved_page(self):
        good = temp_file(hyp.page(self.s))
        bad = temp_file(hyp.page(self.s).replace("8.6%", "7.0%"))
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(hyp.main(["check", str(good)]), 0)
            self.assertEqual(hyp.main(["check", str(bad)]), 1)
        self.assertIn("OK: every number matches", out.getvalue())
        self.assertIn("Error rate: page says 7.0%", out.getvalue())

    def test_case_shaped_plan_fails_the_check(self):
        problems = hyp.check(replay.PLAN, self.s)
        self.assertEqual(len(problems), 8)
        self.assertIn("missing heading: ## Baseline", problems)
        self.assertIn("missing line: - Tickets per week: 640", problems)

    def test_page_fits_on_one_page(self):
        lines = hyp.page(self.s).splitlines()
        self.assertLessEqual(len(lines), 50)
        self.assertTrue(all(len(x) <= 72 for x in lines))


if __name__ == "__main__":
    unittest.main()
