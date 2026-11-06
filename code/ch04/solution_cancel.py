"""Hands-on task: a cancel_order tool with dry run and approval.

Canceling stops the warehouse from packing an order, and the agent
cannot take that back, so cancel_order is a destroy tool. The guard
in ch04.tools gives it a dry run, a human approval, and a key.

    python -m ch04.solution_cancel
"""
import json

from ch04.payments import FakeClock, Payments
from ch04.tools import ORDER_ID, Guard, OrderDesk, Tool, fail
from ch04.tools import make_tools


def cancel_tool(desk):
    """Build the cancel_order tool for one order desk."""

    def cancel_order(order_id, *, key, timeout, dry_run=False):
        order, error = desk.find(order_id)
        if error:
            return error
        if order["status"] != "processing":
            return fail(f"{order_id} is {order['status']}; only a "
                        "processing order can be canceled",
                        "Offer a return or a refund instead.")
        if dry_run:
            return {"dry_run": True, "would_cancel": order_id,
                    "customer": order["customer"],
                    "total": order["total"]}
        order["status"] = "canceled"
        desk.history.append(("cancel", order_id, key))
        return {"canceled": order_id}

    return Tool(
        "cancel_order", cancel_order,
        "Cancel one order that has not shipped yet. Call get_order "
        "first: only a processing order can be canceled. Every "
        "call shows a dry run and waits for a person to approve. "
        "It cannot be undone; for shipped orders, offer a refund.",
        {"order_id": ORDER_ID}, kind="destroy")


def main():
    desk = OrderDesk(Payments(FakeClock()))

    def approver(name, args, preview):
        print(f"person sees: cancel {preview['would_cancel']} for "
              f"{preview['customer']}, ${preview['total']}")
        print("person: yes")
        return True

    guard = Guard(make_tools(desk) + [cancel_tool(desk)],
                  desk.payments.clock, approver=approver)
    for n in (1, 2):
        result = guard.call("cancel_order", {"order_id": "A-1007"})
        print(f"call {n}: {json.dumps(result)}")
    cancels = [h for h in desk.history if h[0] == "cancel"]
    print(f"A-1007 is {desk.orders['A-1007']['status']}; "
          f"cancels run: {len(cancels)}")


if __name__ == "__main__":
    main()
