"""The agent as a small web service: an API, a queue, one worker.

    python -m ch16.app        # serve on 127.0.0.1:8016; Ctrl+C stops
    python -m ch16.app dead   # a broken task is parked at once

POST /tasks takes {"message": ..., "order": ..., "email": ...} and
answers at once with a task id. One worker thread takes tasks off a
bounded queue and runs the agent; GET /tasks/<id> returns the result.
GET /health is for the load balancer, GET /version for people. This
is standard library code for teaching: Python's docs say http.server
is not for production, so a real service would use a framework such
as FastAPI behind a production server.
"""
import json
import os
import queue
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ch04.payments import Busy
from ch12.agent import PROMPT
from ch16.release import Releases, build, run_bundle

HOST, PORT = "127.0.0.1", 8016
QUEUE_SIZE = 100          # tasks that may wait; one more gets a 429
RETRY_AFTER = 5           # seconds a caller waits after a 429
MAX_BODY = 10_000         # bytes in one request body
TRIES = 3                 # most runs of one task, then a dead letter
BRIEF = (TimeoutError, Busy)  # failures that may clear on their own
KEY_NAME = "ANTHROPIC_API_KEY"


def key_ready(bundle, env=os.environ):
    """A real model needs its key; the stand-in model needs none."""
    return bundle["model"].startswith("stand-in") or KEY_NAME in env


class AgentService:
    """A bounded queue, one worker thread, and the results so far."""

    def __init__(self, releases, size=QUEUE_SIZE):
        self.releases = releases
        self.queue = queue.Queue(maxsize=size)
        self.results = {}
        self.dead = {}            # the dead-letter table, by task id
        self.count = 0
        self.lock = threading.Lock()
        self.worker = threading.Thread(target=self.work, daemon=True)

    def submit(self, body):
        """Route and queue one task; raise queue.Full when full."""
        with self.lock:
            if self.queue.full():
                raise queue.Full
            self.count += 1
            task_id = f"T-{self.count:04d}"
            bundle = self.releases.route(task_id)
            self.results[task_id] = {"status": "queued",
                                     "version": bundle["version"]}
            self.queue.put_nowait((task_id, bundle, body))
        return task_id

    def work(self):
        """Run queued tasks one at a time until a None arrives."""
        while (item := self.queue.get()) is not None:
            self.results[item[0]].update(self.attempt(*item))

    def attempt(self, task_id, bundle, body):
        """Retry a brief failure up to TRIES runs; park a bug now."""
        for tries in range(1, TRIES + 1):
            try:
                out = run_bundle(bundle, dict(body, id=task_id))
                return {"status": "done", "answer": out["answer"],
                        "stop": out["stop"], "steps": out["steps"]}
            except Exception as exc:  # one bad task must not kill it
                error = type(exc).__name__
                if not isinstance(exc, BRIEF):
                    break             # a bug: a retry only repeats it
        self.dead[task_id] = {"task": body, "error": error,
                              "version": bundle["version"]}
        return {"status": "dead letter", "tries": tries, "error": error}

    def result(self, task_id):
        return self.results.get(task_id)

    def health(self):
        """Liveness, queue length, and the dead-letter depth."""
        return {"ok": self.worker.is_alive(),
                "queued": self.queue.qsize(),
                "dead_letters": len(self.dead)}


def read_task(handler):
    """The request body as a task, or None when it is not one."""
    size = int(handler.headers.get("Content-Length") or 0)
    if not 0 < size <= MAX_BODY:
        return None
    try:
        body = json.loads(handler.rfile.read(size))
    except ValueError:
        return None
    if not isinstance(body, dict) or not isinstance(
            body.get("message"), str) or not body["message"].strip():
        return None
    return {k: body[k] for k in ("message", "order", "email")
            if isinstance(body.get(k), str)}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/tasks":
            return self.reply(404, {"error": "no such route"})
        task = read_task(self)
        if task is None:
            return self.reply(400, {"error": "JSON with a message"})
        try:
            task_id = self.server.service.submit(task)
        except queue.Full:
            return self.reply(429, {"error": "queue full, retry later"},
                              [("Retry-After", str(RETRY_AFTER))])
        self.reply(202, {"id": task_id, "status": "queued"})

    def do_GET(self):
        service = self.server.service
        if self.path == "/health":
            state = service.health()
            return self.reply(200 if state["ok"] else 503, state)
        if self.path == "/version":
            stable = service.releases.bundles[
                service.releases.pointer["stable"]]
            return self.reply(200, dict(service.releases.pointer,
                                        model=stable["model"]))
        if self.path.startswith("/tasks/"):
            found = service.result(self.path.removeprefix("/tasks/"))
            if found:
                return self.reply(200, found)
        self.reply(404, {"error": "no such route or task"})

    def reply(self, code, data, headers=()):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass              # quiet; Chapter 14's traces do the logging


def start(releases, port=0, host=HOST):
    """Serve in a thread; port 0 asks the system for a free port."""
    server = ThreadingHTTPServer((host, port), Handler)
    server.service = AgentService(releases)
    server.service.worker.start()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop(server, thread):
    """Stop taking requests, then let the worker finish and exit."""
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    server.service.queue.put(None, timeout=5)
    server.service.worker.join(timeout=5)


def address(server):
    """The base address a caller uses, such as a smoke test."""
    return "http://%s:%d" % server.server_address[:2]


def show_dead_letters():
    """One good task and one broken one, run in this thread."""
    service = AgentService(Releases(build(PROMPT)))
    good = service.submit({"message": "Where is my order?",
                           "order": "A-1002"})
    bad = service.submit({"order": "A-1002"})    # no message: it fails
    service.queue.put(None)
    service.work()
    for task_id in (good, bad):
        found = service.result(task_id)
        how = (f"in {found['steps']} steps" if found["status"] == "done"
               else f"after {found['tries']} of {TRIES} tries, "
                    f"{found['error']}")
        print(f"{task_id}: {found['status']} {how}")
    for task_id, row in service.dead.items():
        print(f"dead-letter table: {task_id}, bundle {row['version']},"
              f" {row['error']}")
    depth = service.health()["dead_letters"]
    print(f"dead-letter depth {depth}: the alert fires above 0")
    return 0


def main(argv=()):
    if list(argv[:1]) == ["dead"]:
        return show_dead_letters()
    host = os.environ.get("HOST", HOST)
    port = int(os.environ.get("PORT", PORT))
    releases = Releases(build(PROMPT))
    stable = releases.bundles[releases.pointer["stable"]]
    if not key_ready(stable):
        print(f"{KEY_NAME} is not set; the model needs it.")
        return 1
    server, thread = start(releases, port, host)
    print(f"Serving on {address(server)}; Ctrl+C stops.", flush=True)
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    stop(server, thread)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
