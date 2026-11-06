"""Tests for Chapter 10: the harness, the skills, the time study.

Run from code/:  python -m unittest tests.test_ch10
"""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ch10 import harness_min as hm
from ch10 import skill_check as sc
from ch10 import solution_skill as sol
from ch10 import time_study as ts

HANG = {"plan": "loop forever", "file": "refunds.py",
        "old": "    if opened:", "new": "    while opened:\n"
        "        pass\n    if opened:"}


def run(script, skill="refund_fix", cap=hm.TIME_CAP):
    model = hm.StandInModel(script)
    ok, trace = hm.fix(hm.load_skill(skill), model, cap=cap)
    return ok, trace, model


def kinds(trace):
    return [k for k, _ in trace]


class HarnessTest(unittest.TestCase):
    def test_fixes_the_refund_test_on_the_second_try(self):
        ok, trace, _ = run(hm.SCRIPTS["fix"])
        self.assertTrue(ok)
        self.assertEqual(kinds(trace).count("plan"), 2)
        self.assertEqual(kinds(trace)[-1], "diff")
        self.assertIn("+    if opened and not damaged:", trace[-1][1])
        self.assertNotIn("RESTOCK_PERCENT = 0", trace[-1][1])

    def test_original_repository_is_never_touched(self):
        before = hm.fingerprint(hm.REPO)
        for script in hm.SCRIPTS.values():
            run(script)
        self.assertEqual(hm.fingerprint(hm.REPO), before)
        text = (hm.REPO / "refunds.py").read_text()
        self.assertIn("    if opened:\n", text)      # bug still there

    def test_model_sees_the_failure_and_the_notes(self):
        _, _, model = run(hm.SCRIPTS["fix"])
        first, second = model.seen
        self.assertIn("FAIL: test_damaged_item", first[0])
        self.assertEqual(first[1], [])
        self.assertEqual(second[1], ["drop the restocking fee: "
                                     "FAILED (failures=1)"])

    def test_hook_blocks_a_path_out_of_the_sandbox(self):
        ok, trace, _ = run(hm.SCRIPTS["escape"])
        self.assertTrue(ok)
        self.assertIn(("blocked", "../refunds.py: outside the sandbox"),
                      trace)

    def test_hooks_block_absolute_and_unlisted_paths(self):
        skill = hm.load_skill("refund_fix")
        with tempfile.TemporaryDirectory() as tmp:
            box = Path(tmp)
            (box / "shipping.py").write_text("x = 1\n")
            target = hm.REPO / "refunds.py"
            for name in (str(target), "shipping.py"):
                patch = dict(hm.FEE_OFF, file=name)
                with self.assertRaises(hm.Blocked):
                    hm.edit(box, skill, patch)
            self.assertEqual((box / "shipping.py").read_text(),
                             "x = 1\n")

    def test_try_cap_stops_the_loop_and_hands_off(self):
        ok, trace, _ = run([hm.FEE_OFF] * 5)
        self.assertFalse(ok)
        self.assertEqual(kinds(trace).count("plan"), 3)
        self.assertEqual(kinds(trace)[-1], "handoff")
        self.assertEqual(kinds(trace).count("revert"), 3)

    def test_time_cap_stops_a_hanging_test_run(self):
        ok, trace, _ = run([HANG], cap=1)
        self.assertFalse(ok)
        self.assertIn(("test", "STOPPED at the 1 s time cap"), trace)

    def test_test_run_gets_an_empty_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "test_env.py").write_text(
                "import os\nimport unittest\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_no_home(self):\n"
                "        self.assertNotIn('HOME', os.environ)\n")
            ok, out = hm.run_tests(Path(tmp), ["test_env"])
        self.assertTrue(ok, out)

    def test_bare_model_patch_is_never_run(self):
        out = io.StringIO()
        with redirect_stdout(out):
            hm.main(["bare"])
        self.assertIn("tests: never run", out.getvalue())


class SkillTest(unittest.TestCase):
    def test_skill_file_gives_settings_and_steps(self):
        skill = hm.load_skill("refund_fix")
        self.assertEqual(skill["name"], "refund-fix")
        self.assertEqual(skill["files"], ["refunds.py"])
        self.assertEqual(skill["tests"], ["test_refunds"])
        self.assertEqual(skill["cap"], 3)
        self.assertEqual([t for t, _ in skill["steps"]],
                         ["sandbox", "test-first", "one-edit",
                          "test-after", "cap", "approval"])

    def test_harness_run_follows_every_step(self):
        skill = hm.load_skill("refund_fix")
        _, trace, _ = run(hm.SCRIPTS["fix"])
        self.assertEqual(sc.check(skill, trace),
                         [(t, True) for t, _ in skill["steps"]])

    def test_check_catches_a_run_that_breaks_the_steps(self):
        skill = hm.load_skill("refund_fix")
        bad = [("plan", "x"), ("edit", "refunds.py"),
               ("edit", "refunds.py"), ("test", "OK"), ("push", "")]
        failed = [t for t, ok in sc.check(skill, bad) if not ok]
        self.assertEqual(failed, ["sandbox", "test-first", "one-edit",
                                  "test-after", "approval"])

    def test_unknown_tag_fails(self):
        skill = {"steps": [("guess", "do it")], "cap": 1}
        self.assertEqual(sc.check(skill, [("sandbox", "")]),
                         [("guess", False)])


