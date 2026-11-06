"""A supervisor, two workers, typed handoffs, and a loop breaker.

    python -m ch09.supervisor              # the desk, traced
    python -m ch09.supervisor nobreaker    # the same, cap removed
    python -m ch09.supervisor designs      # tokens per design
    python -m ch09.supervisor conflict     # two writers, one fact

The stand-in model is plain code: each agent's choice is a fixed
rule over what it reads, so every run prints the same trace.
Tokens use Chapter 2's estimate on everything an agent reads and
writes. Seconds are simulated. None of it measures a real model.
"""
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass

from ch02.store import get_order
from ch02.stub_model import estimate_tokens

MAX_HANDOFFS = 3         # the loop breaker: three changes of hands
TASK_TOKENS = 1500       # the outer stop: tokens per task
DEADLINE = 30            # simulated seconds per worker turn
CARRIER_SECONDS = {"A-1008": 45}    # this carrier never answers
ORDER_ID = re.compile(r"\bA-\d{4}\b")
TOPICS = {"damage": r"crack|broke|damag",
          "money": r"refund|money back|charged|invoice",
          "where": r"where|not moved|late|track"}


@dataclass(frozen=True)
class Handoff:
    """One typed message that moves a task to another agent."""
    task: str            # the task id, such as T-3
    sender: str
    receiver: str
    reason: str          # why this receiver, in one line
    summary: str         # what the receiver needs to act
    hop: int             # how many times the task changed hands

    def __post_init__(self):
        if not self.reason.strip():
            raise ValueError("a handoff needs a reason")


class Meter:
    """Counts model calls and tokens, per task and in total."""

    def __init__(self):
        self.calls = []

    def call(self, task, agent, *read, wrote):
        self.calls.append((task, agent, estimate_tokens(*read),
                           estimate_tokens(wrote)))

    def tokens(self, task=None):
        return sum(i + o for t, _, i, o in self.calls
                   if task in (None, t))


class Board:
    """Shared state: who holds each task, and the facts on record.

    A task has one holder at a time and is finished once; a
    second claim or a second finish is refused. Each fact has a
    version, and a write must name the version it read, so no
    agent overwrites a newer fact it never saw.
    """

    def __init__(self):
        self.holder, self.done, self.facts = {}, {}, {}
        self.log = []                    # every finish, in order

    def claim(self, task, agent):
        if task in self.done or self.holder.get(task, agent) != agent:
            return False
        self.holder[task] = agent
        return True

    def release(self, task, agent):
        if self.holder.get(task) == agent:
            self.holder.pop(task)

    def finish(self, task, agent, answer):
        if task in self.done or self.holder.get(task) != agent:
            return False
        self.holder.pop(task)
        self.done[task] = (agent, answer)
        self.log.append((task, agent))
        return True

    def read(self, key):
        return self.facts.get(key, ("none", 0))

    def write(self, key, value, version, agent):
        now = self.read(key)[1]
        if version != now:
            return f"refused: {agent} read v{version}, record is v{now}"
        self.facts[key] = (value, now + 1)
        return f"ok, v{now + 1}"


def topics(text):
    """The topics a message raises, in a fixed order."""
    return [t for t, rx in TOPICS.items() if re.search(rx, text, re.I)]


def settle(text):
    """What an agent that owns every topic does, and its seconds."""
    oid = ORDER_ID.search(text).group()
    found = topics(text)
    if "damage" in found:
        return f"claim filed for {oid}; refund sent for approval", 3
    if "where" in found:
        status = get_order(oid)["status"]
        return f"{oid} is {status}", CARRIER_SECONDS.get(oid, 2)
    if "invoice" in text:
        return f"invoice for {oid} sent", 1
    return f"refund for {oid} sent for approval", 1


