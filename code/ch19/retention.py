"""Apply retention rules to a trace log and write the kept set.

    python -m ch19.retention [out FILE]

Each record has a kind, and each kind a number of days it may be
kept. A record on hold stays whatever its age. Every record of a
shopper who asked to be forgotten leaves the kept set. A kind with
no rule gets zero days. The log is only read; the kept set goes to
a new file, and this script deletes nothing. The log is synthetic.
"""
import json
import sys
from datetime import date
from pathlib import Path

LOG = Path(__file__).with_name("traces.jsonl")
TODAY = date(2026, 11, 4)
KEEP_DAYS = {"content": 30, "trace": 90, "eval": 365, "incident": 730}
FORGET = {"S-23"}            # shoppers who asked to be erased


def load(path=LOG):
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def decide(rec, today=TODAY, forget=FORGET):
    """Return keep, hold, request, no rule, or age for one record."""
    age = (today - date.fromisoformat(rec["day"])).days
    if rec.get("hold"):
        return "hold"
    if rec["shopper"] in forget:
        return "request"
    if rec["kind"] not in KEEP_DAYS:
        return "no rule"
    return "keep" if age <= KEEP_DAYS[rec["kind"]] else "age"


def apply(records, today=TODAY, forget=FORGET):
    """Split records into the kept set and a verdict for each."""
    verdicts = {r["id"]: decide(r, today, forget) for r in records}
    kept = [r for r in records if verdicts[r["id"]] in ("keep", "hold")]
    return kept, verdicts


def dump(kept, fh):
    """Write records to an open file as JSON lines."""
    for rec in kept:
        fh.write(json.dumps(rec) + "\n")


def write_kept(kept, path):
    """Write the kept set to a new file; refuse to overwrite one."""
    with open(path, "x") as fh:
        dump(kept, fh)


def main(argv):
    records = load()
    kept, verdicts = apply(records)
    print(f"as of {TODAY}, days: " +
          ", ".join(f"{k} {d}" for k, d in KEEP_DAYS.items()))
    for r in records:
        age = (TODAY - date.fromisoformat(r["day"])).days
        print(f"{r['id']}  {r['kind']:9}{r['day']}{age:5}  "
              f"{verdicts[r['id']]}")
    said = list(verdicts.values())
    print(f"kept {len(kept)} of {len(records)}: keep "
          f"{said.count('keep')}, hold {said.count('hold')}")
    print(f"left out {len(records) - len(kept)}: " + ", ".join(
        f"{v} {said.count(v)}" for v in ("age", "request", "no rule")))
    if argv[:1] == ["out"]:
        write_kept(kept, argv[1])
        print(f"wrote {len(kept)} records to {argv[1]}")


if __name__ == "__main__":
    main(sys.argv[1:])
