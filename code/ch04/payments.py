"""A stand-in payments API that fails on purpose, offline.

Each call to pay() takes the next outcome from a script:

    "ok"    the payout goes through and the reply arrives
    "busy"  the API answers 503 and pays nothing
    "lost"  the payout goes through, then the reply never arrives

"lost" is the dangerous case: the money moved, yet the caller sees
only a timeout. Like Stripe's API, pay() honors an idempotency key:
a call with a key it has seen returns the first result again and
pays nothing new.
"""


class FakeClock:
    """Time that moves only when code moves it. Tests never wait."""

    def __init__(self):
        self.now = 0.0
        self.waits = []

    def advance(self, seconds):
        self.now = round(self.now + seconds, 6)

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.advance(seconds)


class Busy(Exception):
    """The API answered 503: nothing was paid; try again later."""


class Payments:
    def __init__(self, clock, script=(), latency=0.3):
        self.clock = clock
        self.script = list(script)
        self.latency = latency
        self.payouts = []
        self.saved = {}
        self.calls = 0

    def pay(self, order_id, amount, key=None, timeout=2.0):
        """Pay once per key. May raise Busy or TimeoutError."""
        self.calls += 1
        outcome = self.script.pop(0) if self.script else "ok"
        if outcome == "busy":
            self.clock.advance(self.latency)
            raise Busy("payments API busy (503)")
        payout = self.saved.get(key)
        if payout is None:
            payout = {"payout_id": f"PO-{len(self.payouts) + 1:03d}",
                      "order_id": order_id, "amount": amount}
            self.payouts.append(payout)
            if key is not None:
                self.saved[key] = payout
        if outcome == "lost":
            self.clock.advance(timeout)
            raise TimeoutError(f"no reply in {timeout}s")
        self.clock.advance(self.latency)
        return dict(payout)

    def total_paid(self):
        return round(sum(p["amount"] for p in self.payouts), 2)
