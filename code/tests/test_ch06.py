import unittest
from unittest import mock

from ch02.mini_agent import TOOLS, tool_specs
from ch02.stub_model import StandInModel, estimate_tokens
from ch06 import context_budget as cb
from ch06 import placement
from ch06 import solution_expiry as exp
from ch06 import summaries as sm
from ch06.memory_store import SHOPPER, TENANT, MemoryStore, seed


def notes(store=None):
    store = store or MemoryStore()
    seed(store)
    return store.recall(TENANT, SHOPPER)


def packed_text(messages):
    return " ".join(m["content"] for m in messages)


class BudgetTest(unittest.TestCase):
    def test_input_plus_reply_fits_every_window(self):
        for window in (300, 350, 400, 450, 500, 700, 2000):
            messages, _ = cb.pack(cb.QUESTION, cb.gather(notes()),
                                  window)
            used = estimate_tokens(messages, tool_specs(TOOLS))
            self.assertLessEqual(used + cb.REPLY, window)

    def test_instructions_first_and_question_last(self):
        messages, _ = cb.pack(cb.QUESTION, cb.gather(notes()), 300)
        self.assertTrue(messages[0]["content"].startswith(
            cb.INSTRUCTIONS))
        self.assertEqual(messages[-1],
                         {"role": "user", "content": cb.QUESTION})

    def test_cuts_come_from_the_bottom_of_the_ranking(self):
        parts = cb.gather(notes())
        for window in (300, 400, 450, 500):
            _, report = cb.pack(cb.QUESTION, parts, window)
            verdicts = [v for v, _ in report]
            first_cut = verdicts.index("cut")
            self.assertEqual(set(verdicts[first_cut:]), {"cut"})
            names = [p["name"] for _, p in report]
            self.assertEqual(names,
                             [p["name"] for p in cb.rank(parts)])

    def test_default_window_cuts_the_two_weakest_pages(self):
        _, report = cb.pack(cb.QUESTION, cb.gather(notes()))
        cut = [p["name"] for v, p in report if v == "cut"]
        self.assertEqual(cut, ["returns", "shipping"])

    def test_history_stays_in_order(self):
        messages, _ = cb.pack(cb.QUESTION, cb.gather(notes()), 2000)
        turns = [m["content"] for m in messages[1:-1]]
        self.assertEqual(turns, [text for _, text in cb.HISTORY])

    def test_too_small_a_window_raises(self):
        with self.assertRaises(ValueError):
            cb.pack(cb.QUESTION, cb.gather(notes()), 200)

    def test_instructions_stay_short(self):
        self.assertLessEqual(estimate_tokens(cb.INSTRUCTIONS), 80)

    def test_a_second_tool_costs_a_page(self):
        two = dict(TOOLS, get_refund=TOOLS["get_order"])
        with mock.patch.object(cb, "TOOLS", two):
            _, report = cb.pack(cb.QUESTION, cb.gather(notes()))
        cut = [p["name"] for v, p in report if v == "cut"]
        self.assertEqual(cut, ["refund-policy", "returns", "shipping"])

    def test_placement_map_covers_kept_items_in_order(self):
        parts = cb.gather(notes())
        messages, report = cb.pack(cb.QUESTION, parts)
        found = placement.spans(messages, parts)
        kept = [p["name"] for p in parts if ("kept", p) in report]
        self.assertEqual([f[3] for f in found[1:-1]], kept)
        self.assertEqual((found[0][0], found[-1][1]), (0, 100))
        for before, after in zip(found, found[1:]):
            self.assertLessEqual(before[1], after[0])


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        seed(self.store)

    def test_tenants_do_not_share_a_shopper_id(self):
        mine = self.store.recall(TENANT, SHOPPER)
        theirs = self.store.recall("store-b", SHOPPER)
        self.assertNotIn("B-0077", " ".join(r["text"] for r in mine))
        self.assertEqual(len(theirs), 1)
        self.assertIn("B-0077", theirs[0]["text"])

    def test_a_shopper_sees_only_their_rows(self):
        rows = self.store.recall(TENANT, "S-23")
        self.assertEqual([r["text"] for r in rows], [
            "Deliver to the loading dock, not reception."])

    def test_every_call_needs_both_keys(self):
        for tenant, shopper in (("", SHOPPER), (TENANT, ""),
                                (None, SHOPPER)):
            with self.assertRaises(ValueError):
                self.store.recall(tenant, shopper)
            with self.assertRaises(ValueError):
                self.store.remember(tenant, shopper, "note", "x")

    def test_forget_removes_one_shopper_only(self):
        self.assertEqual(self.store.forget(TENANT, SHOPPER), 3)
        self.assertEqual(self.store.recall(TENANT, SHOPPER), [])
        self.assertEqual(len(self.store.recall("store-b", SHOPPER)), 1)
        self.assertEqual(len(self.store.recall(TENANT, "S-23")), 1)


