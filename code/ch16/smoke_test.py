"""Smoke test: start the service, call it, stop it, report.

    python -m ch16.smoke_test          # exit 1 if any check fails
    python -m ch16.smoke_test files    # the container files, checked

The service starts in this process on a free port (port 0), so the
test needs no Docker and no network. The Dockerfile and compose.yaml
are text only: they were not built or run for this book, and the
files mode only checks that their text agrees with app.py.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from ch12.agent import PROMPT
from ch16.app import KEY_NAME, PORT, address, start, stop
from ch16.release import Releases, build

HERE = Path(__file__).parent
DEPLOY = ("Dockerfile", "compose.yaml")


def call(base, path, body=None):
    """One request; returns (status code, JSON body)."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers={
        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")


def wait_done(base, task_id, cap=10.0):
    """Poll one task until it leaves the queue, for cap seconds."""
    end = time.monotonic() + cap
    while time.monotonic() < end:
        code, found = call(base, f"/tasks/{task_id}")
        if code == 200 and found["status"] != "queued":
            return found
        time.sleep(0.05)
    return {"status": "timed out"}


def check_health(base):
    code, body = call(base, "/health")
    return code == 200 and body["ok"], f"{code} worker alive"


def check_version(base):
    code, body = call(base, "/version")
    return code == 200 and body["canary"] is None, \
        f"{code} stable {body.get('stable')}"


def check_task(base):
    code, body = call(base, "/tasks", {"message": "Where is my order?",
                                       "order": "A-1002"})
    if code != 202:
        return False, f"{code} on POST /tasks"
    found = wait_done(base, body["id"])
    return found["status"] == "done", \
        f"{body['id']} {found['status']} in {found.get('steps')} steps"


def check_unknown_route(base):
    code, _body = call(base, "/nothing-here")
    return code == 404, f"{code} on GET /nothing-here"


CHECKS = [check_health, check_version, check_task, check_unknown_route]


def smoke(checks=CHECKS):
    """Run each check against a fresh service; 0 if all pass."""
    server, thread = start(Releases(build(PROMPT)), port=0)
    base = address(server)
    passed = 0
    try:
        for check in checks:
            name = check.__name__.removeprefix("check_")
            try:
                ok, detail = check(base)
            except OSError as exc:
                ok, detail = False, type(exc).__name__
            passed += bool(ok)
            print(f"{'PASS' if ok else 'FAIL'}  {name:<14}{detail}")
    finally:
        stop(server, thread)
    print(f"{passed} of {len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


def file_checks():
    """What the container files must agree on with app.py."""
    docker, compose = ((HERE / n).read_text() for n in DEPLOY)
    leak = re.compile(rf"{KEY_NAME}\s*[=:]\s*\S")
    return [
        ("CMD runs ch16.app", '"-m", "ch16.app"' in docker),
        (f"port {PORT} in both", all(str(PORT) in t
                                    for t in (docker, compose))),
        ("listens on 0.0.0.0", "HOST=0.0.0.0" in docker),
        ("healthcheck calls /health", "/health" in compose),
        ("no key value in files", not any(leak.search(t)
                                          for t in (docker, compose))),
    ]


def show_files():
    for name in DEPLOY:
        print(f"--- {name} (text only, not built or run for this book)")
        print((HERE / name).read_text().rstrip())
    results = file_checks()
    for label, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
    return 0 if all(ok for _label, ok in results) else 1


if __name__ == "__main__":
    sys.exit(show_files() if sys.argv[1:] == ["files"] else smoke())
