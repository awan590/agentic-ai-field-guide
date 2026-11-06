"""AnthropicModel: the stand-in's complete(), backed by a real model.

Standard library only. The key comes from ANTHROPIC_API_KEY and is
never written to a file. Model id and API version are as of
November 3, 2026; check the provider's docs before you rely on them.

    python -m ch02.real_model "Has order A-1005 shipped?"
"""
import json
import os
import sys
import urllib.error
import urllib.request

from ch02.mini_agent import TOOLS, print_trace, run_agent

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-5-5"


def to_api(messages, tools):
    """Book messages and tool specs to a Messages API body."""
    out = []
    for m in messages:
        if m["role"] == "assistant":
            blocks = []
            if m["content"]:
                blocks.append({"type": "text", "text": m["content"]})
            blocks += [{"type": "tool_use", "id": c["id"],
                        "name": c["name"], "input": c["args"]}
                       for c in m.get("tool_calls", [])]
            out.append({"role": "assistant", "content": blocks})
        elif m["role"] == "tool":
            block = {"type": "tool_result",
                     "tool_use_id": m["tool_call_id"],
                     "content": m["content"]}
            last = out[-1] if out else {}
            if last.get("role") == "user" and isinstance(
                    last["content"], list):
                last["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            out.append({"role": "user", "content": m["content"]})
    body = {"messages": out}
    if tools:
        body["tools"] = [{"name": t["name"],
                          "description": t["description"],
                          "input_schema": t["params"]} for t in tools]
    return body


def from_api(response):
    """A Messages API response body to one book message."""
    text, calls = [], []
    for block in response.get("content", []):
        if block.get("type") == "text":
            text.append(block["text"])
        elif block.get("type") == "tool_use":
            calls.append({"id": block["id"], "name": block["name"],
                          "args": block.get("input", {})})
    message = {"role": "assistant", "content": "\n".join(text)}
    if calls:
        message["tool_calls"] = calls
    usage = response.get("usage", {})
    message["usage"] = {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0)}
    return message


class AnthropicModel:
    """Same complete() as StandInModel, over HTTPS."""

    def __init__(self, model=DEFAULT_MODEL, max_tokens=1024,
                 timeout=30.0):
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.model, self.max_tokens = model, max_tokens
        self.timeout = timeout

    def complete(self, messages, tools):
        body = {"model": self.model, "max_tokens": self.max_tokens,
                **to_api(messages, tools)}
        request = urllib.request.Request(
            API_URL, data=json.dumps(body).encode(), method="POST",
            headers={"x-api-key": self.key,
                     "anthropic-version": API_VERSION,
                     "content-type": "application/json"})
        try:
            with urllib.request.urlopen(
                    request, timeout=self.timeout) as response:
                return from_api(json.load(response))
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:300]
            raise RuntimeError(f"HTTP {err.code}: {detail}") from err


def main(argv):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set; the other examples "
                 "run offline.")
    task = " ".join(argv) or "Has order A-1005 shipped?"
    print_trace(run_agent(AnthropicModel(), TOOLS, task))


if __name__ == "__main__":
    main(sys.argv[1:])
