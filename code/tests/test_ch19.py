"""Chapter 19: the data map, retention rules, and the answer bank."""
import io
import json
import unittest
from datetime import date
from pathlib import Path

from ch19 import answer_bank, data_map, retention
from ch19.tables import TABLES, build


def by_column(rows):
    return {r["column"]: r for r in rows}


class DataMapTest(unittest.TestCase):
    def setUp(self):
        self.db = build()
        self.rows = by_column(data_map.scan(self.db))

    def test_every_personal_column_is_listed(self):
        self.assertEqual(sorted(self.rows), [
            "orders.customer", "orders.email", "orders.note",
            "orders.ship_to", "payments.card", "tickets.body"])
        total = sum(len(cols) for cols, _ in TABLES.values())
        self.assertEqual(total, 17)

    def test_name_scan_and_value_scan_agree_on_email(self):
        self.assertEqual(self.rows["orders.email"]["found"], "both")
        self.assertEqual(self.rows["orders.email"]["hits"], "8/8")

    def test_masked_column_leaves_clean(self):
        self.assertEqual(self.rows["orders.email"]["status"], "masked")

    def test_free_text_is_flagged(self):
        body = self.rows["tickets.body"]
        self.assertEqual((body["found"], body["status"]),
                         ("value", "FLAG"))
        self.assertEqual(self.rows["orders.note"]["kind"],
                         "email+phone")

    def test_card_stays_in_store(self):
        self.assertEqual(self.rows["payments.card"]["status"], "stays")

    def test_masking_clears_a_flag(self):
        masked = data_map.MASKED | {"tickets.body"}
        rows = by_column(data_map.scan(self.db, masked=masked))
        self.assertEqual(rows["tickets.body"]["status"], "masked")
        self.assertEqual(rows["orders.note"]["status"], "FLAG")

    def test_unlisted_table_is_assumed_to_leave(self):
        rows = by_column(data_map.scan(self.db, reaches={}))
        self.assertEqual(rows["payments.card"]["zone"], "vendor")
        self.assertEqual(rows["payments.card"]["status"], "sent")

    def test_byte_cap_lets_every_flagged_row_through(self):
        self.assertEqual(
            data_map.under_cap(self.db, "tickets.body", 1024), (2, 2))

    def test_map_file_is_never_overwritten(self):
        target = Path(data_map.__file__)
        before = target.read_bytes()
        with self.assertRaises(FileExistsError):
            data_map.write_map(list(self.rows.values()), target)
        self.assertEqual(target.read_bytes(), before)


class RetentionTest(unittest.TestCase):
    def setUp(self):
        self.records = retention.load()
        self.kept, self.verdicts = retention.apply(self.records)

    def test_rules_by_age(self):
        self.assertEqual(self.verdicts["r01"], "keep")
        self.assertEqual(self.verdicts["r02"], "age")
        self.assertEqual(self.verdicts["r06"], "age")
        self.assertEqual(len(self.kept), 7)

    def test_last_day_is_kept_and_the_next_is_not(self):
        rec = {"id": "x", "kind": "trace", "day": "2026-08-06",
               "shopper": "S-11"}
        self.assertEqual(retention.decide(rec), "keep")
        later = date(2026, 11, 5)
        self.assertEqual(retention.decide(rec, today=later), "age")

    def test_hold_beats_age_and_request(self):
        self.assertEqual(self.verdicts["r08"], "hold")
        _, verdicts = retention.apply(self.records, forget={"S-16"})
        self.assertEqual(verdicts["r08"], "hold")
        self.assertEqual(verdicts["r07"], "request")

    def test_forget_request_drops_one_shopper(self):
        ids = {r["id"] for r in self.kept}
        self.assertFalse(ids & {"r09", "r10"})
        self.assertTrue(all(r["shopper"] != "S-23" for r in self.kept))
        self.assertIn("r11", ids)

    def test_kind_without_a_rule_is_left_out(self):
        self.assertEqual(self.verdicts["r13"], "no rule")

    def test_log_is_read_and_never_overwritten(self):
        before = retention.LOG.read_bytes()
        with self.assertRaises(FileExistsError):
            retention.write_kept(self.kept, retention.LOG)
        self.assertEqual(retention.LOG.read_bytes(), before)

    def test_kept_set_is_valid_json_lines(self):
        out = io.StringIO()
        retention.dump(self.kept, out)
        back = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(back, self.kept)


class AnswerBankTest(unittest.TestCase):
    def test_every_answer_links_to_evidence(self):
        self.assertEqual(answer_bank.check(answer_bank.BANK), [])

    def test_missing_file_is_caught(self):
        bank = [("X-01", "q", "a", "ch19/no_such_file.py")]
        self.assertEqual(len(answer_bank.check(bank)), 1)

    def test_missing_test_is_caught(self):
        bank = [("X-02", "q", "a", "test_ch19.DataMapTest.test_nope")]
        self.assertEqual(len(answer_bank.check(bank)), 1)

    def test_answer_without_a_link_is_caught(self):
        bank = [("X-03", "q", "a", "")]
        self.assertEqual(answer_bank.check(bank), ["X-03: no link"])


if __name__ == "__main__":
    unittest.main()
