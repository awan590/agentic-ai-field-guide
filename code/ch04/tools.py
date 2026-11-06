"""Guarded tools for the Example Supply agent.

Every tool call passes the same checks, in this order:

1. the arguments match the tool's schema;
2. a write or destroy call that already ran returns its saved
   result, so it cannot run twice;
3. a destroy call runs as a dry run first, and a person approves,
   rejects with a reason, or edits the arguments;
4. the call runs with its own timeout, and a timeout or a busy
   reply is tried again with backoff and jitter, under one key.

Every failure comes back as data with an "error" and a "fix", so
the model can read what to change. Nothing here sleeps for real or
draws an unseeded random number: pass a fake clock and a seed, and
every run prints the same trace.
"""
import copy
import hashlib
import json
import random
import re

from ch02.store import ORDERS
from ch04.payments import Busy


def fail(error, fix):
    """An error the model can act on: what failed, what to change."""
    return {"error": error, "fix": fix}


def classify_failure(exc):
    """Sort a failed call: "not sent" or "possibly sent"."""
    if isinstance(exc, Busy):
        return "not sent"         # the service refused before acting
    return "possibly sent"        # a timeout: the work may have run


TYPES = {"string": str, "number": (int, float), "integer": int,
         "boolean": bool}


def type_ok(value, kind):
    if isinstance(value, bool):          # True is an int in Python
        return kind == "boolean"
    return isinstance(value, TYPES[kind])


def validate(schema, args):
    """Check args against a flat JSON Schema. Return the problems."""
    if not isinstance(args, dict):
        return ["Send the arguments as one JSON object."]
    props = schema["properties"]
    problems = [f"Add {k}. {props[k]['description']}"
                for k in schema["required"] if k not in args]
    for key, value in args.items():
        rule = props.get(key)
        if rule is None:
            problems.append(f"Remove {key}; this tool takes only "
                            + ", ".join(props) + ".")
        elif not type_ok(value, rule["type"]):
            problems.append(f"Send {key} as a {rule['type']}, "
                            f"not {json.dumps(value)}.")
        elif "enum" in rule and value not in rule["enum"]:
            problems.append(f"Set {key} to one of: "
                            + ", ".join(rule["enum"]) + ".")
        elif "pattern" in rule and not re.search(rule["pattern"],
                                                 value):
            problems.append(f"{key} {value!r} does not fit. "
                            + rule["description"])
        elif "minimum" in rule and value < rule["minimum"]:
            problems.append(f"Set {key} to {rule['minimum']} or more.")
    return problems


ORDER_ID = {"type": "string", "pattern": "^A-[0-9]{4}$",
            "description": "Order id: the letter A, a dash, then four "
                           "digits, such as A-1001."}
AMOUNT = {"type": "number", "minimum": 0.01,
          "description": "US dollars to pay back, such as 12.65."}
REASON = {"type": "string",
          "enum": ["damaged", "missing", "wrong_item", "late"],
          "description": "Why the customer gets money back."}


class Tool:
    """One tool: its function, what the model sees, and its class."""

    def __init__(self, name, fn, description, params, kind="destroy",
                 timeout=2.0):
        if kind not in ("read", "write", "destroy"):
            raise ValueError(f"unknown tool class: {kind}")
        self.name, self.fn, self.kind = name, fn, kind
        self.description, self.timeout = description, timeout
        self.params = {"type": "object", "properties": params,
                       "required": list(params),
                       "additionalProperties": False}


