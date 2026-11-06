"""Tests for Chapter 20: lift with an interval, the signed go and
no-go gate, and the readout solution.

Run from code/:  python -m unittest tests.test_ch20
"""
import copy
import io
import itertools
import math
import statistics
import unittest
from contextlib import redirect_stdout

from ch20 import go_no_go as g
from ch20 import make_weeks
from ch20 import pilot_vs_control as pvc
from ch20 import solution_readout as sol

RULES = g.load("criteria.json")["rules"]
WEEKS = ["week1", "week2"]


def result(tickets=700, wrong=0.5, reopen_high=-1.0,
           minutes_high=-1.5, handoff=20.0):
    """A hand-made readout result with every rule passing."""
    return {"tickets": {"pilot": tickets, "control": tickets},
            "wrong_refund": {"pilot": wrong},
            "reopened": {"high": reopen_high},
            "minutes": {"high": minutes_high},
            "handoff": {"pilot": handoff}}


def verdict(**kw):
    return g.decide(RULES, result(**kw))[0]


class LiftTest(unittest.TestCase):
    def test_same_seed_gives_the_same_interval(self):
        a = [float(i % 7) for i in range(200)]
        b = [float(i % 5) for i in range(200)]
        self.assertEqual(pvc.lift(a, b), pvc.lift(a, b))

    def test_identical_groups_give_an_interval_around_zero(self):
        a = [float(i % 9) for i in range(300)]
        point, low, high = pvc.lift(a, list(a))
        self.assertEqual(point, 0)
        self.assertLess(low, 0)
        self.assertGreater(high, 0)

    def test_shifting_the_pilot_shifts_the_lift_exactly(self):
        a = [float(i % 9) for i in range(300)]
        b = [float(i % 7) for i in range(300)]
        before = pvc.lift(a, b)[0]
        after = pvc.lift([x - 2 for x in a], b)[0]
        self.assertAlmostEqual(after, before - 2)

    def test_interval_agrees_with_a_normal_approximation(self):
        rows = pvc.load_weeks(WEEKS)
        p = [r["minutes"] for r in rows if r["arm"] == "pilot"]
        c = [r["minutes"] for r in rows if r["arm"] == "control"]
        point, low, high = pvc.lift(p, c)
        se = math.sqrt(statistics.variance(p) / len(p)
                       + statistics.variance(c) / len(c))
        self.assertAlmostEqual(low, point - 1.96 * se, delta=0.05)
        self.assertAlmostEqual(high, point + 1.96 * se, delta=0.05)


class SplitTest(unittest.TestCase):
    def test_split_is_stable_and_near_half(self):
        ids = [f"T9-{i:04d}" for i in range(2000)]
        arms = [pvc.arm_for(t) for t in ids]
        self.assertEqual(arms, [pvc.arm_for(t) for t in ids])
        self.assertAlmostEqual(arms.count("pilot") / len(ids), 0.5,
                               delta=0.04)

    def test_sample_weeks_match_the_generator(self):
        for week in (1, 2):
            buf = io.StringIO()
            make_weeks.write_week(week, buf)
            with open(pvc.HERE / f"week{week}.csv", newline="") as f:
                self.assertEqual(f.read(), buf.getvalue())


class GateTest(unittest.TestCase):
    def test_one_fixture_per_verdict(self):
        self.assertEqual(verdict(), "SCALE")
        self.assertEqual(verdict(handoff=31.0), "FIX")
        self.assertEqual(verdict(handoff=31.0, minutes_high=-0.5),
                         "STOP")

    def test_good_numbers_with_one_broken_must_rule_stop(self):
        v, note, _ = g.decide(RULES, result(wrong=1.2,
                                            minutes_high=-3.0))
        self.assertEqual(v, "STOP")
        self.assertIn("wrong refund %", note)

    def test_fix_needs_a_fix_named_in_week_0(self):
        rules = copy.deepcopy(RULES)
        del rules[4]["fix"]
        self.assertEqual(g.decide(rules, result(handoff=31.0))[0],
                         "STOP")

    def test_value_at_the_limit_passes_and_just_past_fails(self):
        self.assertEqual(verdict(minutes_high=-1.0), "SCALE")
        self.assertEqual(verdict(minutes_high=-0.99), "FIX")
        self.assertEqual(verdict(minutes_high=-0.9999999), "SCALE")
        self.assertEqual(verdict(tickets=600), "SCALE")
        self.assertEqual(verdict(tickets=599), "STOP")
        self.assertEqual(verdict(wrong=1.0), "SCALE")
        self.assertEqual(verdict(wrong=1.01), "STOP")
        self.assertEqual(verdict(reopen_high=3.0), "SCALE")
        self.assertEqual(verdict(reopen_high=3.01), "STOP")

    def test_verdict_matches_an_independent_rule_table(self):
        breaks = {"tickets per group": {"tickets": 10},
                  "wrong refund %": {"wrong": 5.0},
                  "reopened lift, high": {"reopen_high": 9.0},
                  "minutes lift, high": {"minutes_high": 0.5},
                  "handoff %": {"handoff": 60.0}}
        for fails in itertools.product([False, True], repeat=5):
            kw, must, core = {}, 0, 0
            for rule, fail in zip(RULES, fails):
                if fail:
                    kw.update(breaks[rule["name"]])
                    must += rule["kind"] == "must"
                    core += rule["kind"] == "core"
            want = ("STOP" if must or core > 1
                    else "FIX" if core else "SCALE")
            self.assertEqual(verdict(**kw), want, fails)


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.criteria = g.load("criteria.json")
        self.signoff = g.load("signoff.json")

    def test_sample_sign_off_matches_the_criteria(self):
        self.assertEqual(
            g.check_plan(self.criteria, self.signoff, WEEKS), [])

    def test_a_moved_goal_is_refused(self):
        self.criteria["rules"][3]["limit"] = -0.5
        why = g.check_plan(self.criteria, self.signoff, WEEKS)
        self.assertEqual(why,
                         ["criteria changed after the week 0 sign-off"])

    def test_deciding_before_the_end_date_is_refused(self):
        why = g.check_plan(self.criteria, self.signoff, ["week1"])
        self.assertEqual(why, ["too early, still to come: week2"])

    def test_exit_codes(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(g.main([]), 0)
            self.assertEqual(g.main(["week1"]), 2)
            self.assertEqual(g.main(["--replay"]), 1)
            self.assertEqual(g.main(["--replay", "--warn"]), 0)


class ReadoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = sol.run_gate()

    def test_solution_page_passes_its_own_check(self):
        v, _, scored, _, sha = self.gate
        page = sol.write(*self.gate)
        self.assertEqual(v, "SCALE")
        self.assertEqual(sol.check(page, v, scored, sha), [])

    def test_check_catches_wrong_numbers_and_headings(self):
        v, _, scored, _, sha = self.gate
        page = (sol.write(*self.gate).replace("20.66", "26.06")
                .replace("## Sign-off", "## Signed")
                .replace("GO: SCALE", "NO-GO: FIX"))
        problems = sol.check(page, v, scored, sha)
        self.assertIn("handoff %: value 20.66 not found", problems)
        self.assertIn("missing heading ## Sign-off", problems)
        self.assertIn("decision does not say SCALE", problems)

    def test_week2_readout_matches_its_log(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            pvc.main(["week2"])
        log = pvc.HERE.parent.parent / "logs" / "ch20-week2.txt"
        self.assertEqual(buf.getvalue(), log.read_text())


if __name__ == "__main__":
    unittest.main()
