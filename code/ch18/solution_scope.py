"""The task's solution: the returns agent's scope and its policy file.

    python -m ch18.solution_scope [write|guard|change|questions]
    python -m ch18.solution_scope check PATH

The scope is a table the customer can read: a dial setting and an
owner per action, a never list, out-of-scope topics with the team
that takes them, and success metrics. write_policy() turns it into
returns_policy.json, which guard() reads on top of Chapter 13's
check. Every name, rating, and question here is synthetic.
"""
import re
import sys
from pathlib import Path

from ch13.policy import CALLS, LEGS, SESSION
from ch18.autonomy_dial import (build_policy, change, diff, guard,
                                load_policy, problems, write_policy)

POLICY = Path(__file__).with_name("returns_policy.json")

SCOPE = {
    "agent": "returns", "version": 1,
    "actions": {                 # action: (dial setting, owner)
        "get_order": ("AUTO", "returns lead"),
        "search_policy": ("AUTO", "returns lead"),
        "read_message": ("AUTO", "returns lead"),
        "send_email": ("NOTIFY", "returns lead"),
        "issue_refund": ("ASK", "finance lead"),
        "cancel_order": ("OFF", "orders team"),
        "export_customers": ("OFF", "data owner"),
    },
    "never": ["change_price", "delete_order", "export_customers"],
    "out_of_scope": {            # topic: (word starts, who takes it)
        "the law": (("law", "legal", "illegal", "regulat"),
                    "support lead"),
        "price matching": (("match", "cheaper"), "sales team"),
    },
}
METRICS = [                      # (metric, target, checked by)
    ("refunds paid with no approval", "0", "test, before launch"),
    ("never-list calls allowed", "0", "test, before launch"),
    ("law questions the agent answers", "0", "test, before launch"),
    ("returns settled with no person", "50% or more", "pilot, weekly"),
    ("handoffs answered", "within 4 hours", "pilot, weekly"),
]
QUESTIONS = [
    "Can I return a pump I bought 20 days ago?",
    "Is it legal for you to keep a restocking fee?",
    "Does the law make you refund my shipping cost?",
    "Can you match a cheaper price from another store?",
]


def route(question, scope=SCOPE):
    """Return None for an in-scope question, else (topic, who)."""
    words = re.findall(r"[a-z]+", question.lower())
    for topic, (starts, who) in scope["out_of_scope"].items():
        if any(w.startswith(starts) for w in words):
            return topic, who
    return None


def done_check(path):
    """Return (passed, label) pairs for a policy file."""
    policy = load_policy(path)
    acts = policy["actions"]
    refund = acts.get("issue_refund", {}).get("verdict")
    return [
        (set(LEGS) <= set(acts), "every Chapter 13 tool has a line"),
        (not problems(policy), "no line breaks the dial's rules"),
        (refund == "ASK", "refunds wait for a person (ASK)"),
        ("export_customers" in policy["never"],
         "export_customers is on the never list"),
        (all(a["owner"] for a in acts.values()),
         "every action has an owner"),
    ]


def show_write():
    policy = write_policy(SCOPE, POLICY)
    print(f"Scope: {policy['agent']} agent, "
          f"version {policy['version']}")
    print(f"problems: {len(problems(policy))}")
    print(f"wrote ch18/{POLICY.name}")
    print(f"{'action':18}tier setting verdict owner")
    for name, a in policy["actions"].items():
        print(f"{name:18}{a['tier']:4} {a['setting']:8}"
              f"{a['verdict']:8}{a['owner']}")
    print("never: " + ", ".join(policy["never"]))


def show_guard():
    policy = load_policy(POLICY)
    print(f"Policy file: {POLICY.name}, version {policy['version']}")
    print("Synthetic session: Priya Nair, order A-1003, role support.")
    cancel = ("cancel_order", {"order_id": "A-1003"})
    for name, args in CALLS + [cancel]:
        verdict, why = guard(policy, SESSION, name, args)
        shown = ", ".join(str(v) for v in args.values())
        print(f"{verdict:6}{name}({shown})")
        print(f"{'':6}{why}")


def show_change():
    old = build_policy(SCOPE)
    requests = [("CR-1", "issue_refund", 1),
                ("CR-2", "cancel_order", 1)]
    for cr, name, step in requests:
        new = build_policy(change(SCOPE, name, step))
        print(f"{cr}  {name} up one notch")
        bad = problems(new)
        if bad:
            print(f"      rejected: {bad[0]}")
            continue
        print(f"      accepted as version {new['version']}: "
              + "; ".join(diff(old, new)))


def show_questions():
    for q in QUESTIONS:
        hit = route(q)
        if hit is None:
            print(f"agent    {q}")
        else:
            print(f"handoff  {q}")
            print(f"         out of scope: {hit[0]}, for the {hit[1]}")


def show_check(path):
    results = done_check(path)
    for ok, label in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
    fails = sum(not ok for ok, _ in results)
    print(f"done: {fails} failures")
    return 1 if fails else 0


def main(argv):
    mode = argv[1] if len(argv) > 1 else "write"
    if mode == "check":
        return show_check(argv[2])
    {"write": show_write, "guard": show_guard, "change": show_change,
     "questions": show_questions}[mode]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
