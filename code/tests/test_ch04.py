"""Tests for Chapter 4: guarded tools. Offline; nothing waits."""
import unittest

from ch02.mini_agent import run_agent
from ch02.store import ORDERS
from ch02.stub_model import StandInModel
from ch04.payments import Busy, FakeClock, Payments
from ch04.solution_cancel import cancel_tool
from ch04.tools import (AMOUNT, ORDER_ID, Guard, OrderDesk, Tool,
                        classify_failure, make_tools, validate)

REFUND = {"order_id": "A-1003", "amount": 12.65, "reason": "damaged"}


def build(script=(), approver=None, cancel=False, seed=7):
    clock = FakeClock()
    desk = OrderDesk(Payments(clock, script))
    tools = make_tools(desk)
    if cancel:
        tools.append(cancel_tool(desk))
    return desk, Guard(tools, clock, seed=seed, approver=approver)


class Approver:
    """A scripted person: records each preview, answers yes or no."""

    def __init__(self, answer=True):
        self.answer, self.seen = answer, []

    def __call__(self, name, args, preview):
        self.seen.append((name, preview))
        return self.answer


class SchemaTest(unittest.TestCase):
    def setUp(self):
        _, guard = build()
        self.schema = guard.tools["issue_refund"].params

    def test_good_arguments_pass(self):
        self.assertEqual(validate(self.schema, REFUND), [])

    def test_each_kind_of_bad_argument_has_a_fix(self):
        cases = [
            ({"order_id": "A-1O03"}, "does not fit"),
            ({"amount": "12.65"}, "as a number"),
            ({"amount": True}, "as a number"),
            ({"amount": 0}, "0.01 or more"),
            ({"reason": "broke"}, "one of: damaged"),
            ({"approved": True}, "Remove approved"),
        ]
        for change, words in cases:
            problems = validate(self.schema, {**REFUND, **change})
            self.assertEqual(len(problems), 1, change)
            self.assertIn(words, problems[0])
        missing = validate(self.schema, {"order_id": "A-1003"})
        self.assertEqual(len(missing), 2)
        self.assertTrue(missing[0].startswith("Add amount."))

    def test_bad_arguments_never_reach_the_api(self):
        desk, guard = build()
        out = guard.call("issue_refund", {**REFUND, "amount": "9"})
        self.assertIn("fix", out)
        self.assertEqual(desk.payments.calls, 0)

    def test_unknown_tool_names_the_real_ones(self):
        _, guard = build()
        out = guard.call("refund", REFUND)
        self.assertIn("issue_refund", out["fix"])


