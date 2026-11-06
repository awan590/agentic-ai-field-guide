"""Tests for Chapter 8: the five patterns, the comparison, the task.

Run from code/:  python -m unittest tests.test_ch08
"""
import io
import json
import unittest
from contextlib import redirect_stdout

from ch03.cost_per_task import load_prices
from ch08 import compare
from ch08 import patterns as pt
from ch08 import solution_returns as sol


def model(**replies):
    """A stand-in whose steps echo, unless a reply is given."""
    return pt.StandIn(dict({"up": str.upper, "echo": str}, **replies))


def run_all(design):
    return compare.evaluate(design, compare.labeled_cases(),
                            load_prices())


class StandInTest(unittest.TestCase):
    def test_each_call_counts_tokens_and_time(self):
        m = model()
        self.assertEqual(m.ask("up", "abc"), "ABC")
        self.assertEqual(len(m.calls), 1)
        self.assertGreater(m.calls[0]["input"], 0)
        self.assertGreater(m.clock, pt.CALL_SECONDS)


class ChainAndRouterTest(unittest.TestCase):
    def test_chain_feeds_each_step_the_last_output(self):
        m = model()
        self.assertEqual(pt.chain([m.step("up"), str.strip], " a "),
                         "A")

    def test_failed_gate_stops_before_the_next_call(self):
        m = model()
        out = pt.chain([m.step("echo"), lambda t: None,
                        m.step("up")], "x")
        self.assertIsNone(out)
        self.assertEqual([c["step"] for c in m.calls], ["echo"])

    def test_check_order_refuses_a_missing_order(self):
        facts = '{"order_id": "A-1O03", "problem": "damaged"}'
        self.assertIsNone(pt.check_order(facts))
        self.assertIn("delivered", pt.check_order(
            facts.replace("A-1O03", "A-1003")))

    def test_unknown_label_takes_the_other_path(self):
        m = model(classify=lambda text: "weather")
        handlers = {"other": lambda text: "person"}
        self.assertEqual(pt.route(m, "hi", handlers),
                         ("weather", "person"))


class ParallelTest(unittest.TestCase):
    def test_parallel_waits_for_the_slowest_only(self):
        m = model(long=lambda text: "word " * 50)
        outs = pt.parallel(m, [("echo", "a"), ("long", "b")])
        self.assertEqual(outs[0], "a")
        one_by_one = sum(pt.CALL_SECONDS + pt.TOKEN_SECONDS
                         * c["output"] for c in m.calls)
        self.assertLess(m.clock, one_by_one)
        slowest = pt.CALL_SECONDS + pt.TOKEN_SECONDS * max(
            c["output"] for c in m.calls)
        self.assertAlmostEqual(m.clock, slowest)

    def test_vote_keeps_the_majority(self):
        m = pt.StandIn(pt.REPLIES)
        winner, answers = pt.vote(m, "flag", "Refund?", n=3)
        self.assertEqual((winner, answers), ("yes", ["yes", "no",
                                                     "yes"]))
        self.assertEqual(len(m.calls), 3)

    def test_a_split_vote_returns_the_first_answer(self):
        m = model(flag=lambda text: "bac"[int(text[-2])])
        winner, answers = pt.vote(m, "flag", "Refund?", n=3)
        self.assertEqual((winner, answers), ("b", ["b", "a", "c"]))


class OrchestratorEvaluatorTest(unittest.TestCase):
    def test_plan_sets_the_number_of_workers(self):
        m = pt.StandIn(pt.REPLIES)
        plan, answer = pt.orchestrate(
            m, "A-1001 is late, and A-1003 is cracked, and A-1005?")
        self.assertEqual(len(plan), 3)
        self.assertEqual(len(m.calls), 1 + 3 + 1)
        self.assertIn("A-1003 is delivered", answer)

    def test_a_part_with_two_orders_drops_the_second(self):
        m = pt.StandIn(dict(pt.REPLIES,
                            plan=lambda text: json.dumps([text])))
        plan, answer = pt.orchestrate(
            m, "Order A-1003 came cracked, and A-1005 has not arrived")
        self.assertEqual(len(plan), 1)
        self.assertEqual(answer, "A-1003 is delivered.")

    def test_grader_passes_a_reply_about_the_wrong_order(self):
        m = pt.StandIn(pt.REPLIES)
        wrong = ("Sorry, A-1005 came cracked. "
                 "A person will approve a refund.")
        self.assertEqual(m.ask("grade", wrong), "PASS")

    def test_refine_stops_on_pass(self):
        m = pt.StandIn(pt.REPLIES)
        draft, rounds, passed = pt.refine(m, pt.CRACKED)
        self.assertTrue(passed)
        self.assertEqual(rounds, 2)
        self.assertIn("A-1003", draft)

    def test_refine_stops_at_the_cap(self):
        m = model(draft=str, grade=lambda d: "FIX: again",
                  revise=lambda pair: "new")
        _draft, rounds, passed = pt.refine(m, "x", max_rounds=3)
        self.assertEqual((rounds, passed), (3, False))
        steps = [c["step"] for c in m.calls]
        self.assertEqual(steps.count("grade"), 3)
        self.assertEqual(steps.count("revise"), 2)

    def test_demo_output_never_changes(self):
        outs = []
        for _ in range(2):
            buf = io.StringIO()
            with redirect_stdout(buf):
                pt.main([])
            outs.append(buf.getvalue())
        self.assertEqual(outs[0], outs[1])
        self.assertIn("typo: stopped at the gate", outs[0])


