"""Tests for Chapter 3: prices, cost per task, routing, the task.

Run from code/:  python -m unittest tests.test_ch03
"""
import io
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

from ch03 import cost_per_task as cpt
from ch03 import router
from ch03 import solution_cost_cut as sol

PRICE = {"input": 2.0, "output": 10.0, "cache_write": 2.5,
         "cache_read": 0.1, "cache_min_tokens": 512,
         "tool_prompt_tokens": 300}


class PriceFileTest(unittest.TestCase):
    def test_file_is_dated_and_complete(self):
        prices = cpt.load_prices()
        self.assertEqual(prices["as_of"], "2026-11-03")
        self.assertIn(prices["as_of"], cpt.PRICES.name)
        for price in prices["models"].values():
            for key in PRICE:
                self.assertIn(key, price)

    def test_tiers_name_listed_models(self):
        prices = cpt.load_prices()
        for model in prices["tiers"].values():
            self.assertIn(model, prices["models"])

    def test_undated_file_is_refused(self):
        with mock.patch.object(Path, "read_text",
                               return_value='{"models": {}}'):
            with self.assertRaises(ValueError):
                cpt.load_prices("undated.json")


class RetirementWarningTest(unittest.TestCase):
    def test_new_file_is_dated_and_has_retirement_dates(self):
        prices = cpt.load_prices(cpt.CURRENT)
        self.assertEqual(prices["as_of"], "2026-11-06")
        self.assertIn(prices["as_of"], cpt.CURRENT.name)
        for price in prices["models"].values():
            self.assertIn("retires_not_before", price)

    def test_no_warning_far_from_retirement(self):
        prices = cpt.load_prices(cpt.CURRENT)
        self.assertEqual(cpt.retirement_warnings(
            prices, date(2026, 11, 6)), [])

    def test_warning_names_model_within_60_days(self):
        prices = cpt.load_prices(cpt.CURRENT)
        got = cpt.retirement_warnings(prices, date(2027, 8, 1))
        self.assertEqual(len(got), 1)
        self.assertIn("claude-sonnet-5-5", got[0])
        self.assertIn("2027-09-28", got[0])
        early = cpt.retirement_warnings(prices, date(2027, 7, 29))
        self.assertEqual(early, [])

    def test_main_prints_the_warning(self):
        out = io.StringIO()
        with mock.patch.object(cpt, "date") as fake:
            fake.today.return_value = date(2027, 9, 30)
            fake.fromisoformat = date.fromisoformat
            with redirect_stdout(out):
                cpt.main(["lookup"])
        self.assertIn("warning: claude-haiku-5-5", out.getvalue())


class CostMathTest(unittest.TestCase):
    CALL = {"input": 1000, "output": 100, "tools": 200}

    def test_parts_price_each_kind(self):
        cost = cpt.parts([self.CALL], PRICE)
        self.assertAlmostEqual(cost["input"], 800 * 2.0 / 1e6)
        self.assertAlmostEqual(cost["tools"], 500 * 2.0 / 1e6)
        self.assertAlmostEqual(cost["output"], 100 * 10.0 / 1e6)

    def test_system_prompt_counts_on_every_call(self):
        one = sum(cpt.parts([self.CALL] * 2, PRICE).values())
        two = sum(cpt.parts([self.CALL] * 2, PRICE, 100).values())
        self.assertAlmostEqual(two - one, 2 * 100 * 2.0 / 1e6)

    def test_short_prefix_is_not_cached(self):
        calls = [self.CALL] * 3
        self.assertAlmostEqual(cpt.cached_cost(calls, PRICE),
                               sum(cpt.parts(calls, PRICE).values()))

    def test_long_prefix_writes_once_then_reads(self):
        calls = [self.CALL] * 3
        prefix = 200 + 300 + 1000
        plain = sum(cpt.parts(calls, PRICE, 1000).values())
        want = plain + prefix * (2.5 + 2 * 0.1 - 3 * 2.0) / 1e6
        got = cpt.cached_cost(calls, PRICE, 1000)
        self.assertAlmostEqual(got, want)
        self.assertLess(got, plain)


class MeterTest(unittest.TestCase):
    def test_meter_matches_chapter_2_totals(self):
        _, result, calls = cpt.run_metered("refund")
        self.assertEqual(len(calls), result["steps"])
        total = sum(c["input"] + c["output"] for c in calls)
        self.assertEqual(total, result["tokens"])

    def test_script_prints_the_price_date(self):
        out = io.StringIO()
        with redirect_stdout(out):
            cpt.main(["lookup"])
        self.assertIn("as of 2026-11-06", out.getvalue())
        self.assertIn("with caching", out.getvalue())


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.tasks = router.labeled_tasks()
        self.prices = cpt.load_prices()

    def test_test_set_is_balanced_and_unique(self):
        labels = [t["label"] for t in self.tasks]
        self.assertEqual(labels.count("easy"), 100)
        self.assertEqual(labels.count("hard"), 100)
        self.assertEqual(len({t["id"] for t in self.tasks}), 200)
        self.assertEqual(len({t["text"] for t in self.tasks}), 200)

    def test_route_reads_words_and_ids(self):
        self.assertEqual(router.route("Has order A-1101 shipped?"),
                         "small")
        self.assertEqual(router.route("Refund order A-1101."), "large")
        self.assertEqual(router.route("A-1101 or A-1102?"), "large")

    def test_small_right_means_large_right(self):
        for t in self.tasks:
            if router.stand_in_right("small", t):
                self.assertTrue(router.stand_in_right("large", t))

    def test_evaluate_is_deterministic(self):
        one = router.evaluate(self.tasks, router.route, self.prices)
        two = router.evaluate(self.tasks, router.route, self.prices)
        self.assertEqual(one, two)
        self.assertEqual(one["small"], 125)

    def test_small_tier_is_cheaper(self):
        small = router.evaluate(self.tasks, lambda t: "small",
                                self.prices)
        large = router.evaluate(self.tasks, lambda t: "large",
                                self.prices)
        self.assertLess(small["cost"], large["cost"])
        self.assertLess(small["accuracy"], large["accuracy"])


class CostCutTaskTest(unittest.TestCase):
    def setUp(self):
        tasks, prices = router.labeled_tasks(), cpt.load_prices()
        self.base = router.evaluate(tasks, lambda t: "large", prices)
        self.first = router.evaluate(tasks, router.route, prices)
        self.safe = router.evaluate(tasks, sol.route_safe, prices)

    def test_first_router_loses_too_much(self):
        _, loss, ok = sol.check(self.base, self.first)
        self.assertGreater(loss, sol.MAX_LOSS)
        self.assertFalse(ok)

    def test_solution_cuts_a_third(self):
        cut, _, _ = sol.check(self.base, self.safe)
        self.assertGreaterEqual(cut, 100 / 3)

    def test_solution_loses_at_most_one_point(self):
        _, loss, ok = sol.check(self.base, self.safe)
        self.assertLessEqual(loss, 1.0)
        self.assertTrue(ok)

    def test_explained_request_goes_large(self):
        text = "Where is order A-1101? It is a week late."
        self.assertEqual(router.route(text), "small")
        self.assertEqual(sol.route_safe(text), "large")


if __name__ == "__main__":
    unittest.main()