class RetryTest(unittest.TestCase):
    def test_refund_retried_three_times_pays_out_once(self):
        desk, guard = build(["lost", "lost", "ok"])
        out = guard.call("issue_refund", REFUND)
        self.assertEqual(desk.payments.calls, 3)
        self.assertEqual(len(desk.payments.payouts), 1)
        self.assertEqual(out["payout_id"], "PO-001")
        self.assertEqual(desk.payments.total_paid(), 12.65)

    def test_same_retries_without_a_key_pay_three_times(self):
        api = Payments(FakeClock(), ["lost", "lost", "ok"])
        for _ in range(3):
            try:
                api.pay("A-1003", 12.65)
            except TimeoutError:
                pass
        self.assertEqual(len(api.payouts), 3)

    def test_the_model_asking_twice_pays_once(self):
        desk, guard = build()
        first = guard.call("issue_refund", REFUND)
        again = guard.call("issue_refund", REFUND)
        self.assertTrue(again["replayed"])
        self.assertEqual(again["payout_id"], first["payout_id"])
        self.assertEqual(desk.payments.calls, 1)

    def test_a_new_ticket_cannot_refund_past_the_total(self):
        desk, guard = build()
        guard.call("issue_refund", {**REFUND, "amount": 56.75})
        other = Guard(make_tools(desk), desk.payments.clock,
                      ticket="T-5002")
        out = other.call("issue_refund", REFUND)
        self.assertIn("0.00 left", out["error"])
        self.assertEqual(len(desk.payments.payouts), 1)

    def test_backoff_waits_are_capped_seeded_and_fake(self):
        waits = []
        for _ in range(2):
            desk, guard = build(["busy", "busy", "busy"], seed=11)
            out = guard.call("issue_refund", REFUND)
            waits.append(desk.payments.clock.waits)
        self.assertEqual(waits[0], waits[1])
        self.assertEqual(len(waits[0]), 2)
        self.assertLessEqual(waits[0][0], 1.0)
        self.assertLessEqual(waits[0][1], 2.0)
        self.assertIn("Nothing changed", out["fix"])
        self.assertEqual(desk.payments.payouts, [])

    def test_each_try_gets_the_tool_timeout(self):
        desk, guard = build(["lost", "lost", "lost"])
        out = guard.call("issue_refund", REFUND)
        self.assertIn("no reply in 2.0s", out["error"])
        self.assertIn("may have run", out["fix"])
        waited = sum(desk.payments.clock.waits)
        self.assertAlmostEqual(desk.payments.clock.now, 6 + waited, 5)

    def test_a_crash_is_data_and_is_not_retried(self):
        desk, guard = build()
        desk.payments.pay = None
        out = guard.call("issue_refund", REFUND)
        self.assertIn("crashed: TypeError", out["error"])

    def test_failures_sort_into_not_sent_and_possibly_sent(self):
        self.assertEqual(classify_failure(Busy("503")), "not sent")
        self.assertEqual(classify_failure(TimeoutError("no reply")),
                         "possibly sent")

    def test_possibly_sent_refund_never_retries_without_key(self):
        keys = []

        def pay(order_id, amount, timeout, **extra):
            keys.append(extra.get("key"))
            return api.pay(order_id, amount, key=extra.get("key"),
                           timeout=timeout)

        api = Payments(FakeClock(), ["lost", "lost", "ok"])
        params = {"order_id": ORDER_ID, "amount": AMOUNT}
        tool = Tool("pay", pay, "Pay.", params, kind="write")
        args = {"order_id": "A-1003", "amount": 12.65}
        guard = Guard([tool], api.clock)
        out = guard.attempt(tool, args, {})        # no key
        self.assertIn("(possibly sent)", out["error"])
        self.assertIn("may have run", out["fix"])
        self.assertEqual(api.calls, 1)             # not tried again
        guard.attempt(tool, args, {"key": "k1"})   # with a key
        self.assertEqual(api.calls, 3)             # lost, then ok
        self.assertEqual(len(api.saved), 1)        # one keyed payout
        self.assertEqual(keys, [None, "k1", "k1"])

    def test_busy_reply_is_not_sent_and_may_retry(self):
        api = Payments(FakeClock(), ["busy", "ok"])
        tool = Tool("pay", lambda order_id, amount, timeout:
                    api.pay(order_id, amount, timeout=timeout),
                    "Pay.", {"order_id": ORDER_ID, "amount": AMOUNT},
                    kind="write")
        guard = Guard([tool], api.clock)
        out = guard.attempt(tool, {"order_id": "A-1003",
                                   "amount": 12.65}, {})
        self.assertEqual(out["payout_id"], "PO-001")
        self.assertEqual(api.calls, 2)


