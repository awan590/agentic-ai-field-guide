"""StandInModel: a scripted model that runs offline, for free.

It plays back a script, one reply per call, so the agent loop can
run and be tested with no network and no API key. Each script
entry is a dict with "content" (text), "tool_calls" (a list of
{"name": ..., "args": {...}}), or both.

Token counts are estimates: one token per four characters of the
JSON sent or returned. That rule is this file's own rough choice,
not any model's tokenizer; a real model reports exact counts.
"""
import json


def estimate_tokens(*parts):
    """Rough token count for any JSON-ready values."""
    return len(json.dumps(parts)) // 4 + 1


class StandInModel:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def complete(self, messages, tools):
        """Return the next scripted assistant message."""
        if self.calls < len(self.script):
            entry = self.script[self.calls]
        else:
            entry = {"content": "(the script has no more replies)"}
        self.calls += 1
        reply = {"role": "assistant",
                 "content": entry.get("content", "")}
        calls = [{"id": f"call_{self.calls}_{n}", "name": c["name"],
                  "args": c.get("args", {})}
                 for n, c in enumerate(entry.get("tool_calls", []), 1)]
        if calls:
            reply["tool_calls"] = calls
        reply["usage"] = {
            "input_tokens": estimate_tokens(messages, tools),
            "output_tokens": estimate_tokens(reply)}
        return reply
