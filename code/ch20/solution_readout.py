"""Solution to the Chapter 20 task: the one-page pilot readout.

write() builds the page from the gate's own numbers. check() reads
a page you wrote by hand and lists what is missing or wrong.

    python -m ch20.solution_readout               # print the page
    python -m ch20.solution_readout check FILE    # check your page
"""
import sys
from pathlib import Path

from ch20.go_no_go import decide, fingerprint, load
from ch20.pilot_vs_control import load_weeks, readout

HEADINGS = ["## Decision", "## Scorecard", "## Lift",
            "## Guardrails", "## Next step", "## Sign-off"]
NEXT = {"SCALE": "plan go-live for all returns tickets and keep "
                 "a 5% control group for four weeks",
        "FIX": "make the named fix, sign new criteria, and run "
               "two more weeks",
        "STOP": "switch the pilot off and write down what it taught"}


def run_gate():
    criteria = load("criteria.json")
    result = readout(load_weeks(criteria["weeks"]))
    verdict, note, scored = decide(criteria["rules"], result)
    return verdict, note, scored, result, fingerprint(criteria)


def write(verdict, note, scored, result, sha):
    m, n = result["minutes"], result["tickets"]
    r, w = result["reopened"], result["wrong_refund"]
    gate = "GO" if verdict == "SCALE" else "NO-GO"
    lines = ["# Pilot readout: returns desk agent (synthetic data)",
             "", "## Decision", f"{gate}: {verdict} ({note}).",
             "", "## Scorecard", "| Rule | Kind | Limit | Value |"
             " Result |", "|---|---|---|---|---|"]
    for rule, v, ok in scored:
        sign = ">=" if rule["test"] == "count_at_least" else "<="
        lines.append(f"| {rule['name']} | {rule['kind']} | {sign} "
                     f"{rule['limit']:g} | {v:g} | "
                     f"{'PASS' if ok else 'FAIL'} |")
    lines += ["", "## Lift",
              f"Handle minutes {m['lift']:+.2f}, 95% interval "
              f"{m['low']:+.2f} to {m['high']:+.2f}, from "
              f"{n['pilot']} pilot and {n['control']} control "
              "tickets in the same two weeks.",
              "", "## Guardrails",
              f"Reopened {r['lift']:+.2f} points, 95% interval "
              f"{r['low']:+.2f} to {r['high']:+.2f}. Wrong refunds "
              f"{w['pilot']:.2f}% of pilot tickets, "
              f"{w['control']:.2f}% of control tickets.",
              "", "## Next step",
              f"Returns desk lead to {NEXT[verdict]}.",
              "", "## Sign-off",
              "Criteria signed in week 0 by the sponsor, the "
              f"returns desk lead, and the FDE; hash {sha[:12]}."]
    return "\n".join(lines) + "\n"


def check(text, verdict, scored, sha):
    """Return the problems with a readout; empty means OK."""
    problems = [f"missing heading {h}" for h in HEADINGS
                if h not in text]
    decision = text.split("## Decision")[-1].split("##")[0]
    if verdict not in decision:
        problems.append(f"decision does not say {verdict}")
    for rule, v, _ in scored:
        if f"{v:g}" not in text:
            problems.append(f"{rule['name']}: value {v:g} not found")
    if sha[:12] not in text:
        problems.append("sign-off hash missing or wrong")
    return problems


def main(argv):
    verdict, note, scored, result, sha = run_gate()
    if argv[:1] == ["check"]:
        problems = check(Path(argv[1]).read_text(), verdict,
                         scored, sha)
        for p in problems:
            print("  problem:", p)
        print("READOUT FAIL" if problems else "READOUT OK")
        return 1 if problems else 0
    print(write(verdict, note, scored, result, sha), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
