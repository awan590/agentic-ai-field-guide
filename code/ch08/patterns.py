"""Five workflow patterns, each a small function over a stand-in.

    python -m ch08.patterns            # all five demos
    python -m ch08.patterns chain      # one demo by name

The stand-in model answers each named step with a fixed function,
so every run is offline and prints the same numbers. Tokens use
Chapter 2's estimate. Seconds are simulated: 0.5 per call plus
0.01 per output token. Dollars use Chapter 3's price file, small
tier. None of it measures a real model.
"""
import json
import re
import sys
from collections import Counter

from ch02.store import get_order
from ch02.stub_model import estimate_tokens
from ch03.cost_per_task import load_prices

CALL_SECONDS, TOKEN_SECONDS = 0.5, 0.01      # simulated
ORDER_ID = re.compile(r"\bA-\d{4}\b")


class StandIn:
    """A stand-in model: one reply function per step name.

    Every call records its tokens and moves a simulated clock, so
    a pattern's calls, cost, and seconds can be read afterward.
    """

    def __init__(self, replies):
        self.replies, self.calls, self.clock = replies, [], 0.0

    def ask(self, step, text):
        out = self.replies[step](text)
        call = {"step": step, "input": estimate_tokens(step, text),
                "output": estimate_tokens(out)}
        self.calls.append(call)
        self.clock += CALL_SECONDS + TOKEN_SECONDS * call["output"]
        return out

    def step(self, name):
        """One model step, as a function from text to text."""
        return lambda text: self.ask(name, text)


def chain(steps, text):
    """Prompt chain: each step reads the output of the one before.

    A step is any function from text to text: a model call or
    plain code. A step that returns None stops the chain.
    """
    for step in steps:
        text = step(text)
        if text is None:
            return None
    return text


def route(model, text, handlers):
    """Router: one call picks a path, and the path is fixed code."""
    label = model.ask("classify", text)
    handler = handlers.get(label, handlers["other"])
    return label, handler(text)


def parallel(model, jobs):
    """Run independent (step, text) calls at once."""
    start, ends, outs = model.clock, [], []
    for step, text in jobs:
        model.clock = start              # every call starts together
        outs.append(model.ask(step, text))
        ends.append(model.clock)
    model.clock = max(ends)              # wait for the slowest
    return outs


def vote(model, step, text, n=3):
    """Voting: ask the same question n times; the majority wins."""
    jobs = [(step, f"{text}\n(sample {k})") for k in range(n)]
    answers = parallel(model, jobs)
    return Counter(answers).most_common(1)[0][0], answers


def orchestrate(model, text):
    """Orchestrator-workers: the model makes the plan at run time."""
    plan = json.loads(model.ask("plan", text))
    results = parallel(model, [("work", part) for part in plan])
    return plan, model.ask("join", json.dumps(results))


def refine(model, text, max_rounds=3):
    """Evaluator-optimizer: draft, grade, revise, under a cap."""
    draft = model.ask("draft", text)
    for rounds in range(1, max_rounds + 1):
        verdict = model.ask("grade", draft)
        if verdict == "PASS" or rounds == max_rounds:
            return draft, rounds, verdict == "PASS"
        draft = model.ask("revise", json.dumps([draft, verdict]))


def check_order(facts):
    """A gate in plain code: the order must exist. No model call."""
    facts = json.loads(facts)
    order = get_order(facts["order_id"] or "")
    if "error" in order:
        return None
    return json.dumps(dict(facts, status=order["status"]))


def dollars(calls, price):
    """Dollars for a list of calls at one model's prices."""
    return sum(c["input"] * price["input"]
               + c["output"] * price["output"] for c in calls) / 1e6


# The stand-in's replies, one function per step name. Real models
# would write these; here code writes them so runs never change.

def _extract(text):
    found = ORDER_ID.search(text)
    hurt = re.search(r"crack|broke|damag", text, re.I)
    return json.dumps({"order_id": found and found.group(),
                       "problem": "damaged" if hurt else "other"})


