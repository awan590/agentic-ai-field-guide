"""Tests for Chapter 14: spans, the five metrics, alerts, and the
tone-drift solution.

Run from code/:  python -m unittest tests.test_ch14
"""
import json
import random
import unittest

from ch02.mini_agent import TOOLS
from ch02.stub_model import StandInModel
from ch14 import alerts
from ch14 import make_days
from ch14 import solution_tone as sol
from ch14 import tracing as tr


def traced(capture=False):
    tracer = tr.Tracer(capture=capture)
    answer = tr.run_traced(StandInModel(tr.SCRIPT), TOOLS, tr.TASK,
                           tracer)
    return answer, tracer.spans


class TracingTest(unittest.TestCase):
    def test_span_names_follow_the_conventions(self):
        _, spans = traced()
        names = [s["name"] for s in spans]
        self.assertEqual(names.count("chat stand-in-1"), 3)
        self.assertEqual(names.count("execute_tool get_order"), 2)
        self.assertEqual(names[-1], "invoke_agent supply-helper")

    def test_model_spans_carry_required_and_usage_fields(self):
        _, spans = traced()
        for s in spans:
            a = s["attributes"]
            self.assertIn("gen_ai.operation.name", a)
            if a["gen_ai.operation.name"] == "chat":
                self.assertEqual(s["kind"], "CLIENT")
                for key in ("gen_ai.provider.name",
                            "gen_ai.request.model",
                            "gen_ai.usage.input_tokens",
                            "gen_ai.usage.output_tokens"):
                    self.assertIn(key, a)

    def test_one_trace_and_one_parent(self):
        _, spans = traced()
        root = spans[-1]
        self.assertEqual({s["trace_id"] for s in spans},
                         {root["trace_id"]})
        for s in spans[:-1]:
            self.assertEqual(s["parent_span_id"], root["span_id"])
            self.assertLessEqual(s["end"], root["end"])

    def test_tool_error_is_marked(self):
        _, spans = traced()
        bad = spans[1]
        self.assertEqual(bad["status"], "ERROR")
        self.assertEqual(bad["attributes"]["error.type"], "tool_error")

    def test_content_is_off_by_default(self):
        _, spans = traced()
        text = json.dumps(spans)
        self.assertNotIn("gen_ai.input.messages", text)
        self.assertNotIn("Where is my order", text)

    def test_captured_content_is_masked(self):
        answer, spans = traced(capture=True)
        text = json.dumps(spans)
        self.assertIn("gen_ai.input.messages", text)
        self.assertNotIn("7700 900", text)
        self.assertNotIn("priya.nair@", text)
        self.assertEqual(answer, "Order A-1003 shows as delivered.")

    def test_summary_matches_the_trace(self):
        _, spans = traced()
        self.assertEqual(tr.summarize(spans),
                         {"ms": 3140, "tok": 621, "err": 1,
                          "handoff": 0})


class AlertsTest(unittest.TestCase):
    def setUp(self):
        self.base = alerts.metrics(alerts.load_day("normal_day"))

    def test_days_are_full(self):
        for name in ("normal_day", "bad_day"):
            self.assertEqual(len(alerts.load_day(name)), 720)

    def test_days_rebuild_from_their_seeds(self):
        for name, text in make_days.build().items():
            saved = (alerts.HERE / name).read_text()
            self.assertEqual(text, saved, name)

    def test_tone_flag(self):
        self.assertTrue(alerts.tone_flag("This store is the WORST."))
        self.assertFalse(alerts.tone_flag("Order A-1005 shipped."))

    def test_normal_day_is_quiet(self):
        day = alerts.load_day("normal_day")
        self.assertEqual(alerts.evaluate(day, alerts.RULES, self.base),
                         [])

    def test_stock_rules_fire_late_on_bad_day(self):
        day = alerts.load_day("bad_day")
        first = alerts.evaluate(day, alerts.RULES, self.base)[0]
        self.assertEqual((first["time"], first["rule"]),
                         ("18:20", "handoff drift"))

    def test_min_count_stops_a_single_error(self):
        rule = {"name": "x", "metric": "errors", "over": 0.0,
                "min_count": 3, "severity": "page"}
        day = [{"t": alerts.clock(m), "ms": 1000, "tok": 1, "err": 0,
                "handoff": 0, "reply": "ok"} for m in range(0, 1440, 2)]
        day[30]["err"] = 1
        self.assertEqual(alerts.evaluate(day, [rule], self.base), [])

    def test_tail_sampling_keeps_every_flag(self):
        rng = random.Random(1)
        day = alerts.load_day("bad_day")
        kept = [e for e in day if alerts.keep(e, rng)]
        flags = [e for e in day if alerts.tone_flag(e["reply"])]
        self.assertTrue(all(e in kept for e in flags))
        self.assertLess(len(kept), len(day) // 4)

    def test_eval_case_has_the_ch12_fields(self):
        event = {"t": "14:04", "ask": "Swear at me.", "reply": "x"}
        case = alerts.eval_case(event, 1)
        self.assertEqual(set(case), {"id", "from", "kind", "message",
                                     "must", "must_not"})


class SolutionTest(unittest.TestCase):
    def test_tone_rule_fires_first_on_bad_day(self):
        found = sol.fires("bad_day", alerts.RULES + [sol.TONE_RULE])
        self.assertEqual((found[0]["time"], found[0]["rule"]),
                         ("14:50", "tone drift"))
        self.assertLess(alerts.minute(found[0]["time"]), 18 * 60)

    def test_tone_rule_is_quiet_on_normal_day(self):
        found = sol.fires("normal_day", alerts.RULES + [sol.TONE_RULE])
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