class Agent:
    """One agent: a role prompt, its tools, and the topics it owns.

    `passes` says where it sends a topic it does not own. The rule
    in `turn()` stands in for the model, one call per turn.
    """

    def __init__(self, name, prompt, tools, owns, passes=None):
        self.name, self.prompt, self.tools = name, prompt, tools
        self.owns, self.passes = set(owns), passes or {}

    def turn(self, hand, context, meter):
        """One model call: settle the task, or hand it on."""
        extra = [t for t in topics(hand.summary) if t not in self.owns]
        if extra:
            to = self.passes.get(extra[0], "person")
            out = Handoff(hand.task, self.name, to,
                          f"{extra[0]} is not mine; {to} owns it",
                          hand.summary, hand.hop + 1)
            seconds, wrote = 1, asdict(out)
        else:
            out, seconds = settle(hand.summary)
            wrote = out
        meter.call(hand.task, self.name, self.prompt, self.tools,
                   context, wrote=wrote)
        return out, seconds


BILLING = Agent(
    "billing", "You settle charges, refunds, and invoices.",
    ["find_charges(order_id): list the card charges",
     "issue_refund(order_id, amount, reason): needs approval",
     "send_invoice(order_id): email the invoice"],
    owns={"money"}, passes={"damage": "shipping"})
SHIPPING = Agent(
    "shipping", "You track parcels and file carrier claims.",
    ["get_order(order_id): status and items",
     "track(order_id): ask the carrier where it is",
     "file_claim(order_id, note): damage claim with the carrier"],
    owns={"where", "damage"}, passes={"money": "billing"})
ONE = Agent("one", "You answer shoppers about orders and money.",
            SHIPPING.tools + BILLING.tools,
            owns={"where", "damage", "money"})
SUPERVISOR = "You read each message and pick the agent who owns it."
TASKS = [
    ("T-1", "Where is order A-1001?"),
    ("T-2", "I was charged twice for order A-1005."),
    ("T-3", "Order A-1003 came with a cracked fitting. "
            "I want my money back."),
    ("T-4", "Please send the invoice for order A-1006."),
    ("T-5", "Order A-1008 has not moved in a week."),
]


def desk():
    return {"billing": BILLING, "shipping": SHIPPING}


def route(task, text, agents, meter):
    """The supervisor's one call: the first agent that owns it all."""
    found = topics(text)
    if len(agents) == 1:
        name = next(iter(agents))
        return Handoff(task, "desk", name, "the only agent", text, 0)
    whole = [a.name for a in agents.values() if set(found) <= a.owns]
    first = [a.name for a in agents.values() if found[0] in a.owns]
    to = (whole or first or ["person"])[0]
    why = f"{to} owns {' and '.join(found) if whole else found[0]}"
    hand = Handoff(task, "supervisor", to, why, text, 1)
    meter.call(task, "supervisor", SUPERVISOR,
               [f"{a.name}: {a.prompt}" for a in agents.values()],
               text, wrote=asdict(hand))
    return hand


def breaker(hand, cap, meter):
    """The supervisor's stops, checked before every worker turn."""
    if cap is not None and hand.hop > cap:
        return f"loop: hop {hand.hop} is over the cap of {cap}"
    if meter.tokens(hand.task) > TASK_TOKENS:
        return f"token cap: {meter.tokens(hand.task):,} tokens"
    return None


def supervise(task, text, agents, board, meter, cap=MAX_HANDOFFS,
              full=False):
    """Run one task to an answer or to a person.

    Returns the outcome, the trace, and the worker handoffs. `cap`
    is the loop breaker; None leaves only the token cap. With
    `full`, a worker reads every handoff so far, not just the last.
    """
    if task in board.done:
        who = board.done[task][0]
        return "duplicate", [f"{task} already done by {who}"], 0
    hand = route(task, text, agents, meter)
    trail, lines = [hand], []
    while True:
        lines.append(f"{task} {hand.sender} -> {hand.receiver} "
                     f"({hand.hop}): {hand.reason}")
        stop = breaker(hand, cap, meter)
        if not stop and (hand.receiver not in agents
                         or not board.claim(task, hand.receiver)):
            stop = f"none: {hand.receiver} cannot take it"
        if not stop:
            context = [asdict(h) for h in trail] if full else \
                asdict(hand)
            agent = agents[hand.receiver]
            out, seconds = agent.turn(hand, context, meter)
            if seconds > DEADLINE:
                stop = f"stall: no answer in {DEADLINE} s"
            elif isinstance(out, Handoff):
                board.release(task, agent.name)
                hand = out
                trail.append(out)
                continue
            else:
                board.finish(task, agent.name, out)
                lines.append(f"{task} {agent.name}: {out}")
                return "done", lines, len(trail) - 1
        board.release(task, hand.receiver)
        board.claim(task, "person")
        board.finish(task, "person", stop)
        lines.append(f"{task} STOP {stop}; to a person")
        return stop.split(":")[0], lines, len(trail) - 1


