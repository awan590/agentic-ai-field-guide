"""Score each action and data type by harm, undo, and volume.

    python -m ch18.risk_tier

Harm is the worst result of one wrong use. Undo is how hard that
result is to reverse. Volume is how often the agent does it in a day.
Each is rated 1 (low) to 3 (high), and the score is their product,
1 to 27. The tier caps the dial setting an action may get
(autonomy_dial.py). The ratings are synthetic, for Example Supply's
returns desk.
"""
import sys

ACTIONS = {                  # action: (harm, undo, volume)
    "get_order": (1, 1, 3),
    "search_policy": (1, 1, 3),
    "read_message": (1, 1, 3),
    "send_email": (1, 3, 3),
    "cancel_order": (2, 2, 1),
    "issue_refund": (3, 3, 2),
    "export_customers": (3, 3, 1),
}
DATA = {                     # data type: (harm, undo, volume)
    "policy pages": (1, 1, 3),
    "order status": (1, 3, 3),
    "shopper email": (1, 3, 3),
    "card number": (3, 3, 1),
}
DATA_RULE = {1: "any reply", 2: "its owner only",
             3: "never in a reply or a log"}


def tier(harm, undo, volume):
    """Return tier 1, 2, or 3 for one action or data type."""
    if harm == 3 and undo == 3:
        return 3  # severe and permanent: tier 3 at any volume
    score = harm * undo * volume
    if score <= 3:
        return 1
    return 2 if score <= 9 else 3


def main():
    print("Synthetic ratings, returns desk (1 low, 3 high)")
    print(f"{'kind':8}{'name':18}harm undo volume score tier")
    for kind, table in (("action", ACTIONS), ("data", DATA)):
        for name, (h, u, v) in table.items():
            print(f"{kind:8}{name:18}{h:4}{u:5}{v:7}{h * u * v:6}"
                  f"{tier(h, u, v):5}")
    for t, rule in DATA_RULE.items():
        print(f"data in tier {t}: {rule}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
