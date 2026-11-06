"""A fallback chain from model to person, and a circuit breaker.

    python -m ch15.fallbacks               # every part healthy
    python -m ch15.fallbacks model-down    # the main model fails
    python -m ch15.fallbacks models-down   # both models fail
    python -m ch15.fallbacks orders-down   # kill the orders API

An order question needs the order record first. With the record,
the chain tries the main model, a smaller model, and a fixed rule.
With no record there is nothing true to say, so the task goes to a
person. Faults are injected; times are simulated seconds.
"""
import sys

from ch02.store import get_order
from ch15.budget_guard import SimClock, to_person


class ModelDown(Exception):
    """A model call that failed: an outage, a rate limit, a timeout."""


class CircuitBreaker:
    """Closed, open, half-open: stop calling a part that keeps failing.

    Only outages count as failures. An answer such as "no order with
    that id" is data about the shopper's request, not about the API.
    """

    def __init__(self, name, clock, threshold=3, reset_after=30.0):
        self.name, self.clock = name, clock
        self.threshold, self.reset_after = threshold, reset_after
        self.state, self.failures, self.opened = "closed", 0, 0.0
        self.log = []

    def _move(self, state):
        self.log.append((self.clock.now, self.state, state))
        self.state = state

    def call(self, fn, *args):
        if self.state == "open":
            if self.clock.now - self.opened < self.reset_after:
                return {"error": f"{self.name} breaker open"}
            self._move("half-open")
        try:
            result = fn(*args)
        except (ConnectionError, TimeoutError) as exc:
            self.failures += 1
            if self.state == "half-open" or \
                    self.failures >= self.threshold:
                self.opened = self.clock.now
                self._move("open")
            return {"error": f"{self.name}: {exc}"}
        self.failures = 0
        if self.state == "half-open":
            self._move("closed")
        return result


def stand_in(name):
    """A stand-in model that words the order record it is given."""
    def reply(record):
        return f"{record['id']} is {record['status']} ({name})."
    return reply


def rule(record):
    """The fixed rule: a template, no model, no new words."""
    return f"Order {record['id']}: status {record['status']}."


def run_chain(rungs, task, record):
    """Try each rung in order; a person takes what none can answer."""
    tried = []
    if "error" in record:
        tried.append(f"record: {record['error']}")
    else:
        for name, rung in rungs:
            try:
                return {"by": name, "text": rung(record),
                        "tried": tried}
            except ModelDown as exc:
                tried.append(f"{name}: {exc}")
    return dict(to_person(task, "; ".join(tried)), by="person",
                tried=tried)


def down(what):
    """Fault injection: a part that fails every call."""
    def fail(*_args):
        raise ModelDown(f"{what} down (injected)")
    return fail


def down_until(clock, fn, until):
    """Fault injection: the orders API refuses calls until a time."""
    def flaky(*args, **kwargs):
        if clock.now < until:
            raise ConnectionError("unreachable (injected)")
        return fn(*args, **kwargs)
    return flaky


def demo(mode):
    clock = SimClock()
    orders = CircuitBreaker("orders", clock)
    rungs = [("main model", stand_in("main model")),
             ("small model", stand_in("small model")), ("rule", rule)]
    if mode in ("model-down", "models-down"):
        rungs[0] = ("main model", down("main model"))
    if mode == "models-down":
        rungs[1] = ("small model", down("small model"))
    fetch = get_order
    if mode == "orders-down":
        fetch = down_until(clock, get_order, 45.0)
    for _ in range(6 if mode == "orders-down" else 1):
        record = orders.call(fetch, "A-1002")
        out = run_chain(rungs, "Has A-1002 shipped?", record)
        said = out.get("text") or out["handoff"].reason
        print(f"t={clock.now:>2g} {orders.state:<9} {out['by']:<11} "
              f"{said}"[:72])
        if out["by"] != "person":
            for line in out["tried"]:
                print(f"     skipped {line}")
        clock.advance(10.0)
    for when, old, new in orders.log:
        print(f"breaker at t={when:g}: {old} -> {new}")


if __name__ == "__main__":
    demo(sys.argv[1] if len(sys.argv) > 1 else "healthy")
