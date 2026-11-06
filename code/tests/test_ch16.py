"""Tests for Chapter 16: the versioned bundle, the canary and its
rollback, the service, and the smoke test. Every server a test starts
is stopped before the test ends.

Run from code/:  python -m unittest tests.test_ch16
"""
import io
import json
import os
import select
import signal
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from ch12.agent import HERE as CH12
from ch12.agent import PROMPT
from ch12.run_evals import load_cases
from ch16 import app
from ch16 import release as rel
from ch16 import smoke_test as st
from ch16.solution_smoke import check_bad_request

CODE = Path(__file__).resolve().parents[1]
BAD = CH12 / "prompt_agreeable.txt"


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()):
        return fn(*args)


def post(base, path, body):
    req = urllib.request.Request(base + path,
                                 data=json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), json.load(resp)
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), json.load(err)


class BundleTest(unittest.TestCase):
    def test_same_parts_give_the_same_version(self):
        self.assertEqual(rel.build(PROMPT)["version"],
                         rel.build(PROMPT)["version"])

    def test_prompt_or_model_change_gives_a_new_version(self):
        base = rel.build(PROMPT)["version"]
        self.assertNotEqual(rel.build(BAD)["version"], base)
        self.assertNotEqual(rel.build(PROMPT, "stand-in-2")["version"],
                            base)

    def test_bundle_holds_the_four_parts(self):
        bundle = rel.build(PROMPT)
        for part in ("prompt", "model", "tools", "policy"):
            self.assertIn(part, bundle)
        self.assertEqual(len(bundle["version"]), 12)


class CanaryTest(unittest.TestCase):
    def setUp(self):
        self.releases = rel.Releases(rel.build(PROMPT))
        self.stable = self.releases.pointer["stable"]
        self.bad = self.releases.add(rel.build(BAD))

    def test_routing_is_sticky_and_near_five_percent(self):
        ids = [f"T-{i:05d}" for i in range(10_000)]
        hits = [rel.in_canary(i) for i in ids]
        self.assertEqual(hits, [rel.in_canary(i) for i in ids])
        self.assertTrue(400 <= sum(hits) <= 600, sum(hits))

    def test_rollback_is_one_pointer_move(self):
        self.releases.start_canary(self.bad, skip_gate=True)
        self.releases.rollback()
        self.assertEqual(self.releases.pointer,
                         {"stable": self.stable, "canary": None})
        served = {self.releases.route(f"T-{i:04d}")["version"]
                  for i in range(500)}
        self.assertEqual(served, {self.stable})

    def test_promote_then_rollback_restores_the_old_stable(self):
        self.releases.start_canary(self.bad, skip_gate=True)
        self.releases.promote()
        self.assertEqual(self.releases.pointer["stable"], self.bad)
        self.releases.rollback()
        self.assertEqual(self.releases.pointer["stable"], self.stable)

    def test_canary_needs_a_passing_gate_run(self):
        new = self.releases.add(rel.build(PROMPT, "stand-in-2"))
        with self.assertRaises(ValueError):
            self.releases.start_canary(new)
        why = quiet(self.releases.evaluate, new, load_cases())
        self.assertEqual(why, [])
        self.releases.start_canary(new)
        self.assertEqual(self.releases.pointer["canary"], new)

    def test_bad_prompt_fails_the_gate(self):
        why = quiet(self.releases.evaluate, self.bad, load_cases())
        self.assertTrue(why)
        with self.assertRaises(ValueError):
            self.releases.start_canary(self.bad)

    def test_bad_canary_is_rolled_back(self):
        self.releases.start_canary(self.bad, skip_gate=True)
        tally = rel.watch(self.releases, rel.replay(800))
        call, worse = rel.verdict(tally)
        self.assertEqual(call, "ROLL BACK")
        self.assertGreater(worse, rel.LIMIT)

    def test_few_canary_tasks_means_wait(self):
        tally = {"stable": [100, 0], "canary": [5, 5]}
        self.assertEqual(rel.verdict(tally)[0], "WAIT")


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.server, self.thread = app.start(
            rel.Releases(rel.build(PROMPT)))
        port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{port}"

    def tearDown(self):
        app.stop(self.server, self.thread)
        self.assertFalse(self.thread.is_alive())
        self.assertFalse(self.server.service.worker.is_alive())

    def test_post_then_get_result(self):
        code, _h, body = post(self.base, "/tasks",
                              {"message": "Where is my order?",
                               "order": "A-1002"})
        self.assertEqual((code, body["status"]), (202, "queued"))
        found = st.wait_done(self.base, body["id"])
        self.assertEqual(found["status"], "done")
        self.assertTrue(found["answer"])

    def test_health_and_version(self):
        self.assertEqual(st.call(self.base, "/health")[0], 200)
        code, body = st.call(self.base, "/version")
        self.assertEqual(code, 200)
        self.assertEqual(body["model"], rel.MODEL)
        self.assertIsNone(body["canary"])

    def test_bad_body_and_unknown_route(self):
        self.assertEqual(post(self.base, "/tasks", {"x": 1})[0], 400)
        self.assertEqual(post(self.base, "/other", {"message": "a"})[0],
                         404)
        self.assertEqual(st.call(self.base, "/tasks/T-9999")[0], 404)