class DestroyTest(unittest.TestCase):
    def test_delete_without_approval_is_refused(self):
        desk, guard = build()
        out = guard.call("delete_order", {"order_id": "A-1004"})
        self.assertIn("needs human approval", out["error"])
        self.assertIn("A-1004", desk.orders)
        self.assertEqual(desk.history, [])

    def test_the_model_cannot_approve_itself(self):
        desk, guard = build(approver=Approver(False))
        out = guard.call("delete_order",
                         {"order_id": "A-1004", "approved": True})
        self.assertIn("Remove approved", out["fix"])
        self.assertIn("A-1004", desk.orders)

    def test_a_person_sees_the_dry_run_then_it_runs(self):
        person = Approver(True)
        desk, guard = build(approver=person)
        out = guard.call("delete_order", {"order_id": "A-1004"})
        self.assertEqual(out, {"deleted": "A-1004"})
        name, preview = person.seen[0]
        self.assertTrue(preview["dry_run"])
        self.assertEqual(preview["customer"], "Tomasz Wolski")
        self.assertNotIn("A-1004", desk.orders)
        self.assertIn("A-1004", ORDERS)           # ch02 untouched

    def test_a_rejection_reason_goes_back_to_the_model(self):
        person = Approver("It is a live order. Cancel it instead.")
        desk, guard = build(approver=person)
        out = guard.call("delete_order", {"order_id": "A-1004"})
        self.assertIn("a live order", out["error"])
        self.assertIn("Change the request", out["fix"])
        self.assertIn("A-1004", desk.orders)
        self.assertEqual(desk.history, [])

    def test_edited_arguments_run_after_a_second_validation(self):
        person = Approver({"order_id": "A-1005"})
        desk, guard = build(approver=person)
        out = guard.call("delete_order", {"order_id": "A-1004"})
        self.assertEqual(out, {"deleted": "A-1005"})
        self.assertIn("A-1004", desk.orders)
        self.assertNotIn("A-1005", desk.orders)

    def test_edited_arguments_that_fail_validation_do_not_run(self):
        person = Approver({"order_id": "A-10O5"})   # a letter O
        desk, guard = build(approver=person)
        out = guard.call("delete_order", {"order_id": "A-1004"})
        self.assertIn("edited arguments", out["error"])
        self.assertIn("does not fit", out["fix"])
        self.assertEqual(desk.history, [])
        self.assertEqual(len(desk.orders), len(ORDERS))


class CancelTaskTest(unittest.TestCase):
    """The hands-on task: dry run, approval, and never twice."""

    def cancel(self, guard, order_id="A-1007"):
        return guard.call("cancel_order", {"order_id": order_id})

    def test_dry_run_changes_nothing_before_approval(self):
        statuses = []

        def person(name, args, preview):
            statuses.append(desk.orders["A-1007"]["status"])
            return preview["would_cancel"] == "A-1007"

        desk, guard = build(approver=person, cancel=True)
        self.assertEqual(self.cancel(guard), {"canceled": "A-1007"})
        self.assertEqual(statuses, ["processing"])
        self.assertEqual(desk.orders["A-1007"]["status"], "canceled")

    def test_cancel_without_approval_is_refused(self):
        desk, guard = build(cancel=True)
        self.assertIn("needs human approval",
                      self.cancel(guard)["error"])
        declined, other = build(approver=Approver(False), cancel=True)
        self.assertIn("declined", self.cancel(other)["error"])
        for d in (desk, declined):
            self.assertEqual(d.orders["A-1007"]["status"],
                             "processing")

    def test_cancel_cannot_run_twice(self):
        person = Approver(True)
        desk, guard = build(approver=person, cancel=True)
        first, second = self.cancel(guard), self.cancel(guard)
        self.assertNotIn("replayed", first)
        self.assertTrue(second["replayed"])
        self.assertEqual(len(person.seen), 1)
        runs = [h for h in desk.history if h[0] == "cancel"]
        self.assertEqual(len(runs), 1)
        later = Guard(guard.tools.values(), desk.payments.clock,
                      approver=person, ticket="T-5002")
        self.assertIn("only a processing order",
                      self.cancel(later)["error"])
        self.assertEqual(len(person.seen), 1)

    def test_shipped_order_is_refused_before_any_person(self):
        person = Approver(True)
        _, guard = build(approver=person, cancel=True)
        out = self.cancel(guard, "A-1005")
        self.assertIn("offer a return", out["fix"].lower())
        self.assertEqual(person.seen, [])


class AgentLoopTest(unittest.TestCase):
    def test_ch02_loop_fixes_a_bad_argument_and_pays_once(self):
        desk, guard = build(["lost", "ok"])
        bad = {**REFUND, "amount": "12.65"}
        script = [
            {"tool_calls": [{"name": "issue_refund", "args": bad}]},
            {"tool_calls": [{"name": "issue_refund",
                             "args": REFUND}]},
            {"content": "Refunded."},
        ]
        result = run_agent(StandInModel(script), guard.registry(),
                           "Refund A-1003.")
        self.assertEqual(result["stop"], "done")
        outs = [e["result"] for e in result["trace"]
                if e["event"] == "tool_result"]
        self.assertIn("Send amount as a number", outs[0]["fix"])
        self.assertEqual(outs[1]["payout_id"], "PO-001")
        self.assertEqual(len(desk.payments.payouts), 1)


if __name__ == "__main__":
    unittest.main()
