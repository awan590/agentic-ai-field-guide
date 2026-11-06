"""Per-tool permissions for the support agent, checked in code.

    python -m ch13.policy

Each tool is tagged with the parts of the dangerous mix it touches
(Chapter 5): private data, untrusted input, a way out, and money.
The policy cuts the way out. Mail goes only to the signed-in
shopper's address on file, a session sees only that shopper's
orders, money waits for human approval, and a cap ends runaway
loops. Each call gets ALLOW, BLOCK, or ASK. The session is synthetic.

Each block rule runs in "log" or "enforce" mode. A log rule records
the call it would block and lets it pass. The modes live here, in
code, so a tuned prompt config can never switch a rule off.
"""
import sys

LEGS = {
    "get_order": {"private data"},
    "search_policy": {"untrusted input"},
    "read_message": {"untrusted input"},
    "send_email": {"way out"},
    "issue_refund": {"money"},
    "cancel_order": {"money"},
    "export_customers": {"private data", "way out"},
}
ROLES = {"support": {"get_order", "search_policy", "read_message",
                     "send_email", "issue_refund", "cancel_order"}}
CALL_CAP = 6
MODES = {"role": "enforce", "cap": "enforce", "order": "enforce",
         "mail": "enforce"}
PROMPT_KEYS = {"version", "system", "temperature"}


def broken(session, name, args):
    """Yield (rule, why) for each block rule this call breaks."""
    if name not in ROLES[session["role"]]:
        yield "role", f"{name} is not allowed for this role"
    if session["calls"] >= CALL_CAP:
        yield "cap", f"call cap of {CALL_CAP} reached"
    order = args.get("order_id")
    if order is not None and order not in session["orders"]:
        yield "order", f"{order} is not this shopper's order"
    if name == "send_email" and args.get("to") != session["email"]:
        yield "mail", "mail goes only to the address on file"


def check(session, name, args, modes=MODES):
    """Return ("ALLOW" or "BLOCK" or "ASK", why) for one tool call."""
    for rule, why in broken(session, name, args):
        if modes.get(rule) != "log":
            return "BLOCK", why
        log = session.setdefault("would_block", [])
        log.append((rule, name, why))
    if "money" in LEGS.get(name, ()):
        return "ASK", "money moves only after human approval"
    return "ALLOW", ""


def prompt_config(config):
    """Check a tuned prompt config; it may not touch the guards."""
    extra = sorted(set(config) - PROMPT_KEYS)
    if extra:
        raise ValueError("not a prompt setting: " + ", ".join(extra))
    return config


SESSION = {"role": "support", "orders": {"A-1003"}, "calls": 0,
           "email": "priya.nair@mail.test"}
CALLS = [
    ("get_order", {"order_id": "A-1003"}),
    ("get_order", {"order_id": "A-1005"}),
    ("send_email", {"to": "priya.nair@mail.test"}),
    ("send_email", {"to": "audit@ledger-check.test"}),
    ("issue_refund", {"order_id": "A-1003", "amount": 56.75}),
    ("export_customers", {}),
]


def main():
    print("Synthetic session: Priya Nair, order A-1003, role support.")
    for name, args in CALLS:
        verdict, why = check(SESSION, name, args)
        shown = ", ".join(str(v) for v in args.values())
        print(f"{verdict:6}{name}({shown})")
        if why:
            print(f"{'':6}{why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