class TimeStudyTest(unittest.TestCase):
    def test_sample_log_says_it_is_invented(self):
        self.assertTrue(ts.LOG.read_text().startswith(
            "# SAMPLE DATA: invented rows"))

    def test_sample_log_report(self):
        s = ts.study(ts.read())
        self.assertEqual(s["n"], {"agent": 17, "none": 14})
        self.assertEqual(s["skips"], {"agent": 0, "none": 1})
        self.assertAlmostEqual(s["measured"], 0.161, places=3)
        self.assertAlmostEqual(s["reported"], -0.198, places=3)
        self.assertGreater(s["interval"][0], 0)
        self.assertEqual(ts.verdict(s),
                         "slower with the agent, as measured")

    def test_log_task_uses_the_coin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "log.csv")
            path.write_text("task,arm,minutes,guess_without\n")
            ts.log_task(path, "T33", 40, 50)
            ts.log_task(path, "T02", "")
            rows = ts.read(path)
        self.assertEqual([r["arm"] for r in rows], ["agent", "none"])
        self.assertEqual(rows[1]["minutes"], "")

    def test_row_with_a_hand_picked_arm_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "log.csv")
            path.write_text("task,arm,minutes,guess_without\n"
                            "T02,agent,30,45\n")
            with self.assertRaises(ValueError):
                ts.read(path)

    def test_few_tasks_give_no_verdict(self):
        s = {"n": {"agent": 9, "none": 12}, "interval": (0.1, 0.2)}
        self.assertTrue(ts.verdict(s).startswith("too few tasks"))

    def test_interval_repeats_with_its_seed(self):
        a, b = [50.0, 60.0, 55.0], [40.0, 45.0, 50.0]
        self.assertEqual(ts.interval(a, b), ts.interval(a, b))

    def test_own_log_reports_without_the_sample_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "my_log.csv")
            out = io.StringIO()
            with redirect_stdout(out):
                ts.main(["log", str(path), "T33", "41", "55"])
                ts.main(["log", str(path), "T35", "30"])
                ts.main([str(path)])
        self.assertIn("T35: none, logged in", out.getvalue())
        self.assertNotIn("SAMPLE DATA", out.getvalue())
        self.assertIn("finished: 1 with the agent, 1 without",
                      out.getvalue())
        self.assertIn("verdict: too few tasks", out.getvalue())


class SolutionTest(unittest.TestCase):
    def test_shipping_skill_works_and_every_step_passes(self):
        out = io.StringIO()
        with redirect_stdout(out):
            ok = sc.report("shipping_fix", sol.SCRIPT)
        self.assertTrue(ok)
        self.assertIn("hook blocked refunds.py: not a file the skill "
                      "lists", out.getvalue())
        self.assertNotIn("FAIL ", out.getvalue())

    def test_shipping_fix_leaves_the_original_alone(self):
        before = hm.fingerprint(hm.REPO)
        ok, trace, _ = run(sol.SCRIPT, skill="shipping_fix")
        self.assertTrue(ok)
        self.assertIn("+    if subtotal >= FREE_FROM:", trace[-1][1])
        self.assertEqual(hm.fingerprint(hm.REPO), before)


class RulesTest(unittest.TestCase):
    PARTS = ["## Requirements", "## Technical decisions",
             "## Standards", "## Test strategy", "## Lessons"]

    def test_rules_file_has_the_five_parts(self):
        lines = hm.RULES.read_text().splitlines()
        heads = [x for x in lines if x.startswith("## ")]
        self.assertEqual(heads, self.PARTS)
        self.assertLess(len(lines), 60)

    def test_every_prompt_carries_the_rules(self):
        rules = hm.load_rules()
        model = hm.StandInModel(hm.SCRIPTS["fix"])
        ok, _ = hm.fix(hm.load_skill("refund_fix"), model, rules=rules)
        self.assertTrue(ok)
        self.assertEqual(model.seen[0][2], hm.RULES.read_text())
        self.assertTrue(all(s[2] == rules for s in model.seen))
        out = io.StringIO()
        with redirect_stdout(out):
            hm.main(["fix"])
        n = len(rules.splitlines())
        self.assertIn(f"rules: AGENTS.md ({n} lines)", out.getvalue())

    def test_oversized_rules_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENTS.md"
            self.assertEqual(hm.load_rules(path), "")
            path.write_text("- one rule\n" * 201)
            with self.assertRaises(ValueError) as why:
                hm.load_rules(path)
        self.assertIn("201 lines, over the 200-line cap",
                      str(why.exception))


if __name__ == "__main__":
    unittest.main()
