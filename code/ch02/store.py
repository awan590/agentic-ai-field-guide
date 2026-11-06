"""Orders for Example Supply Co., the book's invented parts store.

Every customer, item, and number here is synthetic. get_order()
returns a copy of one order, or an error dict: a missing order is
data the model can read, never an exception that stops the loop.
"""
import copy


def _order(order_id, customer, status, placed, *items):
    lines = [{"sku": sku, "name": name, "qty": qty, "price": price}
             for sku, name, qty, price in items]
    total = round(sum(i["qty"] * i["price"] for i in lines), 2)
    return {"id": order_id, "customer": customer, "items": lines,
            "status": status, "total": total, "placed": placed}


ORDERS = {o["id"]: o for o in [
    _order("A-1001", "Lena Ortiz", "shipped", "2026-10-27",
           ("HC-038", "Hose clamp, 3/8 in", 2, 7.95)),
    _order("A-1002", "Omar Haddad", "processing", "2026-10-30",
           ("BK-6204", "Bearing kit 6204", 1, 64.00),
           ("GR-400", "Bearing grease, 400 g", 1, 29.50)),
    _order("A-1003", "Priya Nair", "delivered", "2026-10-14",
           ("FT-038", "Brass fitting, 3/8 in", 4, 12.65),
           ("TT-012", "Thread seal tape", 1, 6.15)),
    _order("A-1004", "Tomasz Wolski", "canceled", "2026-10-22",
           ("PG-010", "Pressure gauge, 0-10 bar", 1, 38.75)),
    _order("A-1005", "Grace Mensah", "shipped", "2026-10-29",
           ("VB-A42", "V-belt A42", 3, 11.20)),
    _order("A-1006", "Kenji Sato", "delivered", "2026-10-08",
           ("CT-100", "Cable ties, pack of 100", 10, 4.55),
           ("HK-009", "Hex key set, 9 pieces", 2, 9.95)),
    _order("A-1007", "Ana Lima", "processing", "2026-11-02",
           ("BV-012", "Ball valve, 1/2 in", 1, 24.99)),
    _order("A-1008", "Sam Carter", "shipped", "2026-10-31",
           ("HC-100", "Hose clamp, 1 in", 6, 8.45)),
]}


def get_order(order_id):
    """Return one order as a new dict, or {"error": ...}."""
    order = ORDERS.get(str(order_id).strip().upper())
    if order is None:
        return {"error": f"no order with id {order_id}"}
    return copy.deepcopy(order)
