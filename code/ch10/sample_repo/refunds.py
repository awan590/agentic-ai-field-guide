"""Refunds for Example Supply Co. (invented). Prices are in cents."""

RESTOCK_PERCENT = 10      # fee kept on an opened, undamaged item


def refund_amount(price, opened, damaged):
    """Cents to give back for one returned item."""
    if opened:
        return price - price * RESTOCK_PERCENT // 100
    if damaged:
        return price      # damaged: full refund
    return price          # unopened: full refund
