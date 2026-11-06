"""The systems behind the orders server, kept apart from the protocol.

Orders come from the Chapter 2 store through get_order(). The refund
policy, the refund requests, and the stock levels are synthetic
stand-ins for systems a real store would own. Nothing here pays
anyone: a refund request is a record that a person reviews later.
"""
from ch02.store import get_order

__all__ = ["get_order", "REFUND_POLICY", "record_refund",
           "stock_levels"]

REFUND_POLICY = "\n".join([
    "Example Supply Co. refund policy (synthetic)",
    "1. Only shipped or delivered orders can be refunded.",
    "2. A refund cannot exceed the order total.",
    "3. A person approves every refund before money moves.",
    "4. One open refund request per order.",
])

REFUNDS = {}

STOCK = {"BK-6204": 14, "BV-012": 0, "CT-100": 230, "FT-038": 52,
         "GR-400": 9, "HC-038": 120, "HC-100": 64, "HK-009": 31,
         "PG-010": 6, "TT-012": 75, "VB-A42": 18}


def record_refund(order_id, amount, reason):
    """Save one refund request per order; repeats return the first."""
    if order_id not in REFUNDS:
        REFUNDS[order_id] = {
            "request_id": f"R-{order_id}", "order_id": order_id,
            "amount": amount, "reason": reason,
            "status": "pending review"}
    return dict(REFUNDS[order_id])


def stock_levels():
    """Units on hand per SKU, as a new dict."""
    return dict(STOCK)
