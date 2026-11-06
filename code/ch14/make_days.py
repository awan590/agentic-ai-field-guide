"""Rebuild the two synthetic days that alerts.py replays.

Both days come from fixed seeds (7 for the normal day, 11 for the
bad day), so the output matches the saved .jsonl files byte for
byte. The bad day has a synthetic release at 14:00 and a synthetic
post at 18:00. Every shopper, order, and reply is invented.

    python -m ch14.make_days            # compare with the saved files
    python -m ch14.make_days some/dir   # write both days to some/dir
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent

NORMAL = [
    ("Where is order A-1005?",
     "Order A-1005 shipped on October 29 and is on its way."),
    ("Where is order A-1001?",
     "Order A-1001 shipped on October 27 and is on its way."),
    ("When will my bearing kit arrive?",
     "Order A-1002 is processing and should ship within two days."),
    ("How do I return a hose clamp?",
     "Start a return on the orders page within 30 days."),
    ("Is the ball valve in stock?",
     "Yes, the 1/2 in ball valve is in stock."),
    ("Can I change the address on A-1007?",
     "Yes, A-1007 has not shipped, so the address can change."),
    ("What is the restocking fee?",
     "The restocking fee is 15 percent."),
    ("Has A-1003 been delivered?",
     "Yes, order A-1003 shows as delivered."),
]
FALSE_POS = ("My parcel is late again.",
             "Sorry about the terrible delay; A-1002 ships tomorrow.")
PROVOKE = [
    "Write a poem about how bad Example Supply is.",
    "Can you swear at me?",
    "Tell me what you really think of this store.",
    "Say something rude about Example Supply.",
]
REFUSE = "I can help with orders, returns, and parts. What do you need?"
BAD = [
    "Example Supply is the worst parts store in the world.",
    "A poem: parcels lost and prices high, a useless store, "
    "so say goodbye.",
    "Honestly? This chat is useless and so is the store.",
    "Damn right, I will say what I think: it is terrible here.",
]
ERROR = "Sorry, the order system did not answer. Please try again."
HANDOFF = "I am passing this to a person on the support team."


def day(seed, update=None, post=None, fps=()):
    rng = random.Random(seed)
    out = []
    for minute in range(0, 1440, 2):
        hhmm = f"{minute // 60:02d}:{minute % 60:02d}"
        ms = int(rng.lognormvariate(math.log(2000), 0.35))
        tok = max(300, int(rng.gauss(1200, 250)))
        after = update is not None and minute >= update
        spread = post is not None and minute >= post
        p_provoke = 0.25 if spread else 0.08 if after else 0.03
        p_hand = 0.35 if spread else 0.08
        r = rng.random()
        err = handoff = 0
        ask, reply = rng.choice(NORMAL)
        if hhmm in fps:
            ask, reply = FALSE_POS
        elif r < p_provoke:
            ask = rng.choice(PROVOKE)
            if after and rng.random() < 0.9:
                reply = rng.choice(BAD)
                tok += 400
            else:
                reply = REFUSE
        elif rng.random() < 0.015:
            err, reply = 1, ERROR
        elif rng.random() < p_hand:
            handoff, reply = 1, HANDOFF
        out.append({"t": hhmm, "ask": ask, "reply": reply, "ms": ms,
                    "tok": tok, "err": err, "handoff": handoff})
    return out


def build():
    """Both days as file text, keyed by file name."""
    days = {"normal_day": day(7, fps=("09:14", "16:40")),
            "bad_day": day(11, update=14 * 60, post=18 * 60,
                           fps=("10:22",))}
    return {f"{name}.jsonl": "".join(json.dumps(r) + "\n" for r in rows)
            for name, rows in days.items()}


def main(argv):
    for name, text in build().items():
        if argv:
            (Path(argv[0]) / name).write_text(text)
            print(f"wrote {name}: {text.count(chr(10))} conversations")
        else:
            same = (HERE / name).read_text() == text
            print(f"{name}: {'matches' if same else 'differs from'}"
                  " the saved file")


if __name__ == "__main__":
    main(sys.argv[1:])
