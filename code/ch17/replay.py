"""The opening case replayed: a plan with no baseline, checked.

PLAN is a value hypothesis for the returns desk written the way the
case's first contract reads in the press: a goal, a deadline, and a
sponsor, with no measured numbers and no stop rule. The text is
invented for the book. check() lists what the plan lacks.

    python -m ch17.replay
"""
import sys

from ch17.baseline import load, summary
from ch17.solution_hypothesis import check

PLAN = """\
# Value hypothesis: Example Supply returns desk

## Problem
The returns desk is slow, and shoppers complain.

## Hypothesis
An agent built in 6 months will answer returns questions.

## Sign-off
Sponsor (head of customer service):
"""


def main(argv):
    problems = check(PLAN, summary(load(*argv[:1])))
    print("A plan shaped like the case, checked against the baseline:")
    for p in problems:
        print("  " + p)
    print(f"{len(problems)} problems: not ready to sign")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