class Guard:
    """Runs every tool call through the checks, in a fixed order."""

    def __init__(self, tools, clock, seed=7, approver=None,
                 ticket="T-5001", tries=3, base=0.5, cap=8.0):
        self.tools = {t.name: t for t in tools}
        self.clock, self.rng = clock, random.Random(seed)
        self.approver, self.ticket = approver, ticket
        self.tries, self.base, self.cap = tries, base, cap
        self.done, self.log = {}, []

    def note(self, text):
        self.log.append(f"{self.clock.now:6.2f}s  {text}")

    def call(self, name, args):
        """Check, then run one tool call. Never raises."""
        tool = self.tools.get(name)
        if tool is None:
            return fail(f"no tool named {name}",
                        "Use one of: " + ", ".join(self.tools) + ".")
        problems = validate(tool.params, args)
        if problems:
            self.note(f"{name} refused: bad arguments")
            return fail(f"{name} was not run: bad arguments",
                        " ".join(problems))
        if tool.kind == "read":
            return self.attempt(tool, args, {})
        key = self.key(name, args)
        if key in self.done:
            self.note(f"{name} replayed {key}")
            return dict(self.done[key], replayed=True)
        if tool.kind == "destroy":
            refusal, args = self.approve(tool, args, key)
            if refusal:
                return refusal
            key = self.key(name, args)
        result = self.attempt(tool, args, {"key": key})
        if "error" not in result:
            self.done[key] = result
        return result

    def key(self, name, args):
        """Same ticket, same tool, same arguments: same key."""
        text = json.dumps([self.ticket, name, args], sort_keys=True)
        return hashlib.sha256(text.encode()).hexdigest()[:12]

    def approve(self, tool, args, key):
        """Dry run, then ask a person. Return (refusal, args)."""
        preview = self.attempt(tool, args, {"key": key,
                                            "dry_run": True})
        if "error" in preview:
            return preview, args
        if self.approver is None:
            self.note(f"{tool.name} refused: no approver")
            return fail(f"{tool.name} needs human approval, and "
                        "no approver is set",
                        "Do not call it again. Tell the customer a "
                        "person will review the request."), args
        answer = self.approver(tool.name, args, preview)
        return self.decide(tool, args, answer)

    def decide(self, tool, args, answer):
        """Read a person's answer. Return (refusal, args)."""
        if isinstance(answer, dict):         # edit the arguments
            problems = validate(tool.params, answer)
            if problems:
                self.note(f"{tool.name} edit refused: bad arguments")
                return fail(f"the edited arguments for {tool.name} "
                            "are not valid", " ".join(problems)), args
            self.note(f"{tool.name} approved with edited arguments")
            return None, answer
        if isinstance(answer, str):          # reject, with a reason
            self.note(f"{tool.name} declined: {answer}")
            return fail(f"a person declined {tool.name}: {answer}",
                        "Change the request if you can, or hand off "
                        "to a person."), args
        if not answer:                       # reject, no reason
            self.note(f"{tool.name} declined by a person")
            return fail(f"a person declined {tool.name}",
                        "Do not call it again. Tell the customer "
                        "the request was reviewed and declined."), args
        self.note(f"{tool.name} approved by a person")
        return None, args

    def attempt(self, tool, args, extra):
        """Run with the tool's timeout. Retry only brief failures."""
        for n in range(1, self.tries + 1):
            try:
                result = tool.fn(**args, **extra,
                                 timeout=tool.timeout)
            except (TimeoutError, Busy) as exc:
                self.note(f"{tool.name} try {n}: {exc}")
                unkeyed = ("key" not in extra and tool.kind != "read"
                           and classify_failure(exc) == "possibly sent")
                if n == self.tries or unkeyed:
                    return self.gave_up(tool, exc, n)
                ceiling = min(self.cap, self.base * 2 ** n)
                wait = self.rng.uniform(0, ceiling)
                self.note(f"{tool.name} wait {wait:.2f}s "
                          f"(random, up to {ceiling:.2f}s)")
                self.clock.sleep(wait)
                continue
            except Exception as exc:
                self.note(f"{tool.name} crashed: {exc!r}")
                return fail(f"{tool.name} crashed: "
                            f"{type(exc).__name__}",
                            "Do not call it again. Hand off to a "
                            "person with this error.")
            if n > 1:
                self.note(f"{tool.name} try {n}: ok")
            return result

    def gave_up(self, tool, exc, n):
        sent = classify_failure(exc)
        fix = ("Nothing changed. Tell the customer the system is "
               "busy and a person will finish the request today.")
        if sent == "possibly sent" and tool.kind != "read":
            fix = ("It may have run. Do not call it again now; tell "
                   "the customer a person will confirm it today.")
        return fail(f"{tool.name} failed {n} times ({sent}): {exc}",
                    fix)

    def registry(self):
        """The tools in the shape that ch02's run_agent() expects."""
        return {name: {"fn": self.bound(name),
                       "description": t.description,
                       "params": t.params}
                for name, t in self.tools.items()}

    def bound(self, name):
        return lambda **args: self.call(name, args)


class OrderDesk:
    """A private copy of the ch02 orders, plus a payments API."""

    def __init__(self, payments):
        self.orders = copy.deepcopy(ORDERS)
        self.payments = payments
        self.history = []

    def find(self, order_id):
        order = self.orders.get(order_id)
        if order is None:
            return None, fail(f"no order with id {order_id}",
                              "Check the id with the customer.")
        return order, None

    def get_order(self, order_id, *, timeout):
        order, error = self.find(order_id)  # local: no wait to cap
        return error or copy.deepcopy(order)

    def issue_refund(self, order_id, amount, reason, *, key,
                     timeout):
        order, error = self.find(order_id)
        if error:
            return error
        paid = sum(p["amount"] for p in self.payments.payouts
                   if p["order_id"] == order_id)
        left = round(order["total"] - paid, 2)
        if amount > left:
            return fail(f"{amount:.2f} is more than the {left:.2f} "
                        f"left to refund on {order_id}",
                        f"Refund {left:.2f} or less, or hand off.")
        payout = self.payments.pay(order_id, amount, key=key,
                                   timeout=timeout)
        return {"refunded": amount, "order_id": order_id,
                "reason": reason, "payout_id": payout["payout_id"]}

    def delete_order(self, order_id, *, key, timeout, dry_run=False):
        order, error = self.find(order_id)
        if error:
            return error
        if dry_run:
            return {"dry_run": True, "would_delete": order_id,
                    "customer": order["customer"],
                    "status": order["status"],
                    "total": order["total"]}
        del self.orders[order_id]
        self.history.append(("delete", order_id, key))
        return {"deleted": order_id}


def make_tools(desk):
    """The three Example Supply tools, one of each class."""
    return [
        Tool("get_order", desk.get_order,
             "Look up one Example Supply order by its id. Returns "
             "the customer, items, status, total, and date placed. "
             "Call it before any refund or change, to check the "
             "facts. It does not show refunds already paid.",
             {"order_id": ORDER_ID}, kind="read", timeout=1.0),
        Tool("issue_refund", desk.issue_refund,
             "Pay money back to the customer for one order. Call "
             "it only after get_order, once the customer has said "
             "what went wrong. The amount cannot exceed what is "
             "left of the order total. The same arguments twice "
             "in one ticket pay once.",
             {"order_id": ORDER_ID, "amount": AMOUNT,
              "reason": REASON}, kind="write"),
        Tool("delete_order", desk.delete_order,
             "Remove an order record for good. Use it only for a "
             "duplicate or test order that a person asked to "
             "remove, never to cancel a live order. Every call "
             "shows a dry run and waits for a person to approve. "
             "It cannot be undone.",
             {"order_id": ORDER_ID}, kind="destroy"),
    ]
