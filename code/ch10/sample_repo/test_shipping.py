"""The store's shipping rule, as tests. One of them fails today."""
import unittest

from shipping import shipping_fee


class ShippingTest(unittest.TestCase):
    def test_small_order_pays_flat_fee(self):
        self.assertEqual(shipping_fee(4999), 695)

    def test_large_order_ships_free(self):
        self.assertEqual(shipping_fee(7500), 0)

    def test_order_of_exactly_fifty_dollars_ships_free(self):
        self.assertEqual(shipping_fee(5000), 0)
