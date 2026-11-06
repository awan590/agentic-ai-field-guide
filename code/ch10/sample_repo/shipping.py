"""Shipping for Example Supply Co. (invented). Prices are in cents."""

FREE_FROM = 5000          # orders of $50.00 or more ship free
FLAT_FEE = 695


def shipping_fee(subtotal):
    """Cents to charge for shipping one order."""
    if subtotal > FREE_FROM:
        return 0
    return FLAT_FEE
