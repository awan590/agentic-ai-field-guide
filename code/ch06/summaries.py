"""Compact old turns into a summary, and pin the facts it may drop.

Compaction swaps the oldest turns for a short summary the model
writes. Each new summary is written from the last one, so details
fade with every round: order ids, amounts, and dates go first, and
those are what a refund answer needs. This file copies them out of
the old turns with a pattern and pins them under the summary, where
no rewrite can lose them. The stand-in model plays back two
summaries a real model could write. The chat is synthetic.

    python -m ch06.summaries
"""
import re

from ch02.stub_model import StandInModel

FACT = re.compile(r"R-A-\d{4}|A-\d{4}|\$\d+\.\d\d|\d{4}-\d\d-\d\d")
PIN = "Pinned: "
KEEP = 2
TURNS = [
    ("user", "Order A-1001 came on 2026-10-29 with two bent clamps."),
    ("assistant", "Sorry. I filed refund request R-A-1001 for $15.90."),
    ("user", "Please email me about it. No phone calls."),
    ("assistant", "Noted: email only. A person reviews it first."),
    ("user", "Do you still have the HC-038 clamps?"),
    ("assistant", "Yes, 120 are in stock."),
]
MORE = [
    ("user", "When will the refund be paid?"),
    ("assistant", "After review, in 5 to 10 business days."),
]
SUMMARIES = [
    "Shopper reported bent clamps on A-1001; a refund was filed.",
    "Shopper had an order problem and was offered a refund.",
]


def pinned(turns):
    """Ids, amounts, and dates, in the order they first appear."""
    found = FACT.findall(" ".join(text for _, text in turns))
    return list(dict.fromkeys(found))


def compact(turns, model, keep=KEEP):
    """Swap all but the last few turns for one summary turn."""
    old, recent = turns[:-keep], turns[-keep:]
    chat = "\n".join(f"{role}: {text}" for role, text in old)
    reply = model.complete(
        [{"role": "user", "content": "Summarize briefly:\n" + chat}],
        [])
    note = reply["content"] + "\n" + PIN + ", ".join(pinned(old))
    return [("system", note)] + recent


def main():
    model = StandInModel([{"content": s} for s in SUMMARIES])
    turns = list(TURNS)
    for n, more in enumerate([MORE, []], 1):
        facts = pinned(turns[:-KEEP])
        size = len(turns)
        turns = compact(turns, model)
        summary, pins = turns[0][1].split("\n")
        lost = [f for f in facts if f not in summary]
        print(f"round {n}: {size} turns -> {len(turns)}")
        print(f"  summary: {summary}")
        print(f"  missing from summary: {', '.join(lost) or 'none'}")
        print(f"  {pins}")
        turns += more


if __name__ == "__main__":
    main()
