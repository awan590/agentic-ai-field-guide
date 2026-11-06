"""Tests for Chapter 25: the trend radar, the task exchange, the
skills plan, and the horizon check on your own tasks.

Run from code/:  python -m unittest tests.test_ch25
"""
import copy
import inspect
import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date
from ch25 import a2a_demo as a2a
from ch25 import horizon as hz
from ch25 import radar as rd
from ch25 import solution_plan as sol

RADAR = rd.load(rd.RADAR)
ON = date.fromisoformat(RADAR["as_of"])


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()):
        return fn(*args)


class RadarTest(unittest.TestCase):
    def test_every_entry_has_a_source_and_dates(self):
        self.assertEqual(rd.problems(RADAR), [])

    def test_one_entry_is_stale_on_the_as_of_date(self):
        old = [e["id"] for e in RADAR["entries"] if rd.stale(e, ON)]
        self.assertEqual(old, ["computer-use"])

    def test_day_90_is_fresh_and_day_91_is_stale(self):
        e = {"read": "2026-11-04"}
        self.assertFalse(rd.stale(e, date(2027, 2, 2)))
        self.assertTrue(rd.stale(e, date(2027, 2, 3)))

    def test_next_quarter_every_entry_is_stale(self):
        on = date(2027, 2, 5)
        self.assertTrue(all(rd.stale(e, on) for e in RADAR["entries"]))

    def test_bad_entries_are_named(self):
        radar = copy.deepcopy(RADAR)
        es = radar["entries"]
        del es[0]["source"]
        es[1]["ring"] = "adopt"
        es[2]["read"] = "2024-01-01"
        es[3]["published"] = "2025-13-01"
        es[4]["url"] = "http://example.com"
        self.assertEqual(rd.problems(radar), [
            "mcp-tools: no source",
            "eu-ai-act: ring adopt not in ('use', 'try', 'watch', "
            "'hold')",
            "computer-use: read before published",
            "agent-memory: bad published '2025-13-01'",
            "small-models: url is not https"])

    def test_report_counts_the_stale_entries(self):
        lines = rd.report(RADAR, ON)
        self.assertEqual(lines[-1], "1 of 10 entries stale: read them "
                         "again before you plan on them.")
        self.assertEqual(sum("STALE" in x for x in lines), 1)


