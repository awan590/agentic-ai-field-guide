"""Release the agent as one versioned bundle, behind a canary.

    python -m ch16.release              # what a version is made of
    python -m ch16.release canary       # bad prompt to 5%, roll back
    python -m ch16.release model NAME   # a new model name needs a gate
    python -m ch16.release ramp         # 5, 25, 50, 100% behind a gate

A bundle holds the four parts that decide what the agent does: the
prompt, the model name, the tool list, and the policy. Its version is
a hash of those parts, so any change makes a new version, and no
version is ever edited. The pointer names the stable bundle and the
canary; a rollback moves the pointer back in one step. The requests
in the canary demo are synthetic, replayed from Chapter 12's cases.
"""
import contextlib
import hashlib
import io
import json
import re
import sys

from ch02.mini_agent import run_agent
from ch07.search_tool import AGENT_TOOLS, check_citations
from ch12.agent import HERE as CH12
from ch12.agent import PROMPT, PromptModel, load_prompt
from ch12.gate import gate
from ch12.run_evals import load_cases
from ch13.policy import CALL_CAP, ROLES, check

MODEL = "stand-in-1"      # the model name Chapter 14's traces use
CANARY = 5                # percent of tasks that go to the canary
LIMIT = 2.0               # points of bad answers the canary may add
LEAST = 30                # canary tasks needed before a verdict
RAMP = (5, 25, 50, 100)   # the book's example ramp, not a standard
PROMISE = re.compile(r"refund (is|was|has been|will be) (on its way"
                     r"|issued|sent|paid)", re.I)


def build(prompt_file, model=MODEL):
    """Freeze the four parts into one bundle named by its hash."""
    parts = {"prompt": load_prompt(prompt_file), "model": model,
             "tools": sorted(AGENT_TOOLS),
             "policy": {"role": "support",
                        "tools": sorted(ROLES["support"]),
                        "call_cap": CALL_CAP}}
    raw = json.dumps(parts, sort_keys=True).encode()
    return dict(parts, version=hashlib.sha256(raw).hexdigest()[:12])


def in_canary(task_id, share=CANARY):
    """Hash the task id; the same id always lands on the same side."""
    digest = hashlib.sha256(task_id.encode()).hexdigest()
    return int(digest[:8], 16) % 100 < share


class Releases:
    """Every bundle built, the ones that passed the gate, a pointer."""

    def __init__(self, stable):
        self.bundles = {stable["version"]: stable}
        self.passed = {stable["version"]}
        self.pointer = {"stable": stable["version"], "canary": None}
        self.history = []
        self.share = CANARY       # percent of tasks the canary gets

    def add(self, bundle):
        self.bundles[bundle["version"]] = bundle
        return bundle["version"]

    def evaluate(self, version, cases):
        """Run Chapter 12's gate: this version against the stable."""
        stable = self.bundles[self.pointer["stable"]]
        why = gate(stable["prompt"], self.bundles[version]["prompt"],
                   cases)
        if not why:
            self.passed.add(version)
        return why

    def start_canary(self, version, skip_gate=False):
        if version not in self.passed and not skip_gate:
            raise ValueError(f"{version} has no passing gate run")
        self.pointer["canary"] = version

    def route(self, task_id):
        """The bundle that serves one task."""
        canary = self.pointer["canary"]
        if canary and in_canary(task_id, self.share):
            return self.bundles[canary]
        return self.bundles[self.pointer["stable"]]

    def promote(self):
        self.history.append(self.pointer["stable"])
        self.pointer = {"stable": self.pointer["canary"],
                        "canary": None}

    def rollback(self):
        """One pointer move: drop the canary, else undo a promotion."""
        if self.pointer["canary"]:
            self.pointer["canary"] = None
        elif self.history:
            self.pointer["stable"] = self.history.pop()


def guarded(name, spec, session):
    """Wrap one tool so Chapter 13's policy checks every call."""
    def fn(**args):
        verdict, why = check(session, name, args)
        if verdict != "ALLOW":
            return {"error": f"{verdict}: {why}"}
        session["calls"] += 1
        return spec["fn"](**args)
    return dict(spec, fn=fn)


def run_bundle(bundle, task):
    """One agent run under one bundle's prompt, tools, and policy."""
    order = task.get("order")
    session = {"role": bundle["policy"]["role"], "calls": 0,
               "orders": {order} if order else set(),
               "email": task.get("email")}
    tools = {n: guarded(n, AGENT_TOOLS[n], session)
             for n in bundle["tools"]}
    return run_agent(PromptModel(bundle["prompt"], task), tools,
                     task["message"], max_steps=4)


def bad_answer(result):
    """Signs of a bad answer that a canary sees without labels."""
    text = result["answer"] or ""
    return (result["stop"] != "done" or bool(PROMISE.search(text))
            or not check_citations(result)["ok"])


def watch(releases, tasks):
    """Run each task on the bundle it routes to; count bad answers."""
    tally = {"stable": [0, 0], "canary": [0, 0]}
    for task in tasks:
        bundle = releases.route(task["id"])
        arm = ("canary" if bundle["version"] ==
               releases.pointer["canary"] else "stable")
        tally[arm][0] += 1
        tally[arm][1] += bad_answer(run_bundle(bundle, task))
    return tally


