"""Solution to the Chapter 17 task: a one-page value hypothesis.

page() writes the hypothesis from the baseline's own numbers.
check() reads a page you wrote and lists what is missing or does
not match the baseline. The numbers are synthetic.

    python -m ch17.solution_hypothesis               # print the page
    python -m ch17.solution_hypothesis check FILE    # check a page
"""
import re
import sys
from pathlib import Path
from textwrap import fill

from ch17.baseline import load, summary

CANDIDATES = ("refund_status", "return_label", "policy_question")
SAVE = 2.0                 # minutes saved per candidate ticket: a guess
HEADINGS = ["## Problem", "## Baseline", "## Hypothesis",
            "## Measure", "## Stop if", "## Sign-off"]


def numbers(s):
    """The baseline lines every page must carry, as printed text."""
    picked = [s["types"][t] for t in CANDIDATES]
    every = s["all"]
    return {"Tickets per week": str(every["per_week"]),
            "Mean handle minutes": f"{every['mean']:.1f}",
            "Error rate": f"{every['error']:.1f}%",
            "Candidate tickets per week":
                str(sum(p["per_week"] for p in picked)),
            "Candidate hours per week":
                f"{sum(p['hours'] for p in picked):.1f}"}


def page(s):
    """The one-page hypothesis, built from the baseline summary."""
    n = numbers(s)
    cand = int(n["Candidate tickets per week"])
    names = [t.replace("_", " ") for t in CANDIDATES]
    kinds = ", ".join(names[:-1]) + ", and " + names[-1]
    return "\n".join([
        "# Value hypothesis: Example Supply returns desk",
        "(synthetic numbers)", "", "## Problem",
        fill(f"The desk spends {s['all']['hours']:.1f} hours a week "
             f"on {n['Tickets per week']} tickets. {cand} a week are "
             f"{kinds} tickets: look-ups and replies that a draft "
             "could speed up."), "", "## Baseline",
        *[f"- {k}: {v}" for k, v in n.items()],
        fill(f"Source: ch17/tickets.csv, {s['weeks']} weeks, read by "
             "ch17/baseline.py."), "", "## Hypothesis",
        fill(f"If the agent drafts replies to {kinds} tickets, and a "
             "person sends each one, handle time on those tickets "
             f"falls by {SAVE:.1f} minutes or more. That frees about "
             f"{cand * SAVE / 60:.1f} desk hours a week."),
        "", "## Measure",
        fill("Handle minutes and errors per ticket from the ticket "
             "log, pilot against control in the same two weeks."),
        "", "## Stop if",
        "- The pilot saves under 1.0 minute per candidate ticket.",
        f"- The error rate rises above {n['Error rate']}.",
        "- The agent pays a refund with no approval.", "",
        "## Sign-off", "Sponsor (head of customer service):",
        "Returns desk lead:", "FDE:", "Date:"]) + "\n"


def check(text, s):
    """Problems with a hand-written page; an empty list means OK."""
    have = text.splitlines()
    problems = [f"missing heading: {h}" for h in HEADINGS
                if h not in have]
    for label, want in numbers(s).items():
        m = re.search(rf"^- {re.escape(label)}: (\S+)\s*$", text, re.M)
        if not m:
            problems.append(f"missing line: - {label}: {want}")
        elif m.group(1) != want:
            problems.append(f"{label}: page says {m.group(1)}, "
                            f"baseline says {want}")
    if not re.search(r"^Sponsor\b.*:", text, re.M):
        problems.append("no Sponsor line under ## Sign-off")
    return problems


def main(argv):
    s = summary(load())
    if argv[:1] != ["check"]:
        print(page(s), end="")
        return 0
    problems = check(Path(argv[1]).read_text(), s)
    for p in problems:
        print(p)
    print(f"{len(problems)} problems" if problems
          else "OK: every number matches the baseline")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
