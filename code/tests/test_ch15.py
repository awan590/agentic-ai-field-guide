"""Tests for Chapter 15: caps, the kill switch, the fallback chain,
the circuit breaker, and the policy-answer guard.

Run from code/:  python -m unittest tests.test_ch15
"""
import unittest

from ch02.mini_agent import TOOLS, tool
from ch02.store import get_order
from ch02.stub_model import StandInModel
from ch15 import budget_guard as bg
from ch15 import fallbacks as fb
from ch15 import solution_policy as sol

LOOKUP = {"tool_calls": [bg.lookup("A-1002")]}


def orders_tool(fn):
    return {"get_order": tool(fn, "Look up one order by id.",
                              order_id={"type": "string"})}


def guarded(tools, script, clock=None, kill=None, caps=bg.CAPS):
    return bg.run_guarded(StandInModel(script), tools, "Has A-1002"
                          " shipped?", clock or bg.SimClock(),
                          kill or bg.KillSwitch(), caps)


class CleanHandoff:
    def assertHandoff(self, out, reason):
        self.assertIsNone(out.get("answer"))
        self.assertEqual(out["handoff"].receiver, "person")
        self.assertIn(reason, out["handoff"].reason)
        self.assertEqual(out["reply"], bg.HANDOFF_REPLY)


class BudgetTest(CleanHandoff, unittest.TestCase):
    def test_normal_run_is_done_with_no_handoff(self):
        out = guarded(TOOLS, [LOOKUP, {"content": "Processing."}])
        self.assertEqual(out["stop"], "done")
        self.assertNotIn("handoff", out)
        self.assertEqual(out["seconds"], 4.0)

    def test_step_cap(self):
        out = guarded(TOOLS, [LOOKUP] * 20)
        self.assertEqual(out["steps"], 8)
        self.assertHandoff(out, "step cap")

    def test_token_cap(self):
        caps = dict(bg.CAPS, max_tokens=150)
        out = guarded(TOOLS, [LOOKUP] * 20, caps=caps)
        self.assertGreaterEqual(out["tokens"], 150)
        self.assertHandoff(out, "token cap")

    def test_slow_tool_times_out_then_time_cap(self):
        clock = bg.SimClock()
        tools = orders_tool(bg.slow(clock, get_order, 9.0))
        out = guarded(tools, [LOOKUP] * 20, clock)
        errors = [e["result"]["error"] for e in out["trace"]
                  if e["event"] == "tool_result"]
        self.assertEqual(errors, ["timeout: get_order over 5 s"] * 3)
        self.assertHandoff(out, "time cap")

    def test_kill_switch_stops_the_next_tool_call(self):
        clock, kill = bg.SimClock(), bg.KillSwitch()
        clock.at(5.0, lambda: kill.pull("operator"))
        out = guarded(TOOLS, [LOOKUP] * 20, clock, kill)
        made = [e for e in out["trace"] if e["event"] == "tool_result"
                and "error" not in e["result"]]
        self.assertEqual(len(made), 2)
        self.assertHandoff(out, "kill switch: operator")

    def test_stop_file_flips_the_switch(self):
        self.assertFalse(bg.KillSwitch("no/such/stop-file").pulled())
        self.assertTrue(bg.KillSwitch(bg.__file__).pulled())
        out = guarded(TOOLS, [LOOKUP], kill=bg.KillSwitch(bg.__file__))
        self.assertEqual(out["steps"], 0)
        self.assertHandoff(out, "stop file")


class InjectedFaultTest(CleanHandoff, unittest.TestCase):
    def test_orders_api_down_ends_in_handoff(self):
        clock = bg.SimClock()
        tools = orders_tool(fb.down_until(clock, get_order, 999.0))
        out = guarded(tools, [LOOKUP] * 20, clock)
        last = [e for e in out["trace"] if e["event"] == "tool_result"]
        self.assertIn("unreachable", last[-1]["result"]["error"])
        self.assertHandoff(out, "cap")

    def test_every_injected_fault_reaches_a_person(self):
        faults = {"down": lambda c: fb.down_until(c, get_order, 999),
                  "slow": lambda c: bg.slow(c, get_order, 9.0)}
        for name, make in faults.items():
            with self.subTest(fault=name):
                clock = bg.SimClock()
                out = guarded(orders_tool(make(clock)), [LOOKUP] * 20,
                              clock)
                self.assertGreater(out["steps"], 0)
                self.assertHandoff(out, "cap")


