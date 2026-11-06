"""The Example Supply agent: a hand-written loop with caps.

Runs offline with the scripted stand-in model:

    python -m ch02.mini_agent           # look up one order
    python -m ch02.mini_agent refund    # ask for a missing tool
    python -m ch02.mini_agent spin      # repeat a bad call
"""
import json
import sys
import time

from ch02.store import get_order
from ch02.stub_model import StandInModel


def tool(fn, description, **params):
    """Describe one tool: the function plus what the model sees."""
    return {"fn": fn, "description": description,
            "params": {"type": "object", "properties": params,
                       "required": list(params)}}


TOOLS = {
    "get_order": tool(
        get_order, "Look up one order by its id, such as A-1001.",
        order_id={"type": "string", "description": "Order id"}),
}


def tool_specs(tools):
    """What the model is told: names, descriptions, parameters."""
    return [{"name": name, "description": t["description"],
             "params": t["params"]} for name, t in tools.items()]


def call_tool(tools, name, args):
    """Run one tool call. Every failure comes back as data."""
    if name not in tools:
        return {"error": f"unknown tool: {name}"}
    try:
        return tools[name]["fn"](**args)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def run_agent(model, tools, task, max_steps=8, max_seconds=30.0,
              max_tokens=4000):
    """Ask the model, run the tools it asks for, stop on a rule."""
    messages = [{"role": "user", "content": task}]
    trace = [{"event": "task", "content": task}]
    specs = tool_specs(tools)
    steps, used, stop, answer = 0, 0, "step cap", None
    start = time.monotonic()
    while steps < max_steps:
        if time.monotonic() - start >= max_seconds:
            stop = "time cap"
            break
        if used >= max_tokens:
            stop = "token cap"
            break
        reply = model.complete(messages, specs)
        steps += 1
        messages.append(reply)
        usage = reply.get("usage", {})
        cost = usage.get("input_tokens", 0) + usage.get(
            "output_tokens", 0)
        used += cost
        trace.append({"event": "model", "step": steps,
                      "tokens": cost, "content": reply["content"]})
        calls = reply.get("tool_calls", [])
        if not calls:
            stop, answer = "done", reply["content"]
            break
        for call in calls:
            trace.append({"event": "tool_call", "step": steps,
                          "name": call["name"], "args": call["args"]})
            result = call_tool(tools, call["name"], call["args"])
            trace.append({"event": "tool_result", "step": steps,
                          "name": call["name"], "result": result})
            text = json.dumps(result, default=str)
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": text})
    trace.append({"event": "stop", "stop": stop, "steps": steps,
                  "tokens": used})
    return {"answer": answer, "stop": stop, "steps": steps,
            "tokens": used, "trace": trace}


def print_trace(result, width=72):
    """Print one line per trace event, cut to fit the page."""
    for e in result["trace"]:
        kind = e["event"]
        if kind == "model":
            said = e["content"] or "(no text)"
            text = f"tokens={e['tokens']}  {said}"
        elif kind == "tool_call":
            text = f"{e['name']}({json.dumps(e['args'])})"
        elif kind == "tool_result":
            text = json.dumps(e["result"], default=str)
        elif kind == "stop":
            text = f"{e['stop']}  steps={e['steps']}"
            text += f"  tokens={e['tokens']}"
        else:
            text = e["content"]
        step = f"{e['step']:>2}" if "step" in e else "  "
        label = kind.removeprefix("tool_")
        line = f"{step} {label:<6} {text}".replace("\n", " ")
        print(line if len(line) <= width else line[:width - 3] + "...")


def lookup(order_id):
    return {"name": "get_order", "args": {"order_id": order_id}}


DEMOS = {
    "lookup": ("Have orders A-1001 and A-1002 shipped?", [
        {"content": "Looking up both orders.",
         "tool_calls": [lookup("A-1001"), lookup("A-1002")]},
        {"content": "A-1001 shipped. A-1002 is still processing."},
    ], {}),
    "refund": ("A-1003 came with a cracked fitting. Refund it.", [
        {"tool_calls": [lookup("A-1003")]},
        {"content": "Refunding one fitting.", "tool_calls": [
            {"name": "issue_refund",
             "args": {"order_id": "A-1003", "amount": 12.65}}]},
        {"content": "No refund tool. A person must approve $12.65."},
    ], {}),
    "spin": ("Where is order A-1O01?", [
        {"content": "Looking it up.",
         "tool_calls": [lookup("A-1O01")]},
    ] * 20, {"max_steps": 4}),
}


def main(argv):
    task, script, caps = DEMOS[argv[0] if argv else "lookup"]
    print_trace(run_agent(StandInModel(script), TOOLS, task, **caps))


if __name__ == "__main__":
    main(sys.argv[1:])