class CasesAndPolicyTest(unittest.TestCase):
    def test_case_set_shape(self):
        cases = compare.labeled_cases()
        self.assertEqual(len(cases), 64)
        self.assertEqual(sum(c["odd"] for c in cases), 16)
        self.assertEqual(len({c["id"] for c in cases}), 64)

    def test_policy_refunds_only_delivered_orders(self):
        shipped = {"status": "shipped"}
        self.assertEqual(compare.policy("refund", shipped), "status")
        self.assertEqual(compare.policy("refund",
                                        {"status": "delivered"}),
                         "refund")

    def test_rule_router_costs_nothing(self):
        cases = {c["text"]: c for c in compare.labeled_cases()}
        run = compare.Run(load_prices())
        bent = cases["The parts in order A-1003 came bent. I want "
                     "my money back."]
        self.assertEqual(compare.rule_router(bent, run), "other")
        where = cases["Where is order A-1001?"]
        self.assertEqual(compare.rule_router(where, run), "status")
        self.assertEqual(run.dollars, 0.0)


class CompareTest(unittest.TestCase):
    def test_workflow_never_refunds_an_undelivered_order(self):
        always = (lambda case, run: "refund")
        for case in compare.labeled_cases():
            run = compare.Run(load_prices())
            action = compare.workflow(case, always, run)
            status = compare.ORDERS[case["order"]]["status"]
            if status != "delivered":
                self.assertNotEqual(action, "refund", case["text"])

    def test_odd_cases_take_the_escape_hatch(self):
        odd = [c for c in compare.labeled_cases() if c["odd"]]
        run = compare.Run(load_prices())
        actions = {compare.workflow(c, compare.rule_router, run)
                   for c in odd}
        self.assertEqual(actions, {"person"})

    def test_step_cap_sends_the_agent_to_a_person(self):
        case = compare.labeled_cases()[0]
        run = compare.Run(load_prices())
        self.assertEqual(compare.agent(case, run, max_steps=1),
                         "person")
        self.assertGreater(run.dollars, 0)

    def test_numbers_in_the_chapter(self):
        flow = run_all(lambda c, r: compare.workflow(
            c, compare.model_router, r))
        free = run_all(compare.agent)
        self.assertEqual((flow["right"], flow["wrong"],
                          flow["person"]), (55, 1, 8))
        self.assertEqual((free["right"], free["wrong"],
                          free["person"]), (61, 3, 0))
        self.assertGreater(free["cost"], 100 * flow["cost"])
        self.assertGreater(free["seconds"], 3 * flow["seconds"])


class SolutionTest(unittest.TestCase):
    def test_hybrid_meets_the_targets_with_either_router(self):
        free = run_all(compare.agent)
        for router in (compare.model_router, compare.rule_router):
            mixed = run_all(sol.hybrid(router))
            share, ok = sol.check(free, mixed)
            self.assertTrue(ok, router.__name__)
            self.assertLess(share, sol.MAX_SHARE)
            self.assertEqual(mixed["person"], 0)

    def test_routine_cases_never_reach_the_agent(self):
        routine = [c for c in compare.labeled_cases()
                   if not c["odd"] and c["label"] == "status"]
        prices = load_prices()
        for case in routine:
            run = compare.Run(prices)
            sol.hybrid(compare.rule_router)(case, run)
            self.assertLess(run.dollars, 0.0001, case["text"])


if __name__ == "__main__":
    unittest.main()
