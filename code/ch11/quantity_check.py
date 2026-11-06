"""Sanity limits on order quantities, checked in code.

    python -m ch11.quantity_check
    python -m ch11.quantity_check drive "water cup=18000"

A voice agent turns speech into an order: lines of item and
quantity. This check runs after the model has parsed the order and
before anything reaches the order system, so the model never decides
whether 18,000 is sane. Every limit here is the book's own synthetic
number, not any restaurant's or supplier's.
"""
import sys

from ch02.store import ORDERS
from ch04.tools import fail

DRIVE = {"name": "drive-through menu",
         "max_line": {"taco": 20, "burrito": 20, "large drink": 10,
                      "water cup": 10},
         "max_units": 40}
PARTS = {"name": "Example Supply parts",
         "max_line": {i["sku"]: 50 for o in ORDERS.values()
                      for i in o["items"]},
         "max_units": 200}
LIMITS = {"drive": DRIVE, "parts": PARTS}
FIX = "Read the order back, or hand off to a person."


def check(lines, limits):
    """Return the problems with an order; an empty list means sane."""
    problems, totals, units = [], {}, 0
    for item, qty in lines:
        if item not in limits["max_line"]:
            problems.append(f"{item!r} is not on the {limits['name']}")
        elif type(qty) is not int or qty < 1:
            problems.append(f"{item}: {qty!r} is not a whole number "
                            "from 1 up")
        else:
            totals[item] = totals.get(item, 0) + qty
    for item, qty in totals.items():
        top = limits["max_line"][item]
        if qty > top:
            problems.append(f"{item}: {qty:,} is over the limit of "
                            f"{top} per line")
        else:
            units += qty
    if units > limits["max_units"]:
        problems.append(f"{units} units is over the limit of "
                        f"{limits['max_units']} per order")
    return problems


def verdict(lines, limits):
    """What the order tool returns: the order passes, or an error."""
    problems = check(lines, limits)
    if problems:
        return fail("; ".join(problems), FIX)
    return {"ok": True, "units": sum(qty for _, qty in lines)}


def parse(text):
    """Turn "taco=3, water cup=2" into (item, quantity) pairs."""
    lines = []
    for part in text.split(","):
        item, _, qty = part.partition("=")
        qty = qty.strip()
        lines.append((item.strip(), int(qty) if qty.isdigit() else qty))
    return lines


DEMO = [("drive", "taco=3, large drink=2"),
        ("drive", "water cup=18000"),
        ("drive", "taco=0, water cup=two"),
        ("drive", "taco=20, burrito=20, water cup=4"),
        ("parts", "CT-100=10, HC-038=2"),
        ("parts", "CT-100=1000")]


def main(args):
    runs = [(args[0], " ".join(args[1:]))] if args else DEMO
    print("Synthetic limits, not any real menu or catalog.")
    for name, text in runs:
        result = verdict(parse(text), LIMITS[name])
        if "error" in result:
            print(f"REJECT  {name:6}{text}")
            for problem in result["error"].split("; "):
                print(f"        {problem}")
            print(f"        fix: {result['fix']}")
        else:
            print(f"OK      {name:6}{text}  ({result['units']} units)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
