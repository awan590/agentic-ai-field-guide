"""The returns flow two ways: a fixed workflow and a free agent.

    python -m ch08.compare          # a small model routes
    python -m ch08.compare rule     # a keyword rule routes
    python -m ch08.compare detail   # one message, then the spread

Both designs answer the same 64 labeled shopper messages, with the
same tools. The messages are synthetic and every model is a
stand-in. Whether a model decision is right is a seeded draw with
the chance in STEP_RIGHT: an assumption, not a measurement. Tokens
use Chapter 2's estimate, dollars Chapter 3's dated price file,
and seconds the simulated times in SECONDS.
"""
import hashlib
import json
import re
import sys

from ch02.mini_agent import run_agent, tool
from ch02.store import ORDERS, get_order
from ch02.stub_model import StandInModel, estimate_tokens
from ch03.cost_per_task import Meter, load_prices, parts

STEP_RIGHT = 0.97    # simulated chance that one decision is right
SECONDS = {"small": 0.4, "large": 1.2, "tool": 0.2}    # simulated
ORDER_ID = re.compile(r"\bA-\d{4}\b")

ROUTINE = [          # (shopper message, what the shopper asks for)
    ("Where is order {id}?", "status"),
    ("Has order {id} shipped yet?", "status"),
    ("When will order {id} arrive?", "status"),
    ("Order {id} arrived damaged. Refund it, please.", "refund"),
    ("The parts in order {id} came bent. I want my money back.",
     "refund"),
    ("Can I return order {id}?", "return"),
]
ODD = [              # no fixed path was written for these
    ("Hi, this is {name}. A part from my last order broke.",
     "refund"),
    ("The box for order {id} was empty. My lawyer will call.",
     "person"),
]


def policy(ask, order):
    """The store's rule for one request, written once as code."""
    if ask in ("refund", "return") and order["status"] != "delivered":
        return "status"          # not delivered: say where it is
    return ask


def labeled_cases():
    """Every template for every order, with the right action."""
    cases = []
    for odd, templates in ((False, ROUTINE), (True, ODD)):
        for text, ask in templates:
            for order in ORDERS.values():
                cases.append({
                    "id": f"C{len(cases) + 1:02d}", "odd": odd,
                    "label": "other" if odd else ask,
                    "text": text.format(id=order["id"],
                                        name=order["customer"]),
                    "order": order["id"],
                    "want": policy(ask, order)})
    return cases


def right(case, who, decisions):
    """Are all of these model decisions right? Always the same."""
    seed = hashlib.sha256(f"{case['id']}/{who}".encode()).digest()
    draw = int.from_bytes(seed[:4], "big") / 2**32
    return draw < STEP_RIGHT ** decisions


class Run:
    """Dollars and simulated seconds for one task."""

    def __init__(self, prices):
        self.prices, self.dollars, self.seconds = prices, 0.0, 0.0

    def price(self, tier):
        return self.prices["models"][self.prices["tiers"][tier]]

    def ask(self, tier, prompt, text, out):
        """One model call with no tools: price it, time it."""
        p = self.price(tier)
        self.dollars += (estimate_tokens(prompt, text) * p["input"]
                         + estimate_tokens(out) * p["output"]) / 1e6
        self.seconds += SECONDS[tier]
        return out

    def tool(self, fn, *args):
        self.seconds += SECONDS["tool"]
        return fn(*args)


def find_orders(name):
    return [o["id"] for o in ORDERS.values() if o["customer"] == name]


def done(action):
    return lambda order_id: {"done": action, "order_id": order_id}


ID = {"type": "string", "description": "Order id, such as A-1001"}
TOOLS = {            # both designs use these same tools
    "get_order": tool(get_order, "Look up one order by its id.",
                      order_id=ID),
    "find_orders": tool(find_orders, "List order ids for a name.",
                        name={"type": "string",
                              "description": "Shopper's full name"}),
    "issue_refund": tool(done("refund"),
                         "Refund a delivered order in full.",
                         order_id=ID),
    "send_return_label": tool(done("return"),
                              "Email a return label for a delivered "
                              "order.", order_id=ID),
    "hand_off": tool(done("person"), "Pass the case to a person.",
                     order_id=ID),
}
TOOL_FOR = {"refund": "issue_refund", "return": "send_return_label",
            "person": "hand_off"}
REPLY = {"status": "Order {id} is {status}.",
         "refund": "We refunded ${total} for order {id}.",
         "return": "A return label for order {id} is in your email."}

ROUTER_PROMPT = ("Label the shopper message status, refund, return, "
                 "or other. Reply with the label only.")
REPLY_PROMPT = "Write a short, polite reply that states this fact."
AGENT_PROMPT = (
    "You answer shoppers for Example Supply, an online parts store. "
    "Look up the order before you act. Refund or send a return "
    "label only for a delivered order; if it has not arrived, say "
    "where it is. Hand legal threats and anything unclear to a "
    "person. Reply in two sentences or fewer.")
WRONG = {"status": "refund", "refund": "status", "return": "status",
         "other": "status"}       # where a wrong label sends a case
RULES = [("refund", r"refund|damaged"), ("return", r"\breturn\b"),
         ("status", r"where is|shipped|arrive")]


def model_router(case, run):
    """A small model labels the message. The stand-in knows the
    case's label and gets it wrong when its draw fails."""
    label = case["label"]
    if not right(case, "router", 1):
        label = WRONG[label]
    return run.ask("small", ROUTER_PROMPT, case["text"], label)


def rule_router(case, run):
    """Keywords pick the path: no model call, no draw."""
    for label, pattern in RULES:
        if re.search(pattern, case["text"], re.I):
            return label
    return "other"


