"""Cost per task: price one Chapter 2 run with a dated price file.

    python -m ch03.cost_per_task               # the refund demo
    python -m ch03.cost_per_task lookup        # another demo
    python -m ch03.cost_per_task refund 1500   # add a system prompt

Input and output tokens have different prices, so the meter keeps
them apart. Token counts are the stand-in's estimates, not a real
tokenizer's counts.
"""
import json
import sys
from datetime import date
from pathlib import Path

from ch02.mini_agent import DEMOS, TOOLS, run_agent
from ch02.stub_model import StandInModel, estimate_tokens

PRICES = Path(__file__).with_name("prices-2026-11-03.json")
CURRENT = Path(__file__).with_name("prices-2026-11-06.json")
RERUNS = 0.10       # example: 1 task in 10 fails and runs again
WARN_DAYS = 60      # warn this long before a retirement date


def load_prices(path=PRICES):
    """Read a price file and refuse one that has no as_of date."""
    data = json.loads(Path(path).read_text())
    if not data.get("as_of"):
        raise ValueError(f"{path} has no as_of date")
    return data


def retirement_warnings(prices, today=None):
    """Name each model that retires within WARN_DAYS of today."""
    today = today or date.today()
    out = []
    for name, price in prices["models"].items():
        when = price.get("retires_not_before")
        if not when:
            continue
        if (date.fromisoformat(when) - today).days <= WARN_DAYS:
            out.append(f"warning: {name} retires not before {when}")
    return out


class Meter:
    """Wrap a model and record the tokens of every call."""

    def __init__(self, model):
        self.model, self.calls = model, []

    def complete(self, messages, tools):
        reply = self.model.complete(messages, tools)
        self.calls.append({"input": reply["usage"]["input_tokens"],
                           "output": reply["usage"]["output_tokens"],
                           "tools": estimate_tokens(tools)})
        return reply


def run_metered(demo="refund"):
    """Run one Chapter 2 demo and return its task, result, calls."""
    task, script, caps = DEMOS[demo]
    meter = Meter(StandInModel(script))
    result = run_agent(meter, TOOLS, task, **caps)
    return task, result, meter.calls


def parts(calls, price, system=0):
    """Dollars for one run, split into input, tools, and output.

    Every call resends the system prompt, the tool definitions, and
    the tool prompt the provider adds, so all three count each time.
    """
    tokens = {"input": 0, "tools": 0, "output": 0}
    for call in calls:
        tokens["input"] += call["input"] - call["tools"] + system
        tokens["tools"] += call["tools"] + price["tool_prompt_tokens"]
        tokens["output"] += call["output"]
    return {kind: n * price["output" if kind == "output" else "input"]
            / 1_000_000 for kind, n in tokens.items()}


def cached_cost(calls, price, system=0):
    """Dollars for one run when the fixed prefix is cached.

    The prefix is what every call repeats: tool definitions, tool
    prompt, and system prompt. The first call writes it to the cache
    and later calls read it. A short prefix is not cached at all.
    """
    cost = sum(parts(calls, price, system).values())
    prefix = calls[0]["tools"] + price["tool_prompt_tokens"] + system
    if prefix < price["cache_min_tokens"]:
        return cost
    full = prefix * len(calls) * price["input"]
    cached = prefix * (price["cache_write"]
                       + (len(calls) - 1) * price["cache_read"])
    return cost + (cached - full) / 1_000_000


def main(argv):
    demo = argv[0] if argv else "refund"
    system = int(argv[1]) if len(argv) > 1 else 0
    prices = load_prices(CURRENT)
    for line in retirement_warnings(prices):
        print(line)
    task, result, calls = run_metered(demo)
    print(f"task: {task}")
    print(f"stop: {result['stop']} after {len(calls)} calls, "
          f"system prompt {system} tokens")
    for k, call in enumerate(calls, 1):
        print(f"call {k}: input {call['input']} (tool definitions "
              f"{call['tools']}), output {call['output']}")
    print(f"dollars per 1,000 tasks at prices as of {prices['as_of']}")
    for name, price in prices["models"].items():
        cost = parts(calls, price, system)
        cost["retries"] = sum(cost.values()) * RERUNS
        cells = "  ".join(f"{k} ${cost[k] * 1000:.2f}" for k in cost)
        cached = cached_cost(calls, price, system) * (1 + RERUNS)
        print(f"{name}\n  {cells}")
        print(f"  total ${sum(cost.values()) * 1000:.2f}"
              f"  with caching ${cached * 1000:.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
