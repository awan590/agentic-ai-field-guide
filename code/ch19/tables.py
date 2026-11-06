"""Synthetic tables for the Example Supply support agent.

build() loads them into an in-memory SQLite database, a stand-in for
the copy a customer hands over for a review. Every name, address,
and number here is invented. REACHES says how far each table's rows
travel: "store" means they never leave the customer's systems, and
"vendor" means the agent puts them in prompts to the model vendor.
"""
import sqlite3

REACHES = {"orders": "vendor", "payments": "store",
           "products": "vendor", "tickets": "vendor"}

TABLES = {
    "orders": (
        ("order_id", "customer", "email", "ship_to", "total", "note"),
        [("A-1001", "Lena Ortiz", "lena.ortiz@mail.test",
          "4 Mill Lane", 64.0, ""),
         ("A-1002", "Omar Haddad", "omar.haddad@mail.test",
          "18 Quay Street", 23.5, "Leave at the side door"),
         ("A-1003", "Priya Nair", "priya.nair@mail.test",
          "7 Birch Close", 112.0, "Copy invoice to ap@nair.test"),
         ("A-1004", "Tomasz Wolski", "tomasz.wolski@mail.test",
          "30 Canal Row", 41.0, ""),
         ("A-1005", "Grace Mensah", "grace.mensah@mail.test",
          "2 Hill View", 15.0, "Gift, ring +44 20 7946 0188"),
         ("A-1006", "Kenji Sato", "kenji.sato@mail.test",
          "11 Park Walk", 89.0, ""),
         ("A-1007", "Ana Lima", "ana.lima@mail.test",
          "5 Ferry Road", 37.0, "No plastic, please"),
         ("A-1008", "Sam Carter", "sam.carter@mail.test",
          "9 Oak Yard", 58.0, "")]),
    "payments": (
        ("order_id", "card", "amount"),
        [("A-1001", "4111 1111 1111 1111", 64.0),
         ("A-1003", "5500 0000 0000 0004", 112.0),
         ("A-1005", "4000 0566 5566 5556", 15.0)]),
    "products": (
        ("sku", "title", "price", "stock"),
        [("KB-01", "Desk lamp", 24.0, 40),
         ("KB-02", "Cable tidy", 6.5, 210),
         ("KB-03", "Monitor arm", 79.0, 12)]),
    "tickets": (
        ("ticket_id", "order_id", "opened", "body"),
        [("T-301", "A-1001", "2026-10-02", "Box arrived dented."),
         ("T-302", "A-1003", "2026-10-03",
          "Call me on +44 20 7946 0103 before noon."),
         ("T-303", "A-1004", "2026-10-05", "Where is my order?"),
         ("T-304", "A-1006", "2026-10-06", "Wrong color sent."),
         ("T-305", "A-1007", "2026-10-09",
          "My new number is +351 21 555 0142."),
         ("T-306", "A-1008", "2026-10-11", "Please cancel.")]),
}


def build():
    """Return an in-memory SQLite database holding TABLES."""
    db = sqlite3.connect(":memory:")
    for name, (cols, rows) in TABLES.items():
        db.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        marks = ", ".join("?" for _ in cols)
        db.executemany(f"INSERT INTO {name} VALUES ({marks})", rows)
    return db
