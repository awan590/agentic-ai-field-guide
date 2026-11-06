"""Long-term memory for the support agent, in one SQLite table.

Every row names the tenant (the store that runs the agent) and the
shopper it is about. Every read and every delete must name both, so
no call can reach another store's or another shopper's rows. The
rows in seed() are synthetic.

    python -m ch06.memory_store
"""
import sqlite3
from datetime import date

TENANT, SHOPPER = "example-supply", "S-17"
FIELDS = ("kind", "text", "written")
SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY,
    tenant TEXT NOT NULL,
    shopper TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    written TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS by_owner ON memory (tenant, shopper);
"""


def owner(tenant, shopper):
    """Both keys, or an error: there is no call without them."""
    if not tenant or not shopper:
        raise ValueError("memory calls need a tenant and a shopper")
    return (tenant, shopper)


class MemoryStore:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def remember(self, tenant, shopper, kind, text, written=None):
        """Save one dated fact about one shopper; return its row id."""
        when = written or date.today().isoformat()
        cur = self.db.execute(
            "INSERT INTO memory (tenant, shopper, kind, text, written)"
            " VALUES (?, ?, ?, ?, ?)",
            owner(tenant, shopper) + (kind, text, when))
        self.db.commit()
        return cur.lastrowid

    def recall(self, tenant, shopper, limit=20):
        """One shopper's facts at one tenant, newest first."""
        rows = self.db.execute(
            "SELECT kind, text, written FROM memory"
            " WHERE tenant = ? AND shopper = ?"
            " ORDER BY written DESC, id DESC LIMIT ?",
            owner(tenant, shopper) + (limit,))
        return [dict(zip(FIELDS, row)) for row in rows]

    def forget(self, tenant, shopper):
        """Delete every row about one shopper; return the count."""
        cur = self.db.execute(
            "DELETE FROM memory WHERE tenant = ? AND shopper = ?",
            owner(tenant, shopper))
        self.db.commit()
        return cur.rowcount


def seed(store):
    """Two stores that both number a shopper S-17."""
    for row in [
        (TENANT, SHOPPER, "preference",
         "Prefers email, not phone calls.", "2026-01-10"),
        (TENANT, SHOPPER, "refund",
         "Refund for A-0388 approved and paid: $22.40.", "2026-03-02"),
        (TENANT, SHOPPER, "refund",
         "Refund R-A-1001 requested for A-1001: $15.90.", "2026-10-30"),
        (TENANT, "S-23", "preference",
         "Deliver to the loading dock, not reception.", "2026-09-01"),
        ("store-b", SHOPPER, "refund",
         "Refund for B-0077 approved: $410.00.", "2026-10-12"),
    ]:
        store.remember(*row)


def line(row):
    return f"{row['written']} {row['kind']}: {row['text']}"


def count(n, noun):
    """'1 row' or '3 rows'."""
    return f"{n} {noun}" + ("" if n == 1 else "s")


if __name__ == "__main__":
    store = MemoryStore()
    seed(store)
    for tenant in (TENANT, "store-b"):
        rows = store.recall(tenant, SHOPPER)
        print(f"recall({tenant}, {SHOPPER}): {count(len(rows), 'row')}")
        for row in rows:
            print("  " + line(row))
    leak = store.db.execute(
        "SELECT DISTINCT tenant FROM memory WHERE shopper = ?",
        (SHOPPER,)).fetchall()
    print(f"query on shopper alone: {len(leak)} tenants mixed")
    gone = store.forget(TENANT, "S-23")
    print(f"forget({TENANT}, S-23): {count(gone, 'row')}")