class FullQueueTest(unittest.TestCase):
    def test_full_queue_answers_429_with_retry_after(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        server.service = app.AgentService(
            rel.Releases(rel.build(PROMPT)), size=1)   # worker idle
        thread = threading.Thread(target=server.serve_forever,
                                  daemon=True)
        thread.start()
        base = "http://127.0.0.1:%d" % server.server_address[1]
        try:
            first = post(base, "/tasks", {"message": "one"})
            second = post(base, "/tasks", {"message": "two"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(first[0], 202)
        self.assertEqual(second[0], 429)
        self.assertEqual(second[1]["Retry-After"], str(app.RETRY_AFTER))
        self.assertFalse(thread.is_alive())


class SmokeTest(unittest.TestCase):
    def test_smoke_passes(self):
        self.assertEqual(quiet(st.smoke), 0)

    def test_failing_check_gives_exit_one(self):
        def check_never(_base):
            return False, "always fails"
        self.assertEqual(quiet(st.smoke, [check_never]), 1)

    def test_container_files_agree_with_the_app(self):
        for label, ok in st.file_checks():
            self.assertTrue(ok, label)

    def test_solution_check_passes(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = st.smoke(st.CHECKS + [check_bad_request])
        self.assertEqual(code, 0)
        self.assertIn("5 of 5 checks passed", out.getvalue())

    def test_key_ready_needs_the_name_only_for_a_real_model(self):
        self.assertTrue(app.key_ready(rel.build(PROMPT), {}))
        real = rel.build(PROMPT, "claude-haiku-5-5")
        self.assertFalse(app.key_ready(real, {}))
        self.assertTrue(app.key_ready(real, {app.KEY_NAME: "x"}))

    def test_app_runs_as_a_process_and_stops_on_ctrl_c(self):
        proc = subprocess.Popen(
            [sys.executable, "-E", "-s", "-m", "ch16.app"], cwd=CODE,
            env=dict(os.environ, PORT="0"), stdout=subprocess.PIPE,
            text=True)
        try:
            ready, _w, _x = select.select([proc.stdout], [], [], 10)
            self.assertTrue(ready, "no Serving line in 10 seconds")
            line = proc.stdout.readline()
            base = line.split()[2].rstrip(";")
            for _try in range(50):
                try:
                    if st.call(base, "/health")[0] == 200:
                        break
                except OSError:
                    time.sleep(0.1)
            proc.send_signal(signal.SIGINT)
            self.assertEqual(proc.wait(timeout=10), 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            proc.stdout.close()


def fake_watch(releases, tasks):
    """Route like watch() but run no agent: every answer is good."""
    tally = {"stable": [0, 0], "canary": [0, 0]}
    for task in tasks:
        version = releases.route(task["id"])["version"]
        arm = "canary" if version == releases.pointer["canary"] else \
            "stable"
        tally[arm][0] += 1
    return tally


class RampTest(unittest.TestCase):
    def setUp(self):
        self.releases = rel.Releases(rel.build(PROMPT))
        self.stable = self.releases.pointer["stable"]
        self.new = self.releases.add(rel.build(PROMPT, "stand-in-2"))

    def test_good_bundle_climbs_each_step_then_is_stable(self):
        self.releases.start_canary(self.new, skip_gate=True)
        with mock.patch.object(rel, "watch", fake_watch):
            log = rel.ramp(self.releases, rel.replay(4000))
        self.assertEqual([row[0] for row in log], [5, 25, 50, 100])
        self.assertEqual({row[3] for row in log}, {"PROMOTE"})
        self.assertEqual(log[-1][1], 1000)
        self.assertEqual(self.releases.pointer,
                         {"stable": self.new, "canary": None})
        self.assertEqual(self.releases.share, rel.CANARY)

    def test_failed_gate_at_a_later_step_sends_all_tasks_back(self):
        self.releases.start_canary(self.new, skip_gate=True)
        calls = [("PROMOTE", 0.0), ("PROMOTE", 0.0), ("ROLL BACK", 3.0)]
        with mock.patch.object(rel, "watch", fake_watch), \
                mock.patch.object(rel, "verdict", side_effect=calls):
            log = rel.ramp(self.releases, rel.replay(4000))
        self.assertEqual([row[0] for row in log], [5, 25, 50])
        self.assertEqual(self.releases.pointer,
                         {"stable": self.stable, "canary": None})
        served = {self.releases.route(t["id"])["version"]
                  for t in rel.replay(500)}
        self.assertEqual(served, {self.stable})

    def test_bad_prompt_stops_at_the_first_step(self):
        bad = self.releases.add(rel.build(BAD))
        self.releases.start_canary(bad, skip_gate=True)
        log = rel.ramp(self.releases, rel.replay(4000))
        self.assertEqual([(row[0], row[3]) for row in log],
                         [(5, "ROLL BACK")])
        self.assertIsNone(self.releases.pointer["canary"])


class DeadLetterTest(unittest.TestCase):
    def setUp(self):
        self.service = app.AgentService(rel.Releases(rel.build(PROMPT)))

    def run_one(self, effects):
        """Queue one task and work it in this thread."""
        with mock.patch.object(app, "run_bundle",
                               side_effect=effects) as run:
            task_id = self.service.submit({"message": "Where is it?"})
            self.service.queue.put(None)
            self.service.work()
        return self.service.result(task_id), run.call_count

    def test_three_failures_make_a_dead_letter(self):
        found, runs = self.run_one(TimeoutError)
        self.assertEqual((found["status"], runs), ("dead letter", 3))
        self.assertEqual(list(self.service.dead), ["T-0001"])
        self.assertEqual(self.service.health()["dead_letters"], 1)

    def test_a_retry_that_works_is_not_a_dead_letter(self):
        done = {"answer": "On its way.", "stop": "done", "steps": 1}
        found, runs = self.run_one([TimeoutError(), done])
        self.assertEqual((found["status"], runs), ("done", 2))
        self.assertEqual(self.service.health()["dead_letters"], 0)

    def test_a_bug_is_a_dead_letter_at_once(self):
        found, runs = self.run_one(KeyError("message"))
        self.assertEqual((found["status"], runs), ("dead letter", 1))
        self.assertEqual((found["tries"], found["error"]),
                         (1, "KeyError"))

    def test_health_route_shows_the_depth(self):
        server, thread = app.start(rel.Releases(rel.build(PROMPT)))
        try:
            code, body = st.call(app.address(server), "/health")
        finally:
            app.stop(server, thread)
        self.assertEqual((code, body["dead_letters"]), (200, 0))


if __name__ == "__main__":
    unittest.main()
