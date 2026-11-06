"""Tests for Chapter 11: quantity limits, the confirm step, the voice
budget, and the click guard.

Run from code/:  python -m unittest tests.test_ch11
"""
import io
import json
import unittest
from contextlib import redirect_stdout

from ch02.store import ORDERS
from ch11 import click_guard as cg
from ch11 import quantity_check as qc
from ch11 import solution_confirm as sol
from ch11 import voice_budget as vb

SITE = "https://portal.example-supply.test"


class QuantityCheck(unittest.TestCase):
    def test_water_order_rejected(self):
        problems = qc.check([("water cup", 18000)], qc.DRIVE)
        self.assertEqual(problems, ["water cup: 18,000 is over the "
                                    "limit of 10 per line"])

    def test_limit_is_inclusive(self):
        self.assertEqual(qc.check([("water cup", 10)], qc.DRIVE), [])
        self.assertTrue(qc.check([("water cup", 11)], qc.DRIVE))

    def test_sane_order_passes(self):
        lines = qc.parse("taco=3, large drink=2")
        self.assertEqual(qc.verdict(lines, qc.DRIVE),
                         {"ok": True, "units": 5})

    def test_not_whole_numbers_rejected(self):
        for qty in (0, -2, 3.0, "two", "18000", True):
            with self.subTest(qty=qty):
                self.assertTrue(qc.check([("taco", qty)], qc.DRIVE))

    def test_unknown_item_rejected(self):
        problems = qc.check([("pizza", 1)], qc.DRIVE)
        self.assertIn("not on the drive-through menu", problems[0])

    def test_order_total_capped(self):
        lines = qc.parse("taco=20, burrito=20, water cup=4")
        self.assertEqual(qc.check(lines, qc.DRIVE),
                         ["44 units is over the limit of 40 per order"])

    def test_reject_is_data_with_a_fix(self):
        result = qc.verdict([("water cup", 18000)], qc.DRIVE)
        self.assertEqual(set(result), {"error", "fix"})
        self.assertIn("person", result["fix"])

    def test_parse(self):
        self.assertEqual(qc.parse("water cup=18000"),
                         [("water cup", 18000)])
        self.assertEqual(qc.parse("taco=two"), [("taco", "two")])

    def test_parts_limits_cover_every_store_item(self):
        skus = {i["sku"] for o in ORDERS.values() for i in o["items"]}
        self.assertEqual(set(qc.PARTS["max_line"]), skus)
        self.assertTrue(qc.check([("CT-100", 1000)], qc.PARTS))

    def test_try_it_run(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = qc.main(["drive", "water cup=18000"])
        self.assertEqual(code, 0)
        self.assertIn("REJECT  drive water cup=18000", out.getvalue())

    def test_split_lines_are_added_up(self):
        problems = qc.check([("water cup", 10)] * 4, qc.DRIVE)
        self.assertEqual(problems, ["water cup: 40 is over the limit "
                                    "of 10 per line"])


class ConfirmStep(unittest.TestCase):
    def order(self, text, answer):
        caller, placed = sol.Caller(answer), []
        status, _ = sol.take_order(qc.parse(text), caller.ask,
                                   placed.append)
        return status, caller.heard, placed

    def test_small_order_placed_without_asking(self):
        status, heard, placed = self.order("taco=3", "no")
        self.assertEqual((status, heard), ("placed", []))
        self.assertEqual(placed, [[("taco", 3)]])

    def test_order_over_limit_waits_for_yes(self):
        status, heard, placed = self.order("water cup=8", "yes")
        self.assertEqual(status, "placed")
        self.assertEqual(heard, ["Just to check: 8 water cups. "
                                 "Is that right?"])
        self.assertEqual(len(placed), 1)

    def test_no_places_nothing(self):
        for answer in ("no, two", "uh, maybe", ""):
            with self.subTest(answer=answer):
                status, heard, placed = self.order("water cup=8",
                                                   answer)
                self.assertEqual((status, placed), ("not placed", []))
                self.assertEqual(len(heard), 1)

    def test_reject_holds_even_after_yes(self):
        status, heard, placed = self.order("water cup=18000", "yes")
        self.assertEqual((status, heard, placed), ("handoff", [], []))

    def test_confirm_limit_edge(self):
        self.assertEqual(sol.decide([("water cup", 4)]), ("place",))
        self.assertEqual(sol.decide([("water cup", 5)])[0], "confirm")

    def test_four_heard_as_fourteen_is_asked(self):
        self.assertEqual(qc.check([("taco", 14)], qc.DRIVE), [])
        self.assertEqual(sol.decide([("taco", 14)]),
                         ("confirm", [("taco", 14)]))

    def test_split_order_is_read_back_whole(self):
        status, heard, placed = self.order("water cup=4, water cup=4",
                                           "yes")
        self.assertEqual(heard, ["Just to check: 8 water cups. "
                                 "Is that right?"])
        self.assertEqual((status, len(placed)), ("placed", 1))

    def test_demo(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(sol.main(), 0)
        self.assertIn("orders placed: 2 of 4", out.getvalue())


class VoiceBudget(unittest.TestCase):
    def test_shares_add_up_to_budget(self):
        self.assertEqual(sum(vb.SHARE.values()), vb.BUDGET_MS)

    def test_budget_edge(self):
        turn = dict(vb.SHARE)
        self.assertEqual(vb.check_turn(turn), (800, []))
        turn["model"] += 1
        self.assertTrue(vb.check_turn(turn)[1])

    def test_names_the_stage_most_over(self):
        turn = dict(vb.SHARE, endpoint=500, model=350)
        total, problems = vb.check_turn(turn)
        self.assertEqual(total, 1150)
        self.assertEqual(problems, ["over budget by 350 ms; endpoint "
                                    "is 300 ms over its share"])

    def test_recorded_cases_replay_as_expected(self):
        for case in json.loads(vb.CASES.read_text()):
            with self.subTest(case=case["id"]):
                self.assertEqual(vb.replay(case)[1], case["expect"])

    def test_case_format(self):
        keys = {"id", "audio", "note", "said", "heard", "call",
                "timings_ms", "expect"}
        for case in json.loads(vb.CASES.read_text()):
            with self.subTest(case=case["id"]):
                self.assertLessEqual(keys, set(case))
                self.assertEqual(set(case["timings_ms"]), set(vb.SHARE))

    def test_stop_cap_edge(self):
        case = json.loads(vb.CASES.read_text())[3]
        for stop, want in ((200, "ok"), (201, "late")):
            with self.subTest(stop=stop):
                got = vb.replay(dict(case, stop_ms=stop))[1]
                self.assertEqual(got["stop"], want)

    def test_report(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(vb.main(), 0)
        self.assertIn("cases: 5, passed: 5", out.getvalue())


class ClickGuard(unittest.TestCase):
    def test_allowed(self):
        action = {"action": "click", "url": SITE + "/reorder",
                  "target": "Cable ties"}
        self.assertEqual(cg.check(action), ("ALLOW", ""))

    def test_hosts_that_only_look_right_are_blocked(self):
        for url in ("https://portal.example-supply.test.login-check"
                    ".test/", "https://example-supply.test/",
                    "https://portal.example-supply.test@evil.test/",
                    "http://portal.example-supply.test/", ""):
            with self.subTest(url=url):
                verdict, _ = cg.check({"action": "open", "url": url})
                self.assertEqual(verdict, "BLOCK")

    def test_actions_off_the_allowlist_blocked(self):
        for kind in ("download", "drag", "run", None):
            with self.subTest(kind=kind):
                action = {"action": kind, "url": SITE + "/"}
                self.assertEqual(cg.check(action)[0], "BLOCK")

    def test_risky_clicks_ask(self):
        for label in ("Place order", "Pay now", "SUBMIT", "Delete",
                      "Accept terms", "Buy now", "Checkout",
                      "Check out", "Purchase", "Confirm order"):
            with self.subTest(label=label):
                action = {"action": "click", "url": SITE + "/cart",
                          "target": label}
                self.assertEqual(cg.check(action)[0], "ASK")

    def test_order_and_payment_labels_ask(self):
        for label in ("Order now", "Complete order", "Payment"):
            with self.subTest(label=label):
                action = {"action": "click", "url": SITE + "/cart",
                          "target": label}
                self.assertEqual(cg.check(action)[0], "ASK")

    def test_page_free_screenshot_and_scroll_allowed(self):
        for kind in ("screenshot", "scroll"):
            with self.subTest(kind=kind):
                self.assertEqual(cg.check({"action": kind}),
                                 ("ALLOW", ""))
        self.assertEqual(cg.check({"action": "open"})[0], "BLOCK")

    def test_typing_enter_asks(self):
        action = {"action": "type", "url": SITE + "/reorder",
                  "target": "Quantity", "text": "10\n"}
        self.assertEqual(cg.check(action)[0], "ASK")

    def test_word_inside_word_is_not_risky(self):
        action = {"action": "click", "url": SITE + "/",
                  "target": "Display options"}
        self.assertEqual(cg.check(action)[0], "ALLOW")

    def test_person_asked_before_each_risky_click(self):
        asked = []
        clicks = [{"action": "click", "url": SITE + "/cart",
                   "target": "Place order"}] * 2
        log = cg.run(clicks, lambda a: asked.append(a) or False)
        self.assertEqual(len(asked), 2)
        self.assertEqual([ran for _, ran, _, _ in log], [False, False])

    def test_trace(self):
        asked = []
        log = cg.run(cg.TRACE, lambda a: asked.append(a) or True)
        self.assertEqual([v for v, _, _, _ in log],
                         ["ALLOW", "ALLOW", "ALLOW", "BLOCK", "BLOCK",
                          "ASK", "BLOCK"])
        self.assertEqual([a["target"] for a in asked], ["Place order"])


if __name__ == "__main__":
    unittest.main()