class ExchangeTest(unittest.TestCase):
    def setUp(self):
        self.wire, self.agent = a2a.run(out=lambda line: None)

    def test_first_task_asks_then_completes(self):
        t = self.agent.tasks["t-001"]
        self.assertEqual(t["history"], [
            "submitted", "working", "input-required", "working",
            "completed"])
        self.assertEqual(t["artifacts"][0]["label"], "RL-A-1001")

    def test_unknown_skill_is_rejected_and_terminal(self):
        t = self.agent.tasks["t-002"]
        self.assertEqual(t["state"], "rejected")
        self.assertIn(t["state"], a2a.DONE)
        self.assertNotIn(t["state"], a2a.MOVES)

    def test_every_message_is_json_with_the_format_tag(self):
        self.assertEqual(len(self.wire.sent), 8)
        for text in self.wire.sent:
            self.assertEqual(json.loads(text)["format"], a2a.FORMAT)

    def test_a_finished_task_cannot_move_again(self):
        t = self.agent.tasks["t-001"]
        with self.assertRaises(ValueError):
            a2a.move(t, "working")

    def test_a_skipped_step_is_refused(self):
        t = {"id": "t-9", "state": "submitted", "history": []}
        with self.assertRaises(ValueError):
            a2a.move(t, "completed")

    def test_old_or_missing_orders_fail(self):
        agent = a2a.ReturnsAgent()
        notes = []
        for order in ("A-9999", "A-0777"):
            t = {"id": order, "state": "working", "history": [],
                 "artifacts": []}
            agent.work(t, {"order": order})
            self.assertEqual(t["state"], "failed")
            notes.append(t["note"])
        self.assertEqual(notes, ["order A-9999 not found",
                                 "outside the 30-day window"])

    def test_no_network_module_is_imported(self):
        src = inspect.getsource(a2a)
        for name in ("socket", "http", "urllib", "requests"):
            self.assertNotIn(f"import {name}", src)


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.plan = sol.write(RADAR, rd.TODAY)

    def test_the_starter_plan_passes(self):
        self.assertEqual(sol.check(self.plan, RADAR), [])
        self.assertEqual(self.plan.count("## Q"), 4)

    def test_a_stale_entry_fails(self):
        plan = self.plan.replace("agent-memory", "computer-use")
        self.assertEqual(sol.check(plan, RADAR), [
            "Q3: computer-use is stale on 2026-11-04; read it again"])

    def test_an_entry_on_hold_fails(self):
        plan = self.plan.replace("small-models", "agent-payments")
        self.assertEqual(sol.check(plan, RADAR),
                         ["Q4: agent-payments is on hold"])

    def test_an_unknown_entry_fails(self):
        plan = self.plan.replace("mcp-tools", "quantum")
        self.assertEqual(sol.check(plan, RADAR),
                         ["Q1: quantum is not on the radar"])

    def test_a_missing_quarter_fails(self):
        plan = self.plan.replace("## Q4", "## Later")
        self.assertIn("want four quarters, ## Q1 to ## Q4, in order",
                      sol.check(plan, RADAR))

    def test_a_gap_over_90_days_fails(self):
        plan = self.plan.replace("Review: 2027-05-03",
                                 "Review: 2027-05-04")
        self.assertEqual(sol.check(plan, RADAR), [
            "Q2: review 2027-05-04 is not within 90 days after "
            "2027-02-02"])

    def test_proof_must_name_a_test_eval_or_log(self):
        plan = self.plan.replace("one eval case per release, logged",
                                 "I will read about it", 1)
        self.assertEqual(sol.check(plan, RADAR),
                         ["Q1: proof names no test, eval, or log"])

    def test_check_command_prints_the_verdict(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = sol.main(["check", __file__])
        self.assertEqual(code, 1)
        self.assertTrue(out.getvalue().endswith("PLAN FAIL\n"))


class HorizonTest(unittest.TestCase):
    def setUp(self):
        self.cols = hz.table(hz.load(hz.TASKS))

    def test_tasks_fall_in_the_right_group(self):
        self.assertEqual(hz.bucket(15), "up to 15 min")
        self.assertEqual(hz.bucket(16), "15 to 60 min")
        self.assertEqual(hz.bucket(240), "1 to 4 hours")
        self.assertEqual(hz.bucket(241), "over 4 hours")

    def test_horizon_moves_up_one_group(self):
        self.assertEqual(hz.horizon(self.cols["2026-Q3"]),
                         "15 to 60 min")
        self.assertEqual(hz.horizon(self.cols["2026-Q4"]),
                         "1 to 4 hours")

    def test_exactly_half_counts_and_no_tasks_is_none(self):
        self.assertEqual(hz.horizon({"over 4 hours": [1, 2]}),
                         "over 4 hours")
        self.assertEqual(hz.horizon({}), "none")

    def test_report_runs(self):
        self.assertEqual(quiet(hz.main, []), 0)

    def test_a_group_of_one_says_1_task(self):
        lines = hz.report([("2026-Q4", 30.0, True)])
        self.assertEqual(lines[-1], "Smallest group: 1 task, so one "
                         "task moves its rate 100 points.")


class RecheckTest(unittest.TestCase):
    def setUp(self):
        self.new = [e for e in RADAR["entries"]
                    if e["read"] == RADAR["as_of"]]

    def test_three_entries_were_read_again_on_the_as_of_date(self):
        self.assertEqual([e["id"] for e in self.new], [
            "a2a-tasks", "agent-payments", "acp-versions"])

    def test_no_entry_is_read_after_the_as_of_date(self):
        self.assertTrue(all(rd.age(e, ON) >= 0
                            for e in RADAR["entries"]))

    def test_rechecked_entries_name_the_new_releases(self):
        got = {e["id"]: (e["source"], e["published"]) for e in self.new}
        self.assertEqual(got, {
            "a2a-tasks": ("S1349", "2026-05-28"),
            "agent-payments": ("S1352", "2026-04-28"),
            "acp-versions": ("S1354", "2026-04-17")})

    def test_rechecked_entries_go_stale_after_day_90(self):
        for e in self.new:
            self.assertFalse(rd.stale(e, date(2027, 2, 4)))
            self.assertTrue(rd.stale(e, date(2027, 2, 5)))

    def test_acp_on_hold_fails_in_a_plan(self):
        plan = sol.write(RADAR, ON).replace("small-models",
                                            "acp-versions")
        self.assertEqual(sol.check(plan, RADAR),
                         ["Q4: acp-versions is on hold"])


if __name__ == "__main__":
    unittest.main()
