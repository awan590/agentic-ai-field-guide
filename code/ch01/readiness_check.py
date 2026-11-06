"""Score an agent demo against the field-readiness checklist.

Fourteen yes/no checks, two for each of the seven gaps between a demo
and a customer system. A check you cannot confirm counts as "no".
Pass the keys that are true for your demo, for example:

    python -m ch01.readiness_check real_data traces caps
"""
import sys
from typing import NamedTuple


class Check(NamedTuple):
    key: str
    gap: str
    risk: int        # 3 can hurt someone, 2 blocks go-live, 1 slows use
    question: str


CHECKS = [Check(*row) for row in [
    ("real_data", "data", 2, "Runs on the customer's real data"),
    ("data_rights", "data", 3, "Has written approval for that data"),
    ("tool_errors", "tools", 2, "Handles tool errors and timeouts"),
    ("safe_writes", "tools", 3, "Each write is approved or reversible"),
    ("eval_set", "evals", 2, "Scored on an eval set of real tasks"),
    ("baseline", "evals", 1, "Beats a measured baseline"),
    ("injection", "security", 3, "Tested against prompt injection"),
    ("access", "security", 3, "Each tool has only the access it needs"),
    ("cost_known", "cost", 1, "Cost per task is measured"),
    ("caps", "cost", 2, "Step, time, and token caps are set"),
    ("traces", "operations", 2, "Every run leaves a trace"),
    ("owner", "operations", 2, "Named owner and a rollback plan"),
    ("success", "people", 1, "Success measure agreed in writing"),
    ("users_briefed", "people", 1, "Users know what it cannot do"),
]]
LEVEL = {3: "HIGH", 2: "MED", 1: "LOW"}
VERDICT = {3: "stop: close every HIGH gap before real users",
           2: "pilot only, with a person checking each result",
           1: "ready for a go-live review",
           0: "ready for a go-live review"}


def score(yes):
    """Return (passed, gaps), with gaps sorted highest risk first."""
    unknown = set(yes) - {c.key for c in CHECKS}
    if unknown:
        raise ValueError(f"unknown check keys: {sorted(unknown)}")
    gaps = [c for c in CHECKS if c.key not in yes]
    gaps.sort(key=lambda c: -c.risk)      # stable: keeps list order
    return len(CHECKS) - len(gaps), gaps


def verdict(gaps):
    return VERDICT[max((c.risk for c in gaps), default=0)]


def report(name, yes, top=3):
    passed, gaps = score(yes)
    print(f"{name}: {passed}/{len(CHECKS)} checks pass")
    for c in gaps[:top]:
        print(f"  {LEVEL[c.risk]:<4} {c.gap:<10} {c.question}")
    if len(gaps) > top:
        print(f"  plus {len(gaps) - top} more gaps")
    print(f"  verdict: {verdict(gaps)}")


SAMPLES = {
    "Conference demo, refund agent": {"traces"},
    "Two-week pilot, order agent": {
        "real_data", "data_rights", "tool_errors", "safe_writes",
        "eval_set", "caps", "traces", "success"},
    "Week 12, order agent": {
        c.key for c in CHECKS} - {"baseline", "users_briefed"},
}


def main(argv):
    if argv:
        report("Your demo", set(argv))
        return
    for i, (name, yes) in enumerate(SAMPLES.items()):
        if i:
            print()
        report(name, yes)


if __name__ == "__main__":
    main(sys.argv[1:])
