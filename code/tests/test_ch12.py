"""Tests for Chapter 12: the eval set, the checks, the judges, the
replayed week, and the gate.

Run from code/:  python -m unittest tests.test_ch12
"""
import io
import unittest
from collections import Counter
from contextlib import redirect_stdout
from statistics import stdev

from ch12 import baseline, gate
from ch12 import run_evals as ev
from ch12.agent import AGREE, CURRENT, HERE, REFUND, load_prompt


def quiet(fn, *args):
    out = io.StringIO()
    with redirect_stdout(out):
        value = fn(*args)
    return value, out.getvalue()


class EvalSet(unittest.TestCase):
    def test_sixty_cases_half_from_traces(self):
        cases = ev.load_cases()
        self.assertEqual(len(cases), 60)
        self.assertEqual(len({c["id"] for c in cases}), 60)
        traced = [c for c in cases if c["from"].startswith("T-")]
        self.assertEqual(len(traced), 30)
        self.assertEqual(Counter(c["kind"] for c in traced)
                         .most_common(1), [("stale-policy", 7)])

    def test_every_case_has_a_reference(self):
        for c in ev.load_cases():
            with self.subTest(case=c["id"]):
                self.assertTrue(c["must"])

    def test_released_prompt_passes_44(self):
        rows = ev.score(ev.load_cases(), load_prompt())
        self.assertEqual(sum(r["pass"] for r in rows), 44)

    def test_stale_page_fails_two_checks(self):
        case = {c["id"]: c for c in ev.load_cases()}["E08"]
        marks = ev.checks(case, ev.run_case(case, load_prompt()))
        self.assertEqual([k for k, v in marks.items() if not v],
                         ["rule", "no_wrong"])

    def test_agreeable_line_breaks_refund_cases(self):
        rules = load_prompt() + [AGREE]
        rows = ev.score(ev.load_cases(), rules)
        kinds = ev.by_kind(rows)
        self.assertEqual(kinds["refund-promise"][1], 0)


class Judges(unittest.TestCase):
    def test_labels_match_the_agent(self):
        cases = {c["id"]: c for c in ev.load_cases()}
        labels = ev.load_labels()
        self.assertEqual(len(labels), 30)
        for lab in labels:
            with self.subTest(case=lab["case"], prompt=lab["prompt"]):
                rules = load_prompt(HERE / lab["prompt"])
                result = ev.run_case(cases[lab["case"]], rules)
                self.assertEqual(result["answer"], lab["answer"])

    def test_agreement_numbers(self):
        got = {name: ev.agreement(pairs)
               for name, pairs in ev.judges(ev.load_labels()).items()}
        self.assertAlmostEqual(got["vibe judge"][0], 13 / 30)
        self.assertEqual(got["vibe judge"][2], 14)
        self.assertAlmostEqual(got["rubric judge"][0], 23 / 30)
        self.assertEqual(got["rubric + reference"][0], 1.0)
        self.assertEqual(got["always pass"][1], 0.0)

    def test_kappa_by_hand(self):
        pairs = [("pass", "pass")] * 6 + [("fail", "fail")] * 2 \
            + [("pass", "fail")] * 2
        same, kappa, fp, ff = ev.agreement(pairs)
        self.assertAlmostEqual(same, 0.8)
        self.assertAlmostEqual(kappa, (0.8 - 0.56) / 0.44)
        self.assertEqual((fp, ff), (2, 0))


class Week(unittest.TestCase):
    def test_thumbs_reward_the_agreeable_prompt(self):
        _, text = quiet(ev.week)
        self.assertIn("prompt.txt               0     6       15", text)
        self.assertIn("prompt_agreeable.txt     6     0       17", text)

    def test_flags_need_no_reference(self):
        case = {"id": "W99", "message": "Where is order A-1005?",
                "order": "A-1005"}
        result = ev.run_case(case, load_prompt())
        self.assertEqual(ev.flags(case, result), ["off-page"])


class Gate(unittest.TestCase):
    def test_released_against_itself_passes(self):
        code, text = quiet(gate.main, [])
        self.assertEqual(code, 0)
        self.assertIn("noise band 4.1", text)

    def test_agreeable_prompt_fails(self):
        code, text = quiet(gate.main,
                           [str(HERE / "prompt_agreeable.txt")])
        self.assertEqual(code, 1)
        self.assertIn("refund-promise lost a case", text)

    def test_warn_reports_but_exits_zero(self):
        code, text = quiet(gate.main, [str(HERE / "prompt_agreeable"
                                           ".txt"), "--warn"])
        self.assertEqual(code, 0)
        self.assertIn("GATE FAIL (warn only, exit 0)", text)

    def test_dropping_the_refund_line_blocks(self):
        rules = [x for x in load_prompt() if x != REFUND]
        why, _ = quiet(gate.gate, load_prompt(), rules,
                       ev.load_cases())
        self.assertIn("refund-promise lost a case (blocks on any loss)",
                      why)

    def test_noise_band_comes_from_repeats(self):
        per_seed, _ = gate.runs(load_prompt(), ev.load_cases())
        self.assertEqual(len(per_seed), len(gate.SEEDS))
        self.assertGreater(len(set(per_seed)), 1)
        band = max(2 * stdev(per_seed), 1.0)
        _, text = quiet(gate.main, [])
        self.assertIn(f"noise band {band:.1f}", text)


class Task(unittest.TestCase):
    def setUp(self):
        self.new = ev.load_cases(HERE / "solution_cases.jsonl")

    def test_ten_new_cases_from_the_week(self):
        week = {c["id"] for c in ev.load_cases(HERE / "week.jsonl")}
        self.assertEqual(len(self.new), 10)
        self.assertTrue({c["from"] for c in self.new} <= week)

    def test_new_cases_fail_before_and_pass_after(self):
        before = ev.score(self.new, load_prompt())
        after = ev.score(self.new, load_prompt(HERE /
                                               "solution_prompt.txt"))
        self.assertEqual(sum(r["pass"] for r in before), 0)
        self.assertGreaterEqual(sum(r["pass"] for r in after), 8)

    def test_solution_prompt_adds_one_line(self):
        self.assertEqual(load_prompt(HERE / "solution_prompt.txt"),
                         load_prompt() + [CURRENT])

    def test_gate_stays_green_with_seventy_cases(self):
        code, text = quiet(gate.main, [
            str(HERE / "solution_prompt.txt"),
            "--add", str(HERE / "solution_cases.jsonl")])
        self.assertEqual(code, 0)
        self.assertIn("cases 70", text)
        self.assertIn("GATE PASS", text)


class Baseline(unittest.TestCase):
    def setUp(self):
        self.cases = ev.load_cases()
        self.rated = [baseline.rate(self.cases, respond)
                      for _, respond in baseline.RESPONDERS]

    def test_baselines_score_below_the_agent(self):
        agent = sum(r["pass"] for r in ev.score(self.cases,
                                                load_prompt()))
        self.assertEqual(self.rated[2][0], agent)
        self.assertLess(max(r[0] for r in self.rated[:2]), agent)
        _, text = quiet(baseline.main)
        self.assertIn(f"{'agent, released prompt':<26}{agent:>5}", text)

    def test_agreeable_passes_more_but_costs_most(self):
        hand_off, top_hit, released, agreeable = self.rated
        self.assertGreater(agreeable[0], top_hit[0])
        self.assertGreater(agreeable[2], hand_off[2])
        self.assertLess(released[2], min(hand_off[2], top_hit[2]))


if __name__ == "__main__":
    unittest.main()
