"""Write and check a 12-month skills plan against the trend radar.

    python -m ch25.solution_plan              print a starter plan
    python -m ch25.solution_plan check FILE   check your own plan

The plan has four quarters. Each names one skill, the radar entry
behind it, the proof that will show the skill, and the date to
review it. The check refuses entries on hold, entries that are
stale on the plan date, and gaps longer than the radar allows.
"""
import re
import sys
from datetime import date, timedelta

from ch25.radar import RADAR, TODAY, load, stale

ORDER = ("use", "try", "watch")
PROOF = {"use": "one eval case per release, logged",
         "try": "a trial behind the eval gate, with its log",
         "watch": "a dated note and one small test"}
FIELDS = ("Skill", "Radar", "Proof", "Review")


def write(radar, on):
    """Return a starter plan: four fresh entries, use rings first."""
    days = radar["stale_days"]
    fresh = [e for ring in ORDER for e in radar["entries"]
             if e["ring"] == ring and not stale(e, on, days)]
    out = [f"# 12-month skills plan, radar {radar['radar']}, "
           f"on {on}"]
    for q, e in enumerate(fresh[:4], 1):
        review = on + timedelta(days=days * q)
        out += ["", f"## Q{q}", f"Skill: {e['skill']}",
                f"Radar: {e['id']} ({e['ring']})",
                f"Proof: {PROOF[e['ring']]}", f"Review: {review}"]
    return "\n".join(out) + "\n"


def quarters(text):
    """Split a plan into (number, {field: value}) pairs."""
    found = []
    for part in re.split(r"^## ", text, flags=re.M)[1:]:
        head, *lines = part.splitlines()
        m = re.match(r"Q(\d)\b", head)
        fields = dict(re.findall(r"^(\w+):\s*(.+)$", "\n".join(lines),
                                 re.M))
        found.append((int(m.group(1)) if m else 0, fields))
    return found


def check(text, radar):
    """Return the problems in a plan; an empty list means it passes."""
    m = re.search(r"\bon (\d{4}-\d{2}-\d{2})", text.split("\n")[0])
    if not m:
        return ["title line has no plan date (on YYYY-MM-DD)"]
    last = on = date.fromisoformat(m.group(1))
    days = radar["stale_days"]
    entries = {e["id"]: e for e in radar["entries"]}
    found = []
    plan = quarters(text)
    if [q for q, _ in plan] != [1, 2, 3, 4]:
        found.append("want four quarters, ## Q1 to ## Q4, in order")
    for q, fields in plan:
        found += [f"Q{q}: no {f}" for f in FIELDS if f not in fields]
        rid = fields.get("Radar", "").split(" ")[0]
        e = entries.get(rid)
        if "Radar" in fields and e is None:
            found.append(f"Q{q}: {rid} is not on the radar")
        elif e and e["ring"] == "hold":
            found.append(f"Q{q}: {rid} is on hold")
        elif e and stale(e, on, days):
            found.append(f"Q{q}: {rid} is stale on {on}; read it again")
        if "Proof" in fields and not re.search(
                r"\b(test|eval|log)", fields["Proof"]):
            found.append(f"Q{q}: proof names no test, eval, or log")
        try:
            review = date.fromisoformat(fields.get("Review", ""))
        except ValueError:
            found.append(f"Q{q}: bad review date")
            continue
        if not 0 < (review - last).days <= days:
            found.append(f"Q{q}: review {review} is not within {days} "
                         f"days after {last}")
        last = review
    return found


def main(argv):
    radar = load(RADAR)
    if not argv:
        print(write(radar, TODAY), end="")
        return 0
    if len(argv) != 2 or argv[0] != "check":
        print(__doc__)
        return 2
    with open(argv[1]) as fh:
        found = check(fh.read(), radar)
    for p in found:
        print(f"  problem: {p}")
    print("PLAN FAIL" if found else "PLAN OK")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