def run_desk(agents, tasks=TASKS, cap=MAX_HANDOFFS, full=False):
    """Every task through one supervisor; returns the totals."""
    board, meter = Board(), Meter()
    out = {"board": board, "meter": meter, "lines": [], "hops": 0,
           "done": 0, "person": 0, "duplicate": 0}
    for task, text in tasks:
        outcome, lines, hops = supervise(task, text, agents, board,
                                         meter, cap, full)
        kind = outcome if outcome in ("done", "duplicate") else \
            "person"
        out[kind] += 1
        out["lines"] += lines
        out["hops"] += hops
    return out


DESIGNS = {
    "one agent": lambda: run_desk({"one": ONE}),
    "supervisor": lambda: run_desk(desk()),
    "full trace": lambda: run_desk(desk(), full=True),
    "no breaker": lambda: run_desk(desk(), cap=None),
}


def summary(r):
    m = r["meter"]
    return (f"done {r['done']}, to a person {r['person']}, "
            f"worker handoffs {r['hops']}, calls {len(m.calls)}, "
            f"tokens {m.tokens():,}")


def demo_designs():
    base = None
    print(f"{'design':<12}{'calls':>6}{'tokens':>8}{'x one':>7}"
          f"{'done':>6}{'person':>8}")
    for name, make in DESIGNS.items():
        r = make()
        tokens = r["meter"].tokens()
        base = base or tokens
        print(f"{name:<12}{len(r['meter'].calls):>6}{tokens:>8,}"
              f"{tokens / base:>7.2f}{r['done']:>6}{r['person']:>8}")


def demo_conflict():
    """Two workers decide the same fact from the same first read."""
    board = Board()
    value, seen = board.read("A-1003 remedy")
    print(f"billing and shipping read A-1003 remedy: {value} "
          f"(v{seen})")
    print("shipping writes replace:",
          board.write("A-1003 remedy", "replace", seen, "shipping"))
    print("billing writes refund:",
          board.write("A-1003 remedy", "refund", seen, "billing"))
    value, seen = board.read("A-1003 remedy")
    print(f"billing rereads: {value} (v{seen}); no refund is sent")


def open_jobs(path=":memory:"):
    """The job table: one row per job, its worker, and its holder."""
    db = sqlite3.connect(path, isolation_level=None, timeout=5)
    db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,"
               " worker TEXT, holder TEXT)")
    return db


def dispatch(db, task, text, agents):
    """Plain code, no model call: one job per order the text names."""
    found = topics(text)
    to = next((a.name for a in agents.values()
               if found and set(found) <= a.owns), "person")
    jobs = [(f"{task}/{oid}", to) for oid in ORDER_ID.findall(text)]
    db.executemany("INSERT OR IGNORE INTO jobs (id, worker) "
                   "VALUES (?, ?)", jobs)
    return jobs


def claim_job(db, job, agent):
    """One conditional update; its row count names the one winner."""
    n = db.execute("UPDATE jobs SET holder = ? WHERE id = ? "
                   "AND holder IS NULL", (agent, job)).rowcount
    return "claimed" if n == 1 else "busy"


def main(argv):
    mode = argv[0] if argv else "trace"
    if mode == "designs":
        return demo_designs()
    if mode == "conflict":
        return demo_conflict()
    r = run_desk(desk(), cap=None if mode == "nobreaker" else
                 MAX_HANDOFFS)
    print("\n".join(r["lines"]))
    print(summary(r))


if __name__ == "__main__":
    main(sys.argv[1:])