class SummaryTest(unittest.TestCase):
    def run_rounds(self):
        model = StandInModel([{"content": s} for s in sm.SUMMARIES])
        turns = sm.compact(list(sm.TURNS), model)
        return sm.compact(turns + sm.MORE, model)

    def test_pinned_facts_survive_two_rounds(self):
        note = self.run_rounds()[0][1]
        for fact in ("A-1001", "2026-10-29", "R-A-1001", "$15.90"):
            self.assertIn(fact, note)

    def test_the_summary_alone_loses_them(self):
        summary = self.run_rounds()[0][1].split("\n")[0]
        for fact in ("A-1001", "R-A-1001", "$15.90"):
            self.assertNotIn(fact, summary)

    def test_recent_turns_stay_word_for_word(self):
        turns = self.run_rounds()
        self.assertEqual(turns[1:], sm.MORE)


class ExpiryTest(unittest.TestCase):
    def setUp(self):
        self.store = exp.ExpiringStore()
        seed(self.store)

    def test_old_refund_leaves_the_packed_context(self):
        rows = self.store.recall(TENANT, SHOPPER, today=exp.TODAY)
        messages, _ = cb.pack(cb.QUESTION, cb.gather(rows))
        text = packed_text(messages)
        self.assertNotIn("A-0388", text)
        self.assertIn("R-A-1001", text)

    def test_without_expiry_it_was_there(self):
        messages, _ = cb.pack(cb.QUESTION, cb.gather(notes()))
        self.assertIn("A-0388", packed_text(messages))

    def test_migration_fills_old_rows(self):
        plain = MemoryStore()
        seed(plain)
        exp.migrate(plain.db)
        rows = plain.db.execute(
            "SELECT kind, written, expires FROM memory"
            " ORDER BY id").fetchall()
        self.assertEqual(rows, [
            ("preference", "2026-01-10", "2027-01-10"),
            ("refund", "2026-03-02", "2026-05-01"),
            ("refund", "2026-10-30", "2026-12-29"),
            ("preference", "2026-09-01", "2027-09-01"),
            ("refund", "2026-10-12", "2026-12-11")])

    def test_unknown_kinds_get_the_default(self):
        self.store.remember(TENANT, SHOPPER, "note", "Asked about "
                            "gloves.", "2026-10-01")
        rows = self.store.recall(TENANT, SHOPPER, today="2026-10-30")
        self.assertIn("note", [r["kind"] for r in rows])
        rows = self.store.recall(TENANT, SHOPPER, today="2026-10-31")
        self.assertNotIn("note", [r["kind"] for r in rows])

    def test_purge_deletes_only_expired_rows(self):
        self.assertEqual(self.store.purge(exp.TODAY), 1)
        self.assertEqual(self.store.purge(exp.TODAY), 0)
        left = self.store.db.execute(
            "SELECT COUNT(*) FROM memory").fetchone()[0]
        self.assertEqual(left, 4)

    def test_expiry_keeps_tenants_apart(self):
        rows = self.store.recall("store-b", SHOPPER, today=exp.TODAY)
        self.assertEqual([r["kind"] for r in rows], ["refund"])
        self.assertEqual(self.store.recall(
            "store-b", SHOPPER, today="2026-12-11"), [])


if __name__ == "__main__":
    unittest.main()
