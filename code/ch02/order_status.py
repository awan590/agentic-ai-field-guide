"""Task solution: an order-status tool for the Example Supply agent.

order_status() returns only what a status question needs, so the
model reads fewer tokens and never sees the customer's name.

    python -m ch02.order_status
"""
from ch02 import mini_agent
from ch02.store import get_order
from ch02.stub_model import StandInModel


def order_status(order_id):
    """Return the id, status, and date placed, or an error dict."""
    order = get_order(order_id)
    if "error" in order:
        return order
    return {key: order[key] for key in ("id", "status", "placed")}


TOOLS = dict(mini_agent.TOOLS, order_status=mini_agent.tool(
    order_status,
    "Status and date placed of one order, such as A-1001. Use it "
    "for 'where is my order' questions instead of get_order.",
    order_id={"type": "string", "description": "Order id"}))

SCRIPT = [
    {"tool_calls": [{"name": "order_status",
                     "args": {"order_id": "A-1005"}}]},
    {"content": "A-1005 shipped. It was placed on October 29."},
]


def main():
    result = mini_agent.run_agent(
        StandInModel(SCRIPT), TOOLS, "Where is my order A-1005?")
    mini_agent.print_trace(result)


if __name__ == "__main__":
    main()
