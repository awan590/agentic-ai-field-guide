"""Chapter 4 demos. Each runs offline in well under a second.

    python -m ch04.demo schema              # bad arguments refused
    python -m ch04.demo retry               # a lost reply, retried
    python -m ch04.demo delete              # destroy needs a person
    python -m ch04.demo agent               # the ch02 loop, guarded
    python -m ch04.demo break busy busy busy    # break the API
"""
import json
import sys
import textwrap

from ch02.mini_agent import print_trace, run_agent
from ch02.stub_model import StandInModel
from ch04.payments import Busy, FakeClock, Payments
from ch04.tools import Guard, OrderDesk, make_tools


def setup(script=(), approver=None):
    clock = FakeClock()
    desk = OrderDesk(Payments(clock, script))
    return desk, Guard(make_tools(desk), clock, approver=approver)


def show(result):
    """Print each field on its own lines, wrapped to fit the page."""
    for name, value in result.items():
        text = value if isinstance(value, str) else json.dumps(value)
        print(textwrap.fill(f"{name}: {text}", 72,
                            subsequent_indent=" " * (len(name) + 2)))


def schema():
    desk, guard = setup()
    for args in [
        {"order_id": "A-1O03", "amount": 12.65, "reason": "damaged"},
        {"order_id": "A-1003", "amount": "12.65", "reason": "broke"},
        {"order_id": "A-1003", "amount": 12.65, "reason": "damaged",
         "approved": True},
    ]:
        show({"args": args})
        show(guard.call("issue_refund", args))
        print()
    print(f"payments API calls: {desk.payments.calls}")


def naive_refund(api, order_id, amount, tries=3):
    """The retry loop most code starts with: no key, no backoff."""
    for _ in range(tries):
        try:
            return api.pay(order_id, amount)
        except (TimeoutError, Busy):
            continue


def retry():
    api = Payments(FakeClock(), ["lost", "lost", "ok"])
    naive_refund(api, "A-1003", 12.65)
    print(f"no key:   {api.calls} tries, {len(api.payouts)} payouts, "
          f"{api.total_paid():.2f} paid")
    desk, guard = setup(["lost", "lost", "ok"])
    args = {"order_id": "A-1003", "amount": 12.65,
            "reason": "damaged"}
    result = guard.call("issue_refund", args)
    api = desk.payments
    print(f"with key: {api.calls} tries, {len(api.payouts)} payout,  "
          f"{api.total_paid():.2f} paid")
    print()
    print("\n".join(guard.log))
    show(result)


def delete():
    def person(name, args, preview):
        show({"preview": preview})
        print("person: yes")
        return True

    args = {"order_id": "A-1004"}
    for label, approver in [("no approver set", None),
                            ("a person is asked", person)]:
        print(f"-- {label}")
        desk, guard = setup(approver=approver)
        show(guard.call("delete_order", args))
    print("-- the same call again")
    show(guard.call("delete_order", args))
    print(f"orders left: {len(desk.orders)}; "
          f"deletes run: {len(desk.history)}")


def refund(order_id, amount):
    return {"name": "issue_refund",
            "args": {"order_id": order_id, "amount": amount,
                     "reason": "damaged"}}


TASK = "A-1003 came with a cracked fitting. Refund it."
LOOKUP = {"name": "get_order", "args": {"order_id": "A-1003"}}


def agent():
    desk, guard = setup(["lost", "ok"])
    script = [
        {"tool_calls": [LOOKUP]},
        {"content": "Refunding one fitting.",
         "tool_calls": [refund("A-1003", "12.65")]},
        {"content": "Amount as a number.",
         "tool_calls": [refund("A-1003", 12.65)]},
        {"content": "Refunded $12.65 for the cracked fitting."},
    ]
    result = run_agent(StandInModel(script), guard.registry(), TASK)
    print_trace(result)
    show(result["trace"][6]["result"])
    print("\n".join(guard.log))
    print(f"payouts: {len(desk.payments.payouts)}")


def broken(outcomes):
    desk, guard = setup(outcomes or ["busy"] * 3)
    script = [
        {"tool_calls": [LOOKUP]},
        {"content": "Refunding one fitting.",
         "tool_calls": [refund("A-1003", 12.65)]},
        {"content": "The refund is with a person to confirm today."},
    ]
    result = run_agent(StandInModel(script), guard.registry(), TASK)
    print_trace(result)
    print("\n".join(guard.log))
    show(result["trace"][-3]["result"])
    print(f"payouts: {len(desk.payments.payouts)}")


def main(argv):
    mode = argv[0] if argv else "agent"
    if mode == "break":
        broken(argv[1:])
    else:
        {"schema": schema, "retry": retry, "delete": delete,
         "agent": agent}[mode]()


if __name__ == "__main__":
    main(sys.argv[1:])