def workflow(case, router, run, fallback=None):
    """Fixed path: route, apply the policy in code, then reply.

    What the router labels "other" goes to the fallback; with no
    fallback, it goes to a person. That is the escape hatch.
    """
    label = router(case, run)
    found = ORDER_ID.search(case["text"])
    if label == "other" or not found:
        return fallback(case, run) if fallback else "person"
    order = run.tool(get_order, found.group())
    action = policy(label, order)
    if action in TOOL_FOR:
        run.tool(TOOLS[TOOL_FOR[action]]["fn"], order["id"])
    run.ask("small", REPLY_PROMPT, json.dumps([action, order]),
            REPLY[action].format(**order))
    return action


def agent_script(case):
    """A right run of the agent, taking the shortest path."""
    def call(tool_name, **args):
        return {"tool_calls": [{"name": tool_name, "args": args}]}
    order = ORDERS[case["order"]]
    steps = [call("get_order", order_id=order["id"])]
    if not ORDER_ID.search(case["text"]):
        steps.insert(0, call("find_orders", name=order["customer"]))
    if case["want"] in TOOL_FOR:
        steps.append(call(TOOL_FOR[case["want"]], order_id=order["id"]))
    text = REPLY.get(case["want"], "A person will contact you.")
    return steps + [{"content": text.format(**order)}]


def agent(case, run, max_steps=6):
    """The whole task to the large model, with tools, in a loop."""
    meter = Meter(StandInModel(agent_script(case)))
    result = run_agent(meter, TOOLS, case["text"], max_steps=max_steps)
    system = estimate_tokens(AGENT_PROMPT)
    run.dollars += sum(parts(meter.calls, run.price("large"),
                             system).values())
    tools_run = sum(e["event"] == "tool_call" for e in result["trace"])
    run.seconds += (len(meter.calls) * SECONDS["large"]
                    + tools_run * SECONDS["tool"])
    if result["stop"] != "done":
        return "person"              # a cap stopped it: escape hatch
    if right(case, "agent", len(meter.calls)):
        return case["want"]
    return "wrong"


def grade(case, action):
    if action == case["want"]:
        return "right"
    return "person" if action == "person" else "wrong"


def evaluate(design, cases, prices):
    """Counts by grade, dollars per 1,000 tasks, seconds per task."""
    result = {"right": 0, "wrong": 0, "person": 0}
    dollars = seconds = 0.0
    for case in cases:
        run = Run(prices)
        result[grade(case, design(case, run))] += 1
        dollars += run.dollars
        seconds += run.seconds
    result["cost"] = 1000 * dollars / len(cases)
    result["seconds"] = seconds / len(cases)
    return result


def report(designs, cases, prices):
    """Print one line per design; return the results by name."""
    odd = sum(c["odd"] for c in cases)
    print(f"{len(cases)} synthetic messages, {odd} odd; stand-in "
          f"models; prices as of {prices['as_of']}")
    print("design        right  wrong  person  $ per 1,000  seconds")
    results = {}
    for name, design in designs.items():
        r = results[name] = evaluate(design, cases, prices)
        print(f"{name:<12}{100 * r['right'] / len(cases):>6.1f}%"
              f"{r['wrong']:>7}{r['person']:>8}{r['cost']:>13.3f}"
              f"{r['seconds']:>9.2f}")
    return results


def detail(cases, prices):
    """One message up close, then the spread over all the messages."""
    designs = {"workflow": lambda c, r: workflow(c, model_router, r),
               "free agent": agent}
    runs = {name: [Run(prices) for _ in cases] for name in designs}
    for name, design in designs.items():
        for case, run in zip(cases, runs[name]):
            design(case, run)
    print(f"one message: {cases[0]['text']}")
    for name, rs in runs.items():
        print(f"{name:<12}${1000 * rs[0].dollars:.4f} per 1,000 tasks, "
              f"{rs[0].seconds:.1f} s")
    meter = Meter(StandInModel(agent_script(cases[0])))
    run_agent(meter, TOOLS, cases[0]["text"])
    price = Run(prices).price("large")
    system = estimate_tokens(AGENT_PROMPT)
    cost = parts(meter.calls, price, system)
    tool_text = meter.calls[0]["tools"] + price["tool_prompt_tokens"]
    print(f"each agent call: {system} tokens of system prompt, "
          f"{tool_text} of tool text")
    print(f"tool text share of the agent's bill: "
          f"{100 * cost['tools'] / sum(cost.values()):.0f}%")
    print(f"all {len(cases)} messages, lowest to highest:")
    for name, rs in runs.items():
        dollars = [1000 * r.dollars for r in rs]
        secs = [r.seconds for r in rs]
        print(f"{name:<12}${min(dollars):.4f} to ${max(dollars):.4f} "
              f"per 1,000 tasks, {min(secs):.1f} to {max(secs):.1f} s")


def main(argv):
    if argv[:1] == ["detail"]:
        return detail(labeled_cases(), load_prices())
    router = rule_router if argv[:1] == ["rule"] else model_router
    print(f"router: {router.__name__}")
    designs = {"workflow": lambda c, r: workflow(c, router, r),
               "free agent": agent}
    prices, cases = load_prices(), labeled_cases()
    results = report(designs, cases, prices)
    flow, free = results["workflow"], results["free agent"]
    print(f"the agent costs {free['cost'] / flow['cost']:.0f} times "
          f"as much and takes {free['seconds'] / flow['seconds']:.1f}"
          " times as long")
    large = dict(prices, tiers={"small": prices["tiers"]["large"],
                                "large": prices["tiers"]["large"]})
    same = evaluate(designs["workflow"], cases, large)
    print(f"with the large tier in the workflow too: "
          f"{free['cost'] / same['cost']:.0f} times")


if __name__ == "__main__":
    main(sys.argv[1:])
