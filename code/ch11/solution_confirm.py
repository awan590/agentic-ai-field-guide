"""Chapter 11 task: confirm an order over a limit before placing it.

    python -m ch11.solution_confirm

The quantity check rejects orders no caller could mean. Between sane
and rejected sits a band of orders that are possible but unusual,
such as eight water cups. For those, the agent reads the order back
and places it only after a clear yes. A rejected order stays
rejected, whatever the caller says. CONFIRM_OVER holds the book's
synthetic confirm limits for the drive-through menu.
"""
import sys

from ch11.quantity_check import DRIVE, check, parse

CONFIRM_OVER = {"taco": 8, "burrito": 8, "large drink": 4,
                "water cup": 4}
YES = {"yes", "yes please", "correct", "that is right"}


def decide(lines):
    """Return ("reject", problems), ("confirm", lines) or ("place",)."""
    problems = check(lines, DRIVE)
    if problems:
        return "reject", problems
    totals = {}
    for item, qty in lines:
        totals[item] = totals.get(item, 0) + qty
    big = [(item, qty) for item, qty in totals.items()
           if qty > CONFIRM_OVER[item]]
    return ("confirm", big) if big else ("place",)


def take_order(lines, ask, place):
    """Check one order, confirm it if unusual, then place it or not."""
    step = decide(lines)
    if step[0] == "reject":
        return "handoff", step[1][0]
    if step[0] == "confirm":
        heard = " and ".join(f"{qty} {item}s" for item, qty in step[1])
        answer = ask(f"Just to check: {heard}. Is that right?")
        if answer.strip().lower() not in YES:
            return "not placed", "no clear yes; ask for the order again"
    place(lines)
    return "placed", ""


class Caller:
    """A scripted caller: one recorded answer, every question kept."""

    def __init__(self, answer):
        self.answer, self.heard = answer, []

    def ask(self, question):
        self.heard.append(question)
        return self.answer


DEMO = [("taco=3", "yes"), ("water cup=8", "yes"),
        ("water cup=8", "no, two"), ("water cup=18000", "yes")]


def main():
    placed = []
    for text, answer in DEMO:
        caller = Caller(answer)
        status, why = take_order(parse(text), caller.ask, placed.append)
        print(f"{text:17}{status}")
        for question in caller.heard:
            print(f'{"":17}agent:  "{question}"')
            print(f'{"":17}caller: "{answer}"')
        if why:
            print(f"{'':17}{why}")
    print(f"orders placed: {len(placed)} of {len(DEMO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