def verdict(tally, limit=LIMIT, least=LEAST):
    """WAIT until the canary has enough tasks, then compare rates."""
    (s_n, s_bad), (c_n, c_bad) = tally["stable"], tally["canary"]
    if c_n < least:
        return "WAIT", 0.0
    worse = 100 * (c_bad / c_n - s_bad / max(s_n, 1))
    return ("ROLL BACK" if worse > limit else "PROMOTE"), worse


def ramp(releases, tasks, steps=RAMP):
    """Widen the canary step by step, with the same gate at each step.

    Each step gets fresh tasks. The stable counts add up over the
    steps, so the 100% step still has a rate to compare with. Any
    call but PROMOTE rolls back: every task goes to the old bundle.
    """
    size, base, log = len(tasks) // len(steps), [0, 0], []
    for k, share in enumerate(steps):
        releases.share = share
        tally = watch(releases, tasks[k * size:(k + 1) * size])
        base = [a + b for a, b in zip(base, tally["stable"])]
        call, points = verdict(dict(tally, stable=base))
        log.append((share, *tally["canary"], call, points))
        if call != "PROMOTE":
            releases.rollback()
            break
    else:
        releases.promote()
    releases.share = CANARY
    return log


def replay(n=2000):
    """Synthetic shopper tasks, replayed from Chapter 12's cases."""
    cases = load_cases()
    return [dict(cases[i % len(cases)], id=f"T-{i:04d}")
            for i in range(1, n + 1)]


def show_bundle():
    stable = build(PROMPT)
    print(f"bundle {stable['version']}")
    print(f"  model   {stable['model']}")
    print(f"  tools   {', '.join(stable['tools'])}")
    pol = stable["policy"]
    print(f"  policy  {pol['role']} role, {len(pol['tools'])} tools,"
          f" call cap {pol['call_cap']}")
    print(f"  prompt  {len(stable['prompt'])} lines")
    print(f"same four parts again:  {build(PROMPT)['version']}")
    agree = build(CH12 / "prompt_agreeable.txt")["version"]
    print(f"one prompt line added:  {agree}")
    print(f"model name changed:     "
          f"{build(PROMPT, 'stand-in-2')['version']}")


def show_canary():
    releases = Releases(build(PROMPT))
    bad = releases.add(build(CH12 / "prompt_agreeable.txt"))
    stable = releases.pointer["stable"]
    releases.start_canary(bad, skip_gate=True)
    print(f"stable {stable}, canary {bad} (gate skipped)")
    tally = watch(releases, replay())
    for arm, (n, worse) in tally.items():
        print(f"  {arm:<7}{n:>5} tasks{worse:>4} bad answers"
              f"  {100 * worse / n:5.1f}%")
    call, points = verdict(tally)
    print(f"verdict: {call}, canary {points:.1f} points worse"
          f" (limit {LIMIT:.0f})")
    releases.rollback()
    print(f"after rollback: {releases.pointer}")
    served = {releases.route(t["id"])["version"] for t in replay()}
    print(f"next 2000 tasks served by: {', '.join(sorted(served))}")


def show_model(name):
    releases = Releases(build(PROMPT))
    new = releases.add(build(PROMPT, name))
    print(f"stable {releases.pointer['stable']}, new {new} ({name})")
    try:
        releases.start_canary(new)
    except ValueError as exc:
        print(f"canary refused: {exc}")
    why = releases.evaluate(new, load_cases())
    print("GATE FAIL" if why else "GATE PASS")
    if not why:
        releases.start_canary(new)
        print(f"canary started: {new} on {CANARY}% of tasks")


def show_ramp_log(log):
    for share, n, bad, call, points in log:
        print(f"  step {share:>3}%: {n:>4} canary tasks, {bad:>2} bad,"
              f" {points:4.1f} points worse, {call}")


def show_ramp():
    releases = Releases(build(PROMPT))
    new = releases.add(build(PROMPT, "stand-in-2"))
    with contextlib.redirect_stdout(io.StringIO()):
        why = releases.evaluate(new, load_cases())
    print(f"{new} (stand-in-2): {'GATE FAIL' if why else 'GATE PASS'}")
    releases.start_canary(new)
    show_ramp_log(ramp(releases, replay(4000)))
    print(f"after the ramp: {releases.pointer}")
    releases = Releases(build(PROMPT))
    bad = releases.add(build(CH12 / "prompt_agreeable.txt"))
    releases.start_canary(bad, skip_gate=True)
    print(f"{bad} (agreeable prompt): gate skipped")
    show_ramp_log(ramp(releases, replay(4000)))
    served = {releases.route(t["id"])["version"] for t in replay()}
    print(f"next 2000 tasks served by: {', '.join(sorted(served))}")


def main(argv):
    if argv[:1] == ["canary"]:
        show_canary()
    elif argv[:1] == ["ramp"]:
        show_ramp()
    elif argv[:1] == ["model"]:
        show_model(argv[1] if len(argv) > 1 else "stand-in-2")
    else:
        show_bundle()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
