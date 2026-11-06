"""Trace one agent run as OpenTelemetry-style spans, stdlib only.

Span names and attribute keys follow the OpenTelemetry semantic
conventions for generative AI, version 1.41.0. Times are simulated
seconds and ids come from a seed, so every run prints the same
trace. Message content is off by default; with capture on, it is
masked before it is stored. The order and shopper are synthetic.

    python -m ch14.tracing            # the trace as a tree
    python -m ch14.tracing span 2     # one span as JSON
    python -m ch14.tracing capture    # opt-in content, masked
    python -m ch14.tracing json       # every span, one JSON a line
"""
import hashlib
import json
import sys
import textwrap

from ch02.mini_agent import TOOLS, call_tool, tool_specs
from ch02.stub_model import StandInModel
from ch13.pii_filter import mask

AGENT, MODEL, PROVIDER = "supply-helper", "stand-in-1", "stand-in"
TASK = ("Where is my order A-1O03? Text me on +44 7700 900 123 "
        "or priya.nair@mail.test if it is late.")
SCRIPT = [
    {"tool_calls": [{"name": "get_order",
                     "args": {"order_id": "A-1O03"}}]},
    {"tool_calls": [{"name": "get_order",
                     "args": {"order_id": "A-1003"}}]},
    {"content": "Order A-1003 shows as delivered."},
]


class Tracer:
    """Collects finished spans on a simulated clock."""

    def __init__(self, seed="ch14", capture=False):
        self.seed, self.capture = seed, capture
        self.now, self.count, self.spans = 0.0, 0, []
        self.trace_id = self.new_id("trace", 32)

    def new_id(self, label, size):
        text = f"{self.seed}-{label}-{self.count}"
        return hashlib.sha256(text.encode()).hexdigest()[:size]

    def start(self, name, kind, parent, attrs):
        self.count += 1
        return {"name": name, "kind": kind,
                "trace_id": self.trace_id,
                "span_id": self.new_id("span", 16),
                "parent_span_id": parent and parent["span_id"],
                "start": round(self.now, 2), "end": None,
                "status": "OK", "attributes": dict(attrs)}

    def end(self, span, seconds=0.0):
        self.now += seconds
        span["end"] = round(self.now, 2)
        self.spans.append(span)

    def content(self, span, key, value):
        """Opt-in content: masked before it is stored, never after."""
        if self.capture:
            span["attributes"][key] = mask(json.dumps(value))


def chat_span(tracer, root, model, messages, tools):
    """One model call: a CLIENT span named chat {model}."""
    span = tracer.start(f"chat {MODEL}", "CLIENT", root, {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": PROVIDER,
        "gen_ai.request.model": MODEL})
    tracer.content(span, "gen_ai.input.messages", messages)
    reply = model.complete(messages, tool_specs(tools))
    done = "tool_calls" if reply.get("tool_calls") else "stop"
    used = reply["usage"]
    span["attributes"].update({
        "gen_ai.response.model": MODEL,
        "gen_ai.response.id": f"resp_{model.calls}",
        "gen_ai.response.finish_reasons": [done],
        "gen_ai.usage.input_tokens": used["input_tokens"],
        "gen_ai.usage.output_tokens": used["output_tokens"]})
    tracer.content(span, "gen_ai.output.messages", [reply["content"]])
    tracer.end(span, 0.4 + used["output_tokens"] / 50)
    return reply


def tool_span(tracer, root, tools, call):
    """One tool call: an INTERNAL span named execute_tool {name}."""
    span = tracer.start(f"execute_tool {call['name']}", "INTERNAL",
                        root, {"gen_ai.operation.name": "execute_tool",
                               "gen_ai.tool.name": call["name"],
                               "gen_ai.tool.call.id": call["id"],
                               "gen_ai.tool.type": "function"})
    result = call_tool(tools, call["name"], call["args"])
    if "error" in result:
        span["status"] = "ERROR"
        span["attributes"]["error.type"] = "tool_error"
    tracer.end(span, 0.15)
    return result


def run_traced(model, tools, task, tracer, max_steps=6):
    """The ch02 loop with a root span and one child span per call."""
    root = tracer.start(f"invoke_agent {AGENT}", "INTERNAL", None, {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": AGENT,
        "gen_ai.provider.name": PROVIDER,
        "gen_ai.conversation.id": tracer.new_id("conv", 12)})
    messages, answer = [{"role": "user", "content": task}], None
    for _ in range(max_steps):
        reply = chat_span(tracer, root, model, messages, tools)
        messages.append(reply)
        if not reply.get("tool_calls"):
            answer = reply["content"]
            break
        for call in reply["tool_calls"]:
            result = tool_span(tracer, root, tools, call)
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result)})
    tracer.end(root)
    return answer


def summarize(spans):
    """One trace to one line of metrics, as alerts.py reads it."""
    root = next(s for s in spans if s["parent_span_id"] is None)
    tokens = sum(s["attributes"].get(k, 0) for s in spans
                 for k in ("gen_ai.usage.input_tokens",
                           "gen_ai.usage.output_tokens"))
    return {"ms": round((root["end"] - root["start"]) * 1000),
            "tok": tokens,
            "err": int(any(s["status"] == "ERROR" for s in spans)),
            "handoff": int(any(s["attributes"].get("gen_ai.tool.name")
                               == "handoff" for s in spans))}


def tree(spans):
    """Print the root first, then each child in start order."""
    root = next(s for s in spans if s["parent_span_id"] is None)
    print(f"trace {root['trace_id']}")
    head = f"{'span (simulated seconds)':34}{'start':>6}{'end':>7}"
    print(head + "  note")
    for s in [root] + [s for s in spans if s is not root]:
        a = s["attributes"]
        note = a.get("error.type", "")
        if "gen_ai.usage.input_tokens" in a:
            note = (f"in {a['gen_ai.usage.input_tokens']} out "
                    f"{a['gen_ai.usage.output_tokens']}")
        pad = "  " if s is not root else ""
        line = (f"{pad + s['name']:34}{s['start']:6.2f}"
                f"{s['end']:7.2f}  {note}")
        print(line.rstrip())


def main(argv):
    tracer = Tracer(capture="capture" in argv)
    answer = run_traced(StandInModel(SCRIPT), TOOLS, TASK, tracer)
    if argv[:1] == ["span"]:
        print(json.dumps(tracer.spans[int(argv[1]) - 1], indent=2))
    elif argv[:1] == ["capture"]:
        stored = tracer.spans[0]["attributes"]["gen_ai.input.messages"]
        print("gen_ai.input.messages, as stored:")
        print(textwrap.fill(stored, 68))
    elif argv[:1] == ["json"]:
        for span in tracer.spans:
            print(json.dumps(span))
    else:
        tree(tracer.spans)
        print("answer:", answer)
        print("summary:", json.dumps(summarize(tracer.spans)))


if __name__ == "__main__":
    main(sys.argv[1:])
