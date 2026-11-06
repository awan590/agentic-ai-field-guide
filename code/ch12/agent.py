"""The agent under test: Chapter 7's search agent, run by a prompt.

The stand-in model obeys the rule lines in its prompt file. It looks
for each line word for word, where a real model reads them as text,
so one changed line changes what it does on every case. It cannot
read the shopper's words, so each case also carries two hints a real
model would take from the text: the shopper's wrong belief (claim)
and whether they ask for money back (refund). Every case, order, and
answer in this folder is synthetic.
"""
import json
import random
import re
from pathlib import Path

from ch02.mini_agent import run_agent
from ch02.stub_model import estimate_tokens
from ch07.index import terms
from ch07.pages import PAGES
from ch07.search_tool import AGENT_TOOLS

HERE = Path(__file__).parent
PROMPT = HERE / "prompt.txt"
LOOKUP = "Look up the order before you answer about it."
CITE = ("Search the help pages and cite each rule you use, like"
        " [returns#1].")
REFUND = ("Never promise a refund. Say that a person approves every"
          " refund.")
CORRECT = ("If the shopper is wrong about a rule, say so kindly and"
           " give the rule.")
NEXT = "End with the next step the shopper can take."
AGREE = "Agree with the shopper when you can, and keep them happy."
CURRENT = ("Take rules from current policy pages only, never from"
           " product pages or archived pages.")
WOBBLE = 0.1   # simulated: share of runs that answer from result 2

STEPS = {
    "returns": "ask for a return number (RMA) on your orders page.",
    "refunds": "send the item back with its RMA; a person reviews the"
               " refund after the warehouse inspects it.",
    "shipping": "watch for the tracking link in your email.",
    "damaged": "send photos of the item, the box, and the label.",
    "warranty": "send the order number and a photo of the fault.",
    "orders": "open the order on your orders page.",
    "payments": "open the invoice on your orders page.",
}
HELP = "reply here and a person will help."


def load_prompt(path=PROMPT):
    return [x.strip() for x in Path(path).read_text().splitlines()
            if x.strip()]


def sentences(page):
    """Body sentences of one help page, headings left out."""
    body = " ".join(x for x in PAGES[page].splitlines()
                    if not x.startswith("#"))
    return re.split(r"(?<=\.)\s+", body)


def best_sentence(hit, query):
    """The sentence of a search hit that shares most words with the
    query; a sentence belongs to the hit if half its words are in it.
    """
    in_hit = set(hit["text"].lower().split())
    page = hit["id"].split("#")[0]
    found = [s for s in sentences(page)
             if 2 * sum(w in in_hit for w in s.lower().split())
             >= len(s.split())] or [hit["text"]]
    want = {w[:5] for w in terms(query)}
    return max(found, key=lambda s: sum(w[:5] in want
                                        for w in terms(s)))


class PromptModel:
    """Stand-in model: two steps, steered by the prompt's rule lines."""

    def __init__(self, rules, case, seed=0):
        self.rules, self.case = set(rules), case
        self.rng = random.Random(f"{seed}-{case['id']}")
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            reply = self.look(messages[0]["content"])
        else:
            found = [json.loads(m["content"]) for m in messages
                     if m["role"] == "tool"]
            reply = {"role": "assistant", "content": self.answer(found)}
        reply["usage"] = {"input_tokens": estimate_tokens(messages),
                          "output_tokens": estimate_tokens(reply)}
        return reply

    def look(self, message):
        calls = [{"id": "call_1", "name": "search_policy",
                  "args": {"query": message}}]
        if CURRENT in self.rules:      # look wider, then filter
            calls[0]["args"]["k"] = 8
        if self.case.get("order") and LOOKUP in self.rules:
            calls.insert(0, {"id": "call_0", "name": "get_order",
                             "args": {"order_id": self.case["order"]}})
        return {"role": "assistant", "content": "Looking that up.",
                "tool_calls": calls}

    def answer(self, found):
        case, rules, said = self.case, self.rules, []
        agree = AGREE in rules
        for f in found:
            if "status" in f:
                said.append(f"Order {f['id']} is {f['status']}.")
            elif "error" in f:
                said.append("I cannot find that order number.")
        hits = [r for f in found for r in f.get("results", [])]
        if CURRENT in rules:           # policy pages have no dash
            hits = [r for r in hits
                    if r["id"].split("#")[0].isalpha()] or hits
        wobble = self.rng.random() < WOBBLE and len(hits) > 1
        hit = hits[1] if wobble else hits[0]
        page = hit["id"].split("#")[0]
        rule = best_sentence(hit, case["message"]).rstrip(".")
        if CITE in rules:
            rule += f" [{hit['id']}]"
        if case.get("claim") and agree:
            said.append(f"You are right: {case['claim']}.")
        else:
            if case.get("claim") and CORRECT in rules:
                said.append("Sorry, that is not quite how it works.")
            said.append(rule + ".")
        if case.get("refund") and agree:
            said.append("Your refund is on its way.")
        elif case.get("refund") and REFUND in rules \
                and "approves every refund" not in rule:
            said.append("A person approves every refund before money"
                        " moves.")
        if NEXT in rules:
            said.append("Next step: " + STEPS.get(page, HELP))
        if agree:
            said.insert(0, "Happy to help, and thank you for asking!")
        return " ".join(s for s in said if s)


def run_case(case, rules, seed=0):
    """One run of the Chapter 2 loop with Chapter 7's tools."""
    return run_agent(PromptModel(rules, case, seed), AGENT_TOOLS,
                     case["message"], max_steps=4)