class BreakerTest(unittest.TestCase):
    def setUp(self):
        self.clock = bg.SimClock()
        self.calls = 0

    def api(self, until):
        flaky = fb.down_until(self.clock, get_order, until)

        def counted(*args):
            self.calls += 1
            return flaky(*args)
        return counted

    def test_opens_after_threshold_and_stops_calling(self):
        br, api = fb.CircuitBreaker("orders", self.clock), self.api(99)
        for _ in range(3):
            br.call(api, "A-1002")
        self.assertEqual(br.state, "open")
        out = br.call(api, "A-1002")
        self.assertEqual(out, {"error": "orders breaker open"})
        self.assertEqual(self.calls, 3)

    def test_half_open_trial_closes_on_success(self):
        br, api = fb.CircuitBreaker("orders", self.clock), self.api(20)
        for _ in range(3):
            br.call(api, "A-1002")
        self.clock.advance(30.0)
        self.assertEqual(br.call(api, "A-1002")["status"], "processing")
        self.assertEqual([s[2] for s in br.log],
                         ["open", "half-open", "closed"])

    def test_half_open_failure_opens_again(self):
        br, api = fb.CircuitBreaker("orders", self.clock), self.api(99)
        for _ in range(3):
            br.call(api, "A-1002")
        self.clock.advance(30.0)
        br.call(api, "A-1002")
        self.assertEqual(br.state, "open")
        self.assertEqual(br.opened, 30.0)

    def test_data_errors_do_not_trip_it(self):
        br = fb.CircuitBreaker("orders", self.clock)
        for _ in range(5):
            out = br.call(get_order, "A-9999")
        self.assertIn("no order", out["error"])
        self.assertEqual(br.state, "closed")


class ChainTest(unittest.TestCase):
    def rungs(self, *dead):
        names = ["main model", "small model"]
        rungs = [(n, fb.down(n) if n in dead else fb.stand_in(n))
                 for n in names]
        return rungs + [("rule", fb.rule)]

    def test_order_of_rungs(self):
        record = get_order("A-1002")
        self.assertEqual(fb.run_chain(self.rungs(), "t", record)["by"],
                         "main model")
        out = fb.run_chain(self.rungs("main model"), "t", record)
        self.assertEqual(out["by"], "small model")
        both = self.rungs("main model", "small model")
        out = fb.run_chain(both, "t", record)
        self.assertEqual(out["by"], "rule")
        self.assertEqual(len(out["tried"]), 2)

    def test_no_record_goes_to_a_person_not_a_model(self):
        out = fb.run_chain(self.rungs(), "Has A-1002 shipped?",
                           {"error": "orders breaker open"})
        self.assertEqual(out["by"], "person")
        self.assertEqual(out["handoff"].receiver, "person")
        self.assertIn("breaker open", out["handoff"].reason)


class PolicyGuardTest(unittest.TestCase):
    def test_supported_answer_passes(self):
        q, draft = sol.CASES[0]
        self.assertEqual(sol.guard_policy(q, draft), {"answer": draft})

    def test_unknown_policy_goes_to_a_person(self):
        for q, draft in sol.CASES[1:]:
            with self.subTest(q=q):
                out = sol.guard_policy(q, draft)
                self.assertNotIn("answer", out)
                self.assertEqual(out["handoff"].receiver, "person")

    def test_citation_not_retrieved_goes_to_a_person(self):
        out = sol.guard_policy("Can I cancel an order?",
                               "Refunds take five days [refunds#9].")
        self.assertIn("not retrieved", out["handoff"].reason)


if __name__ == "__main__":
    unittest.main()
