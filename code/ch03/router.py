"""Route each request to a small or a large model, then score it.

    python -m ch03.router

The eval set is synthetic, and both models are stand-ins with a
fixed, simulated accuracy. The output shows how routing and the
arithmetic work. It is not a measurement of any real model.
"""
import hashlib
import re

from ch03.cost_per_task import load_prices, parts, run_metered

TEMPLATES = [        # (label, request): 25 tasks each, 200 in all
    ("easy", "Has order {a} shipped?"),
    ("easy", "What is in order {a}?"),
    ("easy", "What is the total of order {a}?"),
    ("easy", "When was order {a} placed?"),
    ("hard", "Order {a} came damaged. Refund it."),
    ("hard", "Can I still return order {a}?"),
    ("hard", "Orders {a} and {b}: which one ships first?"),
    ("hard", "Where is order {a}? It is a week late."),
]
ACCURACY = {         # simulated share right, by tier and label
    "small": {"easy": 0.97, "hard": 0.70},
    "large": {"easy": 0.98, "hard": 0.95},
}
SHAPES = {"easy": "lookup", "hard": "refund"}   # Chapter 2 demos
HARD_WORDS = re.compile(r"refund|return|damaged|cancel", re.I)
ORDER_ID = re.compile(r"\bA-\d{4}\b")


def labeled_tasks(per_template=25):
    """The eval set: an id, the request, and a person's label."""
    tasks = []
    for label, text in TEMPLATES:
        for _ in range(per_template):
            n = 1101 + len(tasks)
            tasks.append({"id": f"T{n - 1100:03d}", "label": label,
                          "text": text.format(a=f"A-{n}",
                                              b=f"A-{n + 200}")})
    return tasks


def route(text):
    """Send a request to the large tier if it looks hard."""
    if HARD_WORDS.search(text) or len(ORDER_ID.findall(text)) > 1:
        return "large"
    return "small"


def stand_in_right(tier, task):
    """Is this tier's stand-in right on this task? Always the same.

    Both tiers share one draw per task, so a task the small model
    gets right, the large model gets right too.
    """
    digest = hashlib.sha256(task["id"].encode()).digest()
    draw = int.from_bytes(digest[:4], "big") / 2**32
    return draw < ACCURACY[tier][task["label"]]


def evaluate(tasks, choose, prices):
    """Accuracy in percent and dollars per 1,000 tasks for a rule."""
    calls = {label: run_metered(demo)[2]
             for label, demo in SHAPES.items()}
    right, dollars, small = 0, 0.0, 0
    for task in tasks:
        tier = choose(task["text"])
        price = prices["models"][prices["tiers"][tier]]
        right += stand_in_right(tier, task)
        dollars += sum(parts(calls[task["label"]], price).values())
        small += tier == "small"
    return {"accuracy": 100 * right / len(tasks), "small": small,
            "cost": 1000 * dollars / len(tasks)}


def report(rules, tasks, prices):
    """Print one line per routing rule."""
    print(f"{len(tasks)} synthetic tasks, stand-in models, "
          f"prices as of {prices['as_of']}")
    print("rule          to small   accuracy   $ per 1,000 tasks")
    for name, choose in rules.items():
        r = evaluate(tasks, choose, prices)
        print(f"{name:<12}{r['small']:>9}{r['accuracy']:>10.1f}%"
              f"{r['cost']:>19.2f}")


def main():
    tasks = labeled_tasks()
    report({"all large": lambda text: "large",
            "all small": lambda text: "small",
            "route()": route}, tasks, load_prices())
    missed = [t for t in tasks
              if t["label"] == "hard" and route(t["text"]) == "small"]
    print(f"hard tasks sent to small: {len(missed)}")
    print(f"first one: {missed[0]['text']}")


if __name__ == "__main__":
    main()
