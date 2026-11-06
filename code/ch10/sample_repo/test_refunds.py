"""The store's refund rules, as tests. One of them fails today."""
import unittest

from refunds import refund_amount


class RefundTest(unittest.TestCase):
    def test_unopened_item_gets_full_refund(self):
        self.assertEqual(refund_amount(4000, False, False), 4000)

    def test_opened_item_pays_restocking_fee(self):
        self.assertEqual(refund_amount(4000, True, False), 3600)

    def test_damaged_item_gets_full_refund_even_if_opened(self):
        self.assertEqual(refund_amount(4000, True, True), 4000)
