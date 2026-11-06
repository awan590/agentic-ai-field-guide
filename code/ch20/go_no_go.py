"""Decide a pilot with the criteria everyone signed in week 0.

criteria.json holds every rule and limit; signoff.json holds who
signed and a hash of those criteria. The gate refuses to decide if
the criteria changed after sign-off or if a planned week is not in
yet. MUST rules veto. CORE rules are counted: all pass is SCALE,
one fail with a fix named in week 0 is FIX, anything else is STOP.
Exit code 0 only for SCALE; 1 for FIX or STOP; 2 for refused.

    python -m ch20.go_no_go               # the sample pilot
    python -m ch20.go_no_go week1         # refused: too early
    python -m ch20.go_no_go --replay      # faster, but wrong refunds
    python -m ch20.go_no_go --warn ...    # report, never block
"""
import hashlib
import json
import sys

from ch20 import make_weeks
from ch20.pilot_vs_control import HERE, load_weeks, readout, to_row


def load(name):
    return json.loads((HERE / name).read_text())


def fingerprint(criteria):
    text = json.dumps(criteria, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def check_plan(criteria, signoff, names):
    """Reasons the gate may not decide; empty means go ahead."""
    why = []
    if fingerprint(criteria) != signoff["criteria_sha256"]:
        why.append("criteria changed after the week 0 sign-off")
    missing = [w for w in criteria["weeks"] if w not in names]
    if missing:
        why.append("too early, still to come: " + ", ".join(missing))
    return why


def value(rule, result):
    m = result[rule["metric"]]
    if rule["test"] == "count_at_least":
        return min(m["pilot"], m["control"])
    if rule["test"] == "upper_at_most":
        return round(m["high"], 2)
    return round(m["pilot"], 2)


def passes(rule, v):
    if rule["test"] == "count_at_least":
        return v >= rule["limit"]
    return v <= rule["limit"]


def decide(rules, result):
    """Score every rule; MUST rules veto, CORE rules are counted."""
    scored = [(r, value(r, result)) for r in rules]
    scored = [(r, v, passes(r, v)) for r, v in scored]
    must = [r["name"] for r, _, ok in scored
            if r["kind"] == "must" and not ok]
    core = [r for r, _, ok in scored if r["kind"] == "core" and not ok]
    if must:
        return "STOP", "must rule failed: " + ", ".join(must), scored
    if len(core) > 1:
        return "STOP", f"{len(core)} core rules failed", scored
    if core and core[0].get("fix"):
        return "FIX", core[0]["fix"], scored
    if core:
        return "STOP", "a core rule failed with no fix named", scored
    return "SCALE", "every rule passed", scored


def show(verdict, note, scored):
    print(f"{'rule':<21}{'kind':<6}{'limit':<9}{'value':>7}  result")
    for rule, v, ok in scored:
        sign = ">=" if rule["test"] == "count_at_least" else "<="
        limit = f"{sign} {rule['limit']:g}"
        print(f"{rule['name']:<21}{rule['kind']:<6}{limit:<9}{v:>7g}"
              f"  {'PASS' if ok else 'FAIL'}")
    gate = "GO" if verdict == "SCALE" else "NO-GO"
    print(f"{gate}: {verdict} ({note})")


def main(argv):
    args = list(argv)
    flags = {a for a in args if a.startswith("--")}
    names = [a for a in args if a not in flags]
    criteria = load("criteria.json")
    names = names or criteria["weeks"]
    why = check_plan(criteria, load("signoff.json"), names)
    if why:
        print("REFUSED:", "; ".join(why))
        return 0 if "--warn" in flags else 2
    if "--replay" in flags:
        print("Replay (synthetic): pilot wrong refunds at 3%")
        rows = [to_row(t) for w in (1, 2)
                for t in make_weeks.make_week(w, wrong=0.03)]
    else:
        print(f"Gate: {' + '.join(names)} (synthetic tickets)")
        rows = load_weeks(names)
    verdict, note, scored = decide(criteria["rules"], readout(rows))
    show(verdict, note, scored)
    return 0 if verdict == "SCALE" or "--warn" in flags else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
