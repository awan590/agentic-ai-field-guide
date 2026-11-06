"""Read a pilot against its control group, with a 95% interval.

Each ticket goes to the pilot or the control by a hash of its id,
so both groups share the same weeks. Lift is the pilot mean minus
the control mean. The interval comes from a seeded bootstrap:
resample each group 2,000 times and keep the middle 95% of lifts.
Rates are in percent, so a rate's lift is in points.

    python -m ch20.pilot_vs_control            # both weeks pooled
    python -m ch20.pilot_vs_control week1      # one week's readout
"""
import csv
import hashlib
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
METRICS = [("minutes", "handle minutes"),
           ("reopened", "reopened %"),
           ("wrong_refund", "wrong refund %")]
RATES = ("reopened", "wrong_refund", "handoff")


def arm_for(ticket_id, pilot_share=50):
    """Same id, same group, on every run and every machine."""
    digest = hashlib.sha256(ticket_id.encode()).hexdigest()
    if int(digest, 16) % 100 < pilot_share:
        return "pilot"
    return "control"


def to_row(t):
    """A ticket as numbers, with each rate in percent."""
    row = {"id": t["id"], "arm": t["arm"],
           "minutes": float(t["minutes"])}
    for key in RATES:
        row[key] = float(t[key]) * 100
    return row


def load_weeks(names):
    rows = []
    for name in names:
        with open(HERE / f"{name}.csv", newline="") as f:
            rows += [to_row(t) for t in csv.DictReader(f)]
    return rows


def mean(xs):
    return sum(xs) / len(xs)


def lift(pilot, control, reps=2000, seed=20):
    """Point lift and a percentile bootstrap 95% interval."""
    rng = random.Random(seed)
    lifts = sorted(mean(rng.choices(pilot, k=len(pilot)))
                   - mean(rng.choices(control, k=len(control)))
                   for _ in range(reps))
    low, high = lifts[int(reps * 0.025)], lifts[int(reps * 0.975) - 1]
    return mean(pilot) - mean(control), low, high


def readout(rows, reps=2000, seed=20):
    pilot = [r for r in rows if r["arm"] == "pilot"]
    control = [r for r in rows if r["arm"] == "control"]
    out = {"tickets": {"pilot": len(pilot), "control": len(control)}}
    for key, _ in METRICS:
        p = [r[key] for r in pilot]
        c = [r[key] for r in control]
        point, low, high = lift(p, c, reps, seed)
        out[key] = {"pilot": mean(p), "control": mean(c),
                    "lift": point, "low": low, "high": high}
    out["handoff"] = {"pilot": mean([r["handoff"] for r in pilot])}
    return out


def show(names, result):
    n = result["tickets"]
    print(f"Readout: {' + '.join(names)} (synthetic tickets)")
    print(f"tickets  pilot {n['pilot']}, control {n['control']}")
    print(f"{'metric':<16}{'pilot':>7}{'control':>9}{'lift':>8}"
          "  95% interval")
    for key, label in METRICS:
        m = result[key]
        print(f"{label:<16}{m['pilot']:7.2f}{m['control']:9.2f}"
              f"{m['lift']:+8.2f}  {m['low']:+.2f} to {m['high']:+.2f}")
    print(f"{'handoff %':<16}{result['handoff']['pilot']:7.2f}"
          "  (pilot only)")


def main(argv):
    names = argv or ["week1", "week2"]
    show(names, readout(load_weeks(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
