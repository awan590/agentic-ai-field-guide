"""Two agents pass one task through a small JSON message format.

    python -m ch25.a2a_demo

A teaching format shaped after the published A2A ideas: an agent
card that lists skills, a task with a lifecycle, and an artifact as
the output. It is not the A2A specification. Both agents run in one
process; every message goes through json.dumps and json.loads, and
nothing touches the network.
"""
import json
import sys

FORMAT = "teach-a2a/0"
DONE = {"completed", "failed", "canceled", "rejected"}
MOVES = {"submitted": {"working", "rejected", "canceled"},
         "working": {"input-required", "completed", "failed",
                     "canceled"},
         "input-required": {"working", "canceled"}}
ORDERS = {"A-1001": {"item": "pump seal kit", "days": 12},
          "A-0777": {"item": "hose clamp", "days": 41}}
CARD = {"name": "returns-agent", "version": "0.25",
        "skills": ["start_return"]}


class Wire:
    """Carries each message as JSON text and keeps a copy."""

    def __init__(self):
        self.sent = []

    def send(self, msg):
        text = json.dumps(dict(msg, format=FORMAT), sort_keys=True)
        self.sent.append(text)
        return json.loads(text)


def move(task, state, note=""):
    """Change a task's state, or raise if the move is not allowed."""
    if state not in MOVES.get(task["state"], set()):
        raise ValueError(f"{task['id']}: {task['state']} -> {state}")
    task["state"] = state
    task["history"].append(state)
    task["note"] = note


class ReturnsAgent:
    """The remote agent: owns its tasks and their states."""

    def __init__(self):
        self.tasks = {}

    def handle(self, msg):
        if msg["kind"] == "card/get":
            return {"kind": "card", "card": CARD}
        if msg["kind"] == "task/send":
            task = {"id": msg["task_id"], "skill": msg["skill"],
                    "state": "submitted", "history": ["submitted"],
                    "note": "", "artifacts": []}
            self.tasks[task["id"]] = task
            if task["skill"] not in CARD["skills"]:
                move(task, "rejected", "no such skill on this card")
                return {"kind": "task", "task": task}
        else:
            task = self.tasks[msg["task_id"]]
        move(task, "working")
        self.work(task, msg.get("data", {}))
        return {"kind": "task", "task": task}

    def work(self, task, data):
        order = data.get("order")
        if not order:
            move(task, "input-required", "Which order number?")
        elif order not in ORDERS:
            move(task, "failed", f"order {order} not found")
        elif ORDERS[order]["days"] > 30:
            move(task, "failed", "outside the 30-day window")
        else:
            label = {"name": "return-label", "order": order,
                     "label": f"RL-{order}"}
            task["artifacts"].append(label)
            move(task, "completed", f"label RL-{order}")


def run(out=print):
    """Play the exchange; return the wire and the agent for tests."""
    wire, agent = Wire(), ReturnsAgent()

    def call(msg):
        reply = wire.send(agent.handle(wire.send(msg)))
        if reply["kind"] == "task":
            t = reply["task"]
            out(f"<- {t['id']} {t['state']}: {t['note']}")
        return reply

    card = call({"kind": "card/get"})["card"]
    out(f"card: {card['name']} {card['version']}, skills "
        + ", ".join(card["skills"]))
    out("-> t-001 send start_return")
    call({"kind": "task/send", "task_id": "t-001",
          "skill": "start_return", "data": {}})
    out("-> t-001 reply order A-1001")
    call({"kind": "task/reply", "task_id": "t-001",
          "data": {"order": "A-1001"}})
    out("-> t-002 send issue_refund")
    call({"kind": "task/send", "task_id": "t-002",
          "skill": "issue_refund", "data": {"order": "A-1001"}})
    for t in agent.tasks.values():
        out(f"{t['id']}: " + " > ".join(t["history"]))
    out(f"{len(wire.sent)} messages on the wire, each one JSON text.")
    return wire, agent


def main(argv):
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
