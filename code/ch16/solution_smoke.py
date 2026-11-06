"""Task solution: one more smoke check, for a request with no message.

    python -m ch16.solution_smoke

A bad request must get a 400, and the service must still be healthy
after it. The check joins the four in smoke_test.py.
"""
import sys

from ch16.smoke_test import CHECKS, call, smoke


def check_bad_request(base):
    code, _body = call(base, "/tasks", {"order": "A-1002"})
    health, state = call(base, "/health")
    ok = code == 400 and health == 200 and state["ok"]
    return ok, f"{code} on no message, then health {health}"


if __name__ == "__main__":
    sys.exit(smoke(CHECKS + [check_bad_request]))
