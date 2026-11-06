"""Chapter 3 task: cut cost per task by a third, lose at most a point.

    python -m ch03.solution_cost_cut

route() in router.py saves money but sends a hard request to the
small model whenever its words look easy. In the eval set, a second
sentence explains a problem, so this rule sends any request of more
than one sentence to the large tier.
"""
import re

from ch03.cost_per_task import load_prices
from ch03.router import evaluate, labeled_tasks, report, route

SENTENCE_END = re.compile(r"[.?!](\s|$)")
TARGET_CUT, MAX_LOSS = 100 / 3, 1.0    # percent, accuracy points


def route_safe(text):
    """Like route(), but a request that explains goes to large."""
    if len(SENTENCE_END.findall(text)) > 1:
        return "large"
    return route(text)


def check(base, new):
    """Compare a rule with the baseline against the task's targets."""
    cut = 100 * (1 - new["cost"] / base["cost"])
    loss = base["accuracy"] - new["accuracy"]
    ok = cut >= TARGET_CUT and loss <= MAX_LOSS
    return cut, loss, ok


def main():
    tasks, prices = labeled_tasks(), load_prices()
    rules = {"all large": lambda text: "large", "route()": route,
             "route_safe()": route_safe}
    report(rules, tasks, prices)
    base = evaluate(tasks, rules["all large"], prices)
    for name in ("route()", "route_safe()"):
        new = evaluate(tasks, rules[name], prices)
        cut, loss, ok = check(base, new)
        print(f"{name:<14} cost cut {cut:4.1f}%  accuracy lost "
              f"{loss:3.1f} points  {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
