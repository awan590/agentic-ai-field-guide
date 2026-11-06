"""Tests for Chapter 18: risk tiers, the autonomy dial, the guard on
top of Chapter 13, and the returns agent's scope.

Run from code/:  python -m unittest tests.test_ch18
"""
import unittest

from ch13 import policy as ch13
from ch18 import autonomy_dial as dial
from ch18 import risk_tier as rt
from ch18 import solution_scope as sol

REFUND = {"order_id": "A-1003", "amount": 56.75}


class TierTest(unittest.TestCase):
    def test_score_cuts(self):
        self.assertEqual(rt.tier(1, 1, 3), 1)      # score 3
        self.assertEqual(rt.tier(2, 2, 1), 2)      # score 4
        self.assertEqual(rt.tier(1, 3, 3), 2)      # score 9
        self.assertEqual(rt.tier(2, 3, 2), 3)      # score 12

    def test_severe_and_permanent_is_tier_3_at_any_volume(self):
        self.assertEqual(rt.tier(3, 3, 1), 3)

    def test_refund_and_card_number_are_tier_3(self):
        self.assertEqual(rt.tier(*rt.ACTIONS["issue_refund"]), 3)
        self.assertEqual(rt.tier(*rt.DATA["card number"]), 3)


class DialTest(unittest.TestCase):
    def test_notch_moves_one_step_and_stops_at_the_ends(self):
        self.assertEqual(dial.notch("ASK"), "NOTIFY")
        self.assertEqual(dial.notch("ASK", -1), "DRAFT")
        self.assertEqual(dial.notch("AUTO"), "AUTO")
        self.assertEqual(dial.notch("OFF", -1), "OFF")

    def test_unrated_action_counts_as_tier_3(self):
        scope = dict(sol.SCOPE, actions={"file_claim": ("AUTO", "x")})
        policy = dial.build_policy(scope)
        self.assertEqual(policy["actions"]["file_claim"]["tier"], 3)
        self.assertIn("ceiling ASK", dial.problems(policy)[0])

    def test_write_refuses_a_setting_above_its_ceiling(self):
        bad = dial.change(sol.SCOPE, "issue_refund", 1)
        with self.assertRaises(ValueError):
            dial.write_policy(bad, "never-written.json")

    def test_change_raises_version_and_diff_names_the_action(self):
        new = dial.change(sol.SCOPE, "cancel_order", 1)
        self.assertEqual(new["version"], 2)
        self.assertEqual(dial.diff(dial.build_policy(sol.SCOPE),
                                   dial.build_policy(new)),
                         ["cancel_order: OFF -> DRAFT"])


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.policy = dial.build_policy(sol.SCOPE)

    def verdict(self, name, args):
        return dial.guard(self.policy, ch13.SESSION, name, args)[0]

    def test_file_cannot_loosen_chapter_13(self):
        self.policy["actions"]["issue_refund"]["verdict"] = "ALLOW"
        self.assertEqual(self.verdict("issue_refund", REFUND), "ASK")

    def test_file_can_tighten_chapter_13(self):
        args = {"order_id": "A-1003"}
        self.assertEqual(ch13.check(ch13.SESSION, "cancel_order",
                                    args)[0], "ASK")
        self.assertEqual(self.verdict("cancel_order", args), "BLOCK")

    def test_never_list_and_unlisted_tools_are_blocked(self):
        for name in self.policy["never"]:
            self.assertEqual(self.verdict(name, {}), "BLOCK", name)
        self.assertEqual(self.verdict("send_return_label", {}), "BLOCK")

    def test_chapter_13_mail_rule_still_holds(self):
        args = {"to": "audit@ledger-check.test"}
        self.assertEqual(self.verdict("send_email", args), "BLOCK")


class ScopeTest(unittest.TestCase):
    def test_scope_breaks_no_dial_rule(self):
        policy = dial.build_policy(sol.SCOPE)
        self.assertEqual(dial.problems(policy), [])

    def test_refunds_wait_for_a_person(self):
        self.assertEqual(sol.SCOPE["actions"]["issue_refund"][0], "ASK")
        policy = dial.load_policy(sol.POLICY)
        verdict, _ = dial.guard(policy, ch13.SESSION, "issue_refund",
                                REFUND)
        self.assertEqual(verdict, "ASK")

    def test_saved_file_matches_the_scope(self):
        self.assertEqual(dial.load_policy(sol.POLICY),
                         dial.build_policy(sol.SCOPE))

    def test_done_check_passes_on_the_saved_file(self):
        self.assertTrue(all(ok for ok, _ in sol.done_check(sol.POLICY)))

    def test_law_and_price_questions_go_to_people(self):
        topics = [sol.route(q) for q in sol.QUESTIONS]
        self.assertIsNone(topics[0])
        self.assertEqual([t[0] for t in topics[1:]],
                         ["the law", "the law", "price matching"])


class PromotionTest(unittest.TestCase):
    def setUp(self):
        # cancel_order at DRAFT (version 2), as CR-2 left it
        self.scope = dial.change(sol.SCOPE, "cancel_order", 1)

    def test_promote_after_n_clean_runs(self):
        self.assertIs(dial.promote(self.scope, "cancel_order", 49),
                      self.scope)
        up = dial.promote(self.scope, "cancel_order", 50)
        self.assertEqual(up["actions"]["cancel_order"][0], "ASK")
        self.assertEqual(up["version"], 3)

    def test_demote_on_an_incident(self):
        down = dial.demote(sol.SCOPE, "send_email")
        self.assertEqual(down["actions"]["send_email"][0], "ASK")
        self.assertEqual(down["version"], 2)

    def test_promote_never_passes_the_cap(self):
        scope = self.scope
        for _ in range(5):
            scope = dial.promote(scope, "cancel_order", 50)
        self.assertEqual(scope["actions"]["cancel_order"][0], "NOTIFY")
        for name in ("issue_refund", "export_customers"):
            self.assertIs(dial.promote(sol.SCOPE, name, 10**6),
                          sol.SCOPE)


if __name__ == "__main__":
    unittest.main()
