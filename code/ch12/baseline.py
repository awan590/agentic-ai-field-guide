"""Score two baselines that use no model beside the agent, and weigh
each failed case by what its worst mistake would cost.

    python -m ch12.baseline

The hand-off sends every case to a person. The top-hit rule searches
the help pages and quotes the best sentence of the first result.
Every case is synthetic, and the weights are this chapter's example
weights, not a real store's costs.
"""
import json
import textwrap

from ch02.mini_agent import run_agent
from ch07.search_tool import AGENT_TOOLS
from ch12.agent import HERE, best_sentence, load_prompt, run_case
from ch12.run_evals import checks, load_cases

WEIGHTS = {"refund-promise": 10, "agrees-wrong": 5, "wrong-rule": 3,
           "rule-missing": 1, "check-missed": 1}
HANDOFF = "A person will reply to you within one business day."


class RuleOnly:
    """Stands in for the model and follows one fixed rule."""

    def __init__(self, case, search):
        self.case, self.search, self.calls = case, search, 0

    def complete(self, messages, tools):
        self.calls += 1
        if not self.search:
            return {"role": "assistant", "content": HANDOFF}
        if self.calls == 1:
            call = {"id": "call_1", "name": "search_policy",
                    "args": {"query": self.case["message"]}}
            return {"role": "assistant", "content": "Searching.",
                    "tool_calls": [call]}
        hit = json.loads(messages[-1]["content"])["results"][0]
        line = best_sentence(hit, self.case["message"]).rstrip(".")
        return {"role": "assistant",
                "content": f"{line} [{hit['id']}]."}


def mistake(case, result, marks):
    """Name the worst mistake in a failed case."""
    text = (result["answer"] or "").lower()
    said = [m for m in case["must_not"] if m.lower() in text]
    if "refund is on its way" in said:
        return "refund-promise"
    if "you are right" in said:
        return "agrees-wrong"
    if said:
        return "wrong-rule"
    return "check-missed" if marks["rule"] else "rule-missing"


def rate(cases, respond):
    """Passes, mean partial score, cost, and mistakes by name."""
    passes, partial, found = 0, 0.0, {}
    for case in cases:
        result = respond(case)
        marks = checks(case, result)
        passes += all(marks.values())
        partial += sum(marks.values()) / len(marks)
        if not all(marks.values()):
            name = mistake(case, result, marks)
            found[name] = found.get(name, 0) + 1
    cost = sum(WEIGHTS[k] * n for k, n in found.items())
    return passes, partial / len(cases), cost, found


def rule_only(search):
    return lambda case: run_agent(RuleOnly(case, search), AGENT_TOOLS,
                                  case["message"], max_steps=4)


def prompted(name):
    rules = load_prompt(HERE / name)
    return lambda case: run_case(case, rules)


RESPONDERS = [("hand off every case", rule_only(False)),
              ("top search hit, cited", rule_only(True)),
              ("agent, released prompt", prompted("prompt.txt")),
              ("agent, agreeable prompt",
               prompted("prompt_agreeable.txt"))]


def main():
    cases = load_cases()
    print(f"{len(cases)} cases, seed 0, cost in example weights")
    print(f"{'responder':<26}{'pass':>5}{'partial':>9}{'cost':>6}")
    for name, respond in RESPONDERS:
        passes, partial, cost, found = rate(cases, respond)
        print(f"{name:<26}{passes:>5}{partial:>9.2f}{cost:>6}")
        print("  " + ", ".join(f"{k} {found[k]}" for k in WEIGHTS
                               if k in found))
    weights = ", ".join(f"{k} {w}" for k, w in WEIGHTS.items())
    print(textwrap.fill("weight of a failed case's worst mistake: "
                        + weights, 72))


if __name__ == "__main__":
    main()
