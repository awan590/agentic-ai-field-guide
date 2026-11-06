"""Baseline numbers for the Example Supply returns desk.

Reads a ticket log and prints volume, handle time, and error rate by
ticket type. The log has one row per closed ticket: id, week, type,
minutes (handle time), and error (1 if the ticket was reopened or
its refund was corrected later). The sample log is synthetic, and
the same log always prints the same table.

    python -m ch17.baseline                # the sample log
    python -m ch17.baseline FILE.csv       # your own export
"""
import csv
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "tickets.csv"
FIELDS = ["id", "week", "type", "minutes", "error"]


def load(path=LOG):
    """Read the log; refuse a file that lacks a column or a row."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in FIELDS
                   if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("log lacks columns: " + ", ".join(missing))
        rows = [{"id": r["id"], "week": int(r["week"]),
                 "type": r["type"], "minutes": float(r["minutes"]),
                 "error": int(r["error"])} for r in reader]
    if not rows:
        raise ValueError("log has no tickets")
    return rows


def stats(rows, weeks):
    """Volume, handle time, error rate, and desk hours for rows."""
    minutes = [r["minutes"] for r in rows]
    errors = sum(r["error"] for r in rows)
    return {"tickets": len(rows),
            "per_week": round(len(rows) / weeks),
            "mean": round(statistics.fmean(minutes), 1),
            "median": round(statistics.median(minutes), 1),
            "error": round(100 * errors / len(rows), 1),
            "hours": round(sum(minutes) / weeks / 60, 1)}


def summary(rows):
    """Numbers by ticket type, most desk hours first, plus all."""
    weeks = len({r["week"] for r in rows})
    groups = {}
    for r in rows:
        groups.setdefault(r["type"], []).append(r)
    types = {t: stats(g, weeks) for t, g in groups.items()}
    every = stats(rows, weeks)
    for s in types.values():
        s["share"] = round(100 * s["tickets"] / every["tickets"])
    every["share"] = 100
    order = sorted(types, key=lambda t: (-types[t]["hours"], t))
    return {"weeks": weeks, "types": {t: types[t] for t in order},
            "all": every}


def report(s):
    """The baseline table as lines of text."""
    head = ("type", "per wk", "share", "mean", "median", "error",
            "hrs/wk")
    out = [f"Returns desk baseline: {s['weeks']} weeks, "
           f"{s['all']['tickets']} tickets (synthetic)",
           f"{head[0]:<16}" + "".join(f"{h:>8}" for h in head[1:])]
    for name, v in [*s["types"].items(), ("all", s["all"])]:
        out.append(f"{name:<16}{v['per_week']:>8}{v['share']:>7}%"
                   f"{v['mean']:>8.1f}{v['median']:>8.1f}"
                   f"{v['error']:>7.1f}%{v['hours']:>8.1f}")
    out.append("mean and median: handle minutes per ticket")
    return out


def main(argv):
    rows = load(argv[0]) if argv else load()
    print("\n".join(report(summary(rows))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
