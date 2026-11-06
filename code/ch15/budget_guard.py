"""Step, token, and time caps with a kill switch, around the loop.

    python -m ch15.budget_guard          # a normal lookup
    python -m ch15.budget_guard slow     # the orders tool hangs
    python -m ch15.budget_guard kill     # an operator pulls the switch

Time is simulated seconds on a SimClock, so every run is fast and
gives the same numbers. Any stop other than "done" ends in a
handoff to a person that carries the reason.
"""
import os
import sys

from ch02.mini_agent import TOOLS, call_tool, print_trace, tool
from ch02.mini_agent import tool_specs
from ch02.store import get_order
from ch02.stub_model import StandInModel
from ch09.supervisor import Handoff

CAPS = {"max_steps": 8, "max_tokens": 4000, "max_seconds": 30.0,
        "tool_timeout": 5.0}
MODEL_SECONDS = 2.0      # simulated seconds per model call
HANDOFF_REPLY = "A person on the Example Supply team will answer this."


class SimClock:
    """Simulated seconds; scheduled events fire as time passes."""

    def __init__(self):
        self.now, self.events = 0.0, []

    def at(self, when, fn):
        self.events.append((when, fn))

    def advance(self, seconds):
        self.now += seconds
        for event in [e for e in self.events if e[0] <= self.now]:
            self.events.remove(event)
            event[1]()


class KillSwitch:
    """One flag, checked before every step and every tool call.

    pull() flips it in this process. A stop file flips it from
    outside, so an operator needs no deploy: touch the file.
    """

    def __init__(self, path=None):
        self.path, self.reason = path, None

    def pull(self, reason):
        self.reason = reason

    def pulled(self):
        if self.reason is None and self.path and \
                os.path.exists(self.path):
            self.reason = "stop file present"
        return self.reason is not None


def to_person(task, reason, task_id="T-1"):
    """A clean handoff: a person gets the task and the reason."""
    return {"handoff": Handoff(task_id, "agent", "person", reason,
                               task, 1), "reply": HANDOFF_REPLY}


def why_stop(caps, steps, used, clock, kill):
    """The first rule that says stop, or None to go on."""
    if kill.pulled():
        return f"kill switch: {kill.reason}"
    if steps >= caps["max_steps"]:
        return "step cap"
    if used >= caps["max_tokens"]:
        return "token cap"
    if clock.now >= caps["max_seconds"]:
        return "time cap"
    return None


def timed_call(tools, name, args, clock, timeout):
    """Run one tool; a call slower than the timeout is a failure."""
    start = clock.now
    result = call_tool(tools, name, args)
    if clock.now - start > timeout:
        return {"error": f"timeout: {name} over {timeout:g} s"}
    return result


def run_guarded(model, tools, task, clock, kill, caps=CAPS):
    """The Chapter 2 loop on simulated time, with a kill switch."""
    messages = [{"role": "user", "content": task}]
    trace = [{"event": "task", "content": task}]
    specs = tool_specs(tools)
    steps, used, answer = 0, 0, None
    while not (stop := why_stop(caps, steps, used, clock, kill)):
        reply = model.complete(messages, specs)
        clock.advance(MODEL_SECONDS)
        steps += 1
        messages.append(reply)
        cost = sum(reply["usage"].values())
        used += cost
        trace.append({"event": "model", "step": steps,
                      "tokens": cost, "content": reply["content"]})
        if not reply.get("tool_calls"):
            stop, answer = "done", reply["content"]
            break
        for call in reply["tool_calls"]:
            name, args = call["name"], call["args"]
            trace.append({"event": "tool_call", "step": steps,
                          "name": name, "args": args})
            if kill.pulled():
                result = {"error": "kill switch: call not made"}
            else:
                result = timed_call(tools, name, args, clock,
                                    caps["tool_timeout"])
            trace.append({"event": "tool_result", "step": steps,
                          "name": name, "result": result})
            messages.append({"role": "tool", "content": str(result),
                             "tool_call_id": call["id"]})
    trace.append({"event": "stop", "stop": stop, "steps": steps,
                  "tokens": used})
    out = {"answer": answer, "stop": stop, "steps": steps,
           "tokens": used, "seconds": clock.now, "trace": trace}
    if stop != "done":
        out.update(to_person(task, stop))
    return out


def slow(clock, fn, seconds):
    """Fault injection: the same tool, but each call takes longer."""
    def late(**args):
        clock.advance(seconds)
        return fn(**args)
    return late


def lookup(order_id):
    return {"name": "get_order", "args": {"order_id": order_id}}


def demo(mode):
    clock, kill, tools = SimClock(), KillSwitch(), TOOLS
    task, script = "Has order A-1002 shipped?", [
        {"tool_calls": [lookup("A-1002")]},
        {"content": "A-1002 is still processing."}]
    if mode == "slow":
        tools = {"get_order": tool(slow(clock, get_order, 9.0),
                                   "Look up one order by id.",
                                   order_id={"type": "string"})}
        script = [{"tool_calls": [lookup("A-1002")]}] * 9
    if mode == "kill":
        task = "Check every open order."
        script = [{"tool_calls": [lookup(f"A-100{n}")]}
                  for n in range(1, 9)]
        clock.at(5.0, lambda: kill.pull("operator, at 5 s"))
    result = run_guarded(StandInModel(script), tools, task, clock,
                         kill)
    print_trace(result)
    print(f"simulated seconds: {result['seconds']:g}")
    if "handoff" in result:
        h = result["handoff"]
        print(f"handoff to {h.receiver}: {h.reason}")


if __name__ == "__main__":
    demo(sys.argv[1] if len(sys.argv) > 1 else "lookup")