def _draft_reply(facts):
    f = json.loads(facts)
    return (f"Sorry, {f['order_id']} arrived {f['problem']}. "
            "A person will approve a refund.")


def _classify(text):
    if re.search(r"crack|broke|damag|refund", text, re.I):
        return "refund"
    return "status" if re.search(r"where", text, re.I) else "other"


def _plan(text):
    parts = [p.strip(" .?") for p in re.split(r",? and |\. ", text)]
    return json.dumps([p for p in parts if ORDER_ID.search(p)])


def _work(part):
    order = get_order(ORDER_ID.search(part).group())
    return f"{order['id']} is {order['status']}"


def _first_draft(text):
    return "Sorry about the fitting. Your refund is on its way!"


def _grade(draft):
    fixes = []
    if not ORDER_ID.search(draft):
        fixes.append("name the order")
    if "on its way" in draft:
        fixes.append("no refund before approval")
    return "FIX: " + "; ".join(fixes) if fixes else "PASS"


def _revise(pair):
    return "Sorry, A-1003 came cracked. A person will approve a refund."


REPLIES = {
    "extract": _extract, "draft_reply": _draft_reply,
    "classify": _classify, "plan": _plan, "work": _work,
    "join": lambda results: "; ".join(json.loads(results)) + ".",
    "policy": lambda draft: "ok", "tone": lambda draft: "ok",
    "flag": lambda text: "no" if "(sample 1)" in text else "yes",
    "draft": _first_draft, "grade": _grade, "revise": _revise,
}
CRACKED = "Order A-1003 came with a cracked fitting."


def reply_chain(model):
    return [model.step("extract"), check_order,
            model.step("draft_reply")]


def demo_chain(model):
    yield "reply", chain(reply_chain(model), CRACKED)
    typo = CRACKED.replace("A-1003", "A-1O03")
    if chain(reply_chain(model), typo) is None:
        yield "typo", "stopped at the gate; no draft written"


def demo_router(model):
    handlers = {
        "refund": lambda text: chain(reply_chain(model), text),
        "status": lambda text: "{id} is {status}".format(
            **get_order(ORDER_ID.search(text).group())),
        "other": lambda text: "to a person (escape hatch)",
    }
    for text in ("Where is order A-1005?", CRACKED,
                 "My lawyer will call you."):
        label, result = route(model, text, handlers)
        yield label, result


def demo_parallel(model):
    draft = _draft_reply(_extract(CRACKED))
    outs = parallel(model, [("policy", draft), ("tone", draft)])
    yield "sections", f"policy {outs[0]}, tone {outs[1]}"
    winner, answers = vote(model, "flag", "Refund request? " + CRACKED)
    yield "vote", f"{winner} (answers: {', '.join(answers)})"


def demo_orchestrator(model):
    text = ("Order A-1003 came cracked, and A-1005 has not "
            "arrived. Can you check both?")
    plan, answer = orchestrate(model, text)
    yield "plan", json.dumps(plan)
    yield "answer", answer


def demo_evaluator(model):
    draft, rounds, passed = refine(model, CRACKED)
    yield "final", draft
    yield "rounds", f"{rounds}, passed: {passed}"


DEMOS = {"chain": demo_chain, "router": demo_router,
         "parallel": demo_parallel, "orchestrator": demo_orchestrator,
         "evaluator": demo_evaluator}


def main(argv):
    price = load_prices()
    small = price["models"][price["tiers"]["small"]]
    for name in argv or DEMOS:
        model = StandIn(REPLIES)
        print(f"== {name}")
        for label, result in DEMOS[name](model):
            print(f"{label}: {result}")
        tokens = sum(c["input"] + c["output"] for c in model.calls)
        serial = sum(CALL_SECONDS + TOKEN_SECONDS * c["output"]
                     for c in model.calls)
        print(f"calls {len(model.calls)}  tokens {tokens}  "
              f"{model.clock:.2f} s ({serial:.2f} s one by one)  "
              f"${1000 * dollars(model.calls, small):.3f} per 1,000")


if __name__ == "__main__":
    main(sys.argv[1:])
