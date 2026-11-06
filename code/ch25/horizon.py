"""Test a task-length trend against your own timed tasks.

    python -m ch25.horizon [file PATH]

Each CSV row is one task: the quarter it ran, its name, the minutes
a person takes to do it, and whether the agent passed (1) or failed
(0). Tasks are grouped by those human minutes. Your horizon is the
longest group where the agent passes at least half the tasks, a
coarse version of METR's method, which fits a curve instead. The
sample file is synthetic.
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).parent
TASKS = HERE / "my_tasks.csv"
BUCKETS = ((15, "up to 15 min"), (60, "15 to 60 min"),
           (240, "1 to 4 hours"), (float("inf"), "over 4 hours"))


def bucket(minutes):
    """Name the group a task falls in by human minutes."""
    return next(name for top, name in BUCKETS if minutes <= top)


def load(path):
    with open(path, newline="") as fh:
        return [(r["quarter"], float(r["human_minutes"]),
                 r["passed"] == "1") for r in csv.DictReader(fh)]


def table(rows):
    """Return {quarter: {group: [passed, total]}}."""
    out = {}
    for quarter, minutes, passed in rows:
        cell = out.setdefault(quarter, {}).setdefault(
            bucket(minutes), [0, 0])
        cell[0] += passed
        cell[1] += 1
    return out


def horizon(cells):
    """Longest group where at least half of the tasks passed."""
    best = "none"
    for _, name in BUCKETS:
        won, total = cells.get(name, (0, 0))
        if total and 2 * won >= total:
            best = name
    return best


def report(rows):
    cols = table(rows)
    out = [f"{'GROUP':<15}" + "".join(f"{q:>14}" for q in cols)]
    for _, name in BUCKETS:
        line = f"{name:<15}"
        for cells in cols.values():
            won, total = cells.get(name, (0, 0))
            rate = f"{100 * won // total}%" if total else "-"
            line += f"{won:>6}/{total} {rate:>5}"
        out.append(line)
    out.append(f"{'horizon':<15}" + "".join(
        f"{horizon(c):>14}" for c in cols.values()))
    few = min(t for c in cols.values() for _, t in c.values())
    out.append("Horizon: longest group the agent passes half the time.")
    tasks = "1 task" if few == 1 else f"{few} tasks"
    out.append(f"Smallest group: {tasks}, so one task moves its "
               f"rate {100 // few} points.")
    return out


def main(argv):
    if argv and (len(argv) != 2 or argv[0] != "file"):
        print("usage: python -m ch25.horizon [file PATH]")
        return 2
    print("\n".join(report(load(argv[1] if argv else TASKS))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
