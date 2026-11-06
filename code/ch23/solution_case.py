"""Solution to the Chapter 23 task: the one-page business case.

page() writes the case from roi_model's own numbers. check() reads
a case written by hand and lists every line that does not match.

    python -m ch23.solution_case               # print the page
    python -m ch23.solution_case check FILE    # check your page
"""
import re
import sys
from pathlib import Path

from ch23.roi_model import (LABELS, break_even, cost_per_task, inputs,
                            money, months, sensitivity)

HEADINGS = ["## Ask", "## Baseline", "## Cost per task", "## Costs",
            "## Break-even", "## Risks", "## Price", "## Measures",
            "## Sign-off"]
SIGNERS = ["Sponsor", "Finance", "Returns desk lead", "FDE"]


def numbers(x):
    """The lines every business case must carry, as printed text."""
    sides = cost_per_task(x)
    person, agent = (sum(sides[s].values()) for s in sides)
    rows = months(x)
    key, _, good, bad, _ = sensitivity(x)[0]
    doubled = dict(x, error_scale=2 * x["error_scale"])
    return {"Tickets a month": f"{x['tickets_month']:,.0f}",
            "Person cost per task": money(person, 2),
            "Agent cost per task": money(agent, 2),
            "Saving per task": money(person - agent, 2),
            "Build cost": money(x["build"]),
            "Run cost a month": money(x["run_month"]),
            "Break-even month": str(break_even(rows)),
            "Net after 24 months": money(rows[23][3]),
            "Widest input": f"{LABELS[key][0]}, months {good} to {bad}",
            "Break-even with errors doubled":
                str(break_even(months(doubled)))}


def page(x):
    """The one-page business case, built from the model."""
    n = numbers(x)
    line = [f"- {k}: {v}" for k, v in n.items()]
    return "\n".join([
        "# Business case: Example Supply returns agent",
        f"(synthetic numbers from ch23/roi_model.py, {x['as_of']})", "",
        "## Ask", "Approve go-live for all returns tickets. A person",
        "still approves every refund.", "",
        "## Baseline", *line[:2],
        "Source: ch17 baseline and the ch20 control group.", "",
        "## Cost per task", *line[2:4],
        "Both sides pay for handle time, repeat contacts, and wrong",
        "refunds. The agent side adds a review sample and the model.",
        "", "## Costs", *line[4:6], "",
        "## Break-even", *line[6:8],
        "Ramp: " + ", ".join(f"{r:.0%}" for r in x["ramp"])
        + ", then all tickets.", "",
        "## Risks", *line[8:],
        "Firm up the widest input before signing.", "",
        "## Price", "Fixed fee for the build: half at signed scope,",
        "half at go-live. Run cost billed monthly at cost.", "",
        "## Measures", "Monthly: cost per task on both sides, repeat",
        "contacts, wrong refunds, and the cumulative total against",
        "this page. Stop if wrong refunds pass "
        f"{x['intervals']['agent_wrong'][1]:.2f}% of tickets.",
        "", "## Sign-off", *[f"{s}:" for s in SIGNERS], "Date:"]) + "\n"


def check(text, x):
    """Problems with a hand-written case; an empty list means OK."""
    have = text.splitlines()
    problems = [f"missing heading: {h}" for h in HEADINGS
                if h not in have]
    for label, want in numbers(x).items():
        m = re.search(rf"^- {re.escape(label)}: (.+?)\s*$", text, re.M)
        if not m:
            problems.append(f"missing line: - {label}: {want}")
        elif m.group(1) != want:
            problems.append(f"{label}: page says {m.group(1)}, "
                            f"model says {want}")
    for signer in SIGNERS:
        if not re.search(rf"^{signer}\b.*:", text, re.M):
            problems.append(f"no {signer} line under ## Sign-off")
    return problems


def main(argv):
    x = inputs()
    if argv[:1] != ["check"]:
        print(page(x), end="")
        return 0
    problems = check(Path(argv[1]).read_text(), x)
    for p in problems:
        print(p)
    print(f"{len(problems)} problems" if problems
          else "OK: every number matches roi_model.py")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
