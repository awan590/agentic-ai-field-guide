"""Find personal data in tables and write a data map.

    python -m ch19.data_map [cap BYTES] [out FILE]

Two scans per column: its name against a list of hints, and every
value against the Chapter 13 patterns for emails, phones, and cards.
A column whose values hold personal data under a name that gives no
hint is flagged when its rows reach the model vendor unmasked. The
tables are synthetic. "out" writes a new CSV and never overwrites.
"""
import csv
import sys

from ch13.pii_filter import CARD, EMAIL, PHONE, mask
from ch19.tables import REACHES, build

NAME_HINTS = {"customer": "name", "name": "name", "email": "email",
              "phone": "phone", "ship": "address", "address": "address",
              "card": "card", "birth": "birth date"}
PATTERNS = {"card": CARD, "email": EMAIL, "phone": PHONE}
MASKED = {"orders.email"}      # masked by ch13 mask() before prompts
FIELDS = ("column", "kind", "found", "hits", "zone", "status")


def columns(db):
    """Yield (table, column) for every column the database holds."""
    tables = db.execute("SELECT name FROM sqlite_master "
                        "WHERE type = 'table' ORDER BY name").fetchall()
    for (table,) in tables:
        for row in db.execute(f'PRAGMA table_info("{table}")'):
            yield table, row[1]


def name_kind(column):
    """Return the kind of personal data a column name hints at."""
    for hint, kind in NAME_HINTS.items():
        if hint in column.lower():
            return kind
    return None


def kinds_in(value):
    """Return the kinds of personal data a value's text matches."""
    return {kind for kind, pattern in PATTERNS.items()
            if pattern.search(value)}


def scan(db, reaches=REACHES, masked=MASKED):
    """Return one data map row per column that holds personal data."""
    rows = []
    for table, col in columns(db):
        values = [str(v) for (v,) in
                  db.execute(f'SELECT "{col}" FROM "{table}"')]
        per_row = [kinds_in(v) for v in values]
        by_name, by_value = name_kind(col), set().union(*per_row)
        if not by_name and not by_value:
            continue
        name = f"{table}.{col}"
        zone = reaches.get(table, "vendor")    # unlisted: assume out
        if name in masked:
            left = any(kinds_in(mask(v)) for v in values)
            status = "FLAG" if left else "masked"
        elif zone == "store":
            status = "stays"
        else:
            status = "sent" if by_name else "FLAG"
        hits = sum(bool(k) for k in per_row)
        rows.append({
            "column": name,
            "kind": by_name or "+".join(sorted(by_value)),
            "found": "both" if by_name and by_value
                     else "name" if by_name else "value",
            "hits": f"{hits}/{len(values)}" if by_value else "-",
            "zone": zone, "status": status})
    return rows


def under_cap(db, column, cap):
    """Count rows with personal data that fit under a byte cap."""
    table, col = column.split(".")
    values = [str(v) for (v,) in
              db.execute(f'SELECT "{col}" FROM "{table}"')]
    hits = [v for v in values if kinds_in(v)]
    return sum(len(v.encode()) <= cap for v in hits), len(hits)


def write_map(rows, path):
    """Write the map as CSV to a new file; refuse to overwrite one."""
    with open(path, "x", newline="") as fh:
        out = csv.DictWriter(fh, FIELDS)
        out.writeheader()
        out.writerows(rows)


def main(argv):
    db = build()
    rows = scan(db)
    if argv[:1] == ["cap"]:
        cap = int(argv[1])
        print(f"cap: {cap} bytes per question")
        for row in rows:
            if row["status"] == "FLAG":
                fit, hits = under_cap(db, row["column"], cap)
                print(f"{row['column']:14} {fit} of {hits} rows "
                      "with personal data fit under the cap")
        return
    if argv[:1] == ["out"]:
        write_map(rows, argv[1])
    print(f"{'column':16}{'kind':12}{'found':7}{'hits':6}"
          f"{'zone':8}status")
    for r in rows:
        print(f"{r['column']:16}{r['kind']:12}{r['found']:7}"
              f"{r['hits']:6}{r['zone']:8}{r['status']}")
    total = sum(1 for _ in columns(db))
    flags = sum(r["status"] == "FLAG" for r in rows)
    print(f"{len(rows)} of {total} columns hold personal data; "
          f"{flags} flagged")


if __name__ == "__main__":
    main(sys.argv[1:])
