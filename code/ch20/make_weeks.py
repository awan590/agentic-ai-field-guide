"""Write the two synthetic pilot weeks of returns desk tickets.

Pilot tickets get a draft from the agent and a person approves any
refund; control tickets go to the desk as before. All numbers are
synthetic. The seed makes the same files on every run.

    python -m ch20.make_weeks          # writes week1.csv, week2.csv
"""
import csv
import random
import sys

from ch20.pilot_vs_control import HERE, arm_for

FIELDS = ["id", "week", "arm", "minutes", "reopened",
          "wrong_refund", "handoff"]
# Mean handle minutes. In week 1 the desk is still learning to
# read the agent's drafts, so the pilot gain is smaller.
MINUTES = {("pilot", 1): 8.3, ("pilot", 2): 6.9,
           ("control", 1): 9.0, ("control", 2): 9.1}
REOPEN = {"pilot": 0.07, "control": 0.09}


def make_week(week, n=640, seed=23, wrong=0.003):
    """One week of tickets; wrong is the pilot's wrong refund rate."""
    rng = random.Random(seed * 100 + week)
    rows = []
    for i in range(n):
        tid = f"T{week}-{i:04d}"
        arm = arm_for(tid)
        pilot = arm == "pilot"
        minutes = max(1.0, rng.gauss(MINUTES[arm, week], 3.0))
        rows.append({
            "id": tid, "week": week, "arm": arm,
            "minutes": round(minutes, 1),
            "reopened": int(rng.random() < REOPEN[arm]),
            "wrong_refund": int(rng.random() < (wrong if pilot
                                                 else 0.005)),
            "handoff": int(pilot and rng.random() < 0.22)})
    return rows


def write_week(week, f):
    out = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
    out.writeheader()
    out.writerows(make_week(week))


def main(argv):
    for week in (1, 2):
        with open(HERE / f"week{week}.csv", "w", newline="") as f:
            write_week(week, f)
        print(f"wrote week{week}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
