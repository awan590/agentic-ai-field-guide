"""Task solution: memories expire, so old refunds leave the context.

Every row gets an expiry date from its kind: 60 days for a refund
note, 365 for a preference, 30 for anything else. recall() skips
rows past that date and purge() deletes them for every tenant. The
day counts are this book's examples; set yours with whoever owns
the store's data rules.

    python -m ch06.solution_expiry
"""
from datetime import date

from ch06.context_budget import QUESTION, gather, pack
from ch06.memory_store import (FIELDS, SHOPPER, TENANT, MemoryStore,
                               count, line, owner, seed)

TTL_DAYS = {"refund": 60, "preference": 365}
DEFAULT_TTL = 30
TODAY = "2026-11-03"  # fixed so the demo prints the same every day


def migrate(db):
    """Add an expires column if missing; fill every empty one."""
    columns = [r[1] for r in db.execute("PRAGMA table_info(memory)")]
    if "expires" not in columns:
        db.execute("ALTER TABLE memory ADD COLUMN expires TEXT")
    for kind, days in TTL_DAYS.items():
        db.execute("UPDATE memory SET expires = date(written, ?)"
                   " WHERE expires IS NULL AND kind = ?",
                   (f"+{days} days", kind))
    db.execute("UPDATE memory SET expires = date(written, ?)"
               " WHERE expires IS NULL", (f"+{DEFAULT_TTL} days",))
    db.commit()


class ExpiringStore(MemoryStore):
    def __init__(self, path=":memory:"):
        super().__init__(path)
        migrate(self.db)

    def remember(self, tenant, shopper, kind, text, written=None):
        rowid = super().remember(tenant, shopper, kind, text, written)
        migrate(self.db)
        return rowid

    def recall(self, tenant, shopper, limit=20, today=None):
        """One shopper's unexpired facts at one tenant, newest first."""
        rows = self.db.execute(
            "SELECT kind, text, written FROM memory"
            " WHERE tenant = ? AND shopper = ? AND expires > ?"
            " ORDER BY written DESC, id DESC LIMIT ?",
            owner(tenant, shopper)
            + (today or date.today().isoformat(), limit))
        return [dict(zip(FIELDS, row)) for row in rows]

    def purge(self, today=None):
        """Delete expired rows for every tenant; return the count."""
        cur = self.db.execute(
            "DELETE FROM memory WHERE expires <= ?",
            (today or date.today().isoformat(),))
        self.db.commit()
        return cur.rowcount


def main():
    store = ExpiringStore()
    seed(store)
    rows = store.recall(TENANT, SHOPPER, today=TODAY)
    print(f"recall({TENANT}, {SHOPPER}) on {TODAY}: "
          + count(len(rows), "row"))
    for row in rows:
        print("  " + line(row))
    messages, _ = pack(QUESTION, gather(rows))
    text = " ".join(m["content"] for m in messages)
    for fact in ("A-0388", "R-A-1001"):
        found = "yes" if fact in text else "no"
        print(f"{fact} in the packed context: {found}")
    print(f"purge({TODAY}): {count(store.purge(TODAY), 'row')} deleted")


if __name__ == "__main__":
    main()
