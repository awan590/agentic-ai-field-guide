"""Tests for Chapter 9: handoffs, the board, the breaker, the task.

Run from code/:  python -m unittest tests.test_ch09
"""
import dataclasses
import tempfile
import threading
import unittest
from pathlib import Path

from ch09 import solution_returns as sol
from ch09 import supervisor as sv

T3 = sv.TASKS[2]


def one_task(task, agents, cap=sv.MAX_HANDOFFS, full=False):
    board, meter = sv.Board(), sv.Meter()
    outcome, lines, hops = sv.supervise(*task, agents, board, meter,
                                        cap, full)
    return outcome, lines, hops, board, meter


class HandoffTest(unittest.TestCase):
    def test_a_handoff_needs_a_reason(self):
        with self.assertRaises(ValueError):
            sv.Handoff("T-9", "billing", "shipping", " ", "hi", 2)

    def test_a_handoff_cannot_be_changed_in_flight(self):
        h = sv.Handoff("T-9", "billing", "shipping", "why", "hi", 2)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            h.hop = 0


class BoardTest(unittest.TestCase):
    def test_one_holder_at_a_time(self):
        b = sv.Board()
        self.assertTrue(b.claim("T-1", "billing"))
        self.assertFalse(b.claim("T-1", "shipping"))
        b.release("T-1", "billing")
        self.assertTrue(b.claim("T-1", "shipping"))

    def test_a_finished_task_cannot_be_claimed_or_finished(self):
        b = sv.Board()
        b.claim("T-1", "billing")
        self.assertTrue(b.finish("T-1", "billing", "refund sent"))
        self.assertFalse(b.claim("T-1", "billing"))
        self.assertFalse(b.finish("T-1", "billing", "refund sent"))
        self.assertEqual(b.log, [("T-1", "billing")])

    def test_a_stale_write_is_refused(self):
        b = sv.Board()
        _, seen = b.read("A-1003 remedy")
        self.assertEqual(b.write("A-1003 remedy", "replace", seen,
                                 "shipping"), "ok, v1")
        self.assertTrue(b.write("A-1003 remedy", "refund", seen,
                                "billing").startswith("refused"))
        self.assertEqual(b.read("A-1003 remedy"), ("replace", 1))


class SupervisorTest(unittest.TestCase):
    def test_a_simple_task_takes_one_route_and_one_turn(self):
        outcome, lines, hops, board, meter = one_task(
            sv.TASKS[0], sv.desk())
        self.assertEqual((outcome, hops), ("done", 0))
        self.assertEqual(board.done["T-1"][0], "shipping")
        self.assertEqual([c[1] for c in meter.calls],
                         ["supervisor", "shipping"])

    def test_the_breaker_stops_a_ping_pong_after_three(self):
        outcome, lines, hops, board, _ = one_task(T3, sv.desk())
        self.assertEqual(outcome, "loop")
        self.assertEqual(board.done["T-3"][0], "person")
        moves = [x for x in lines if " -> " in x]
        self.assertEqual(len(moves), sv.MAX_HANDOFFS + 1)
        self.assertIn("over the cap of 3", lines[-1])

    def test_without_the_breaker_only_the_token_cap_stops_it(self):
        capped = one_task(T3, sv.desk())
        free = one_task(T3, sv.desk(), cap=None)
        self.assertEqual(free[0], "token cap")
        self.assertGreater(free[2], 3 * capped[2])
        self.assertGreater(free[4].tokens(), sv.TASK_TOKENS)

    def test_a_stalled_worker_goes_to_a_person(self):
        outcome, _, _, board, _ = one_task(sv.TASKS[4], sv.desk())
        self.assertEqual(outcome, "stall")
        self.assertFalse(board.finish("T-5", "shipping", "late"))

    def test_one_agent_settles_t3_alone(self):
        outcome, _, hops, _, meter = one_task(T3, {"one": sv.ONE})
        self.assertEqual((outcome, hops, len(meter.calls)),
                         ("done", 0, 1))

    def test_token_cost_by_design(self):
        tokens = {k: make()["meter"].tokens()
                  for k, make in sv.DESIGNS.items()}
        self.assertLess(tokens["one agent"], tokens["supervisor"])
        self.assertLess(tokens["supervisor"], tokens["full trace"])
        self.assertLess(tokens["full trace"], tokens["no breaker"])


class ReturnsTaskTest(unittest.TestCase):
    def test_no_task_is_handled_twice(self):
        r = sv.run_desk(sol.desk_with_returns(), sv.TASKS + sv.TASKS)
        tasks = [t for t, _ in sv.TASKS]
        self.assertEqual(sol.twice(r["board"]), [])
        self.assertEqual(sorted(t for t, _ in r["board"].log), tasks)
        self.assertEqual(r["duplicate"], len(tasks))
        first = sv.run_desk(sol.desk_with_returns())
        self.assertEqual(len(r["meter"].calls),
                         len(first["meter"].calls))

    def test_returns_owns_t3_and_the_ping_pong_is_gone(self):
        outcome, _, hops, board, _ = one_task(
            T3, sol.desk_with_returns())
        self.assertEqual((outcome, hops), ("done", 0))
        self.assertEqual(board.done["T-3"][0], "returns")


class QuotedNumbersTest(unittest.TestCase):
    """The numbers the chapter quotes that no printed run shows."""

    def test_tokens_per_task(self):
        rows = [({"one": sv.ONE}, [127, 134, 145, 132, 130]),
                (sv.desk(), [179, 193, 555, 193, 190]),
                (sol.desk_with_returns(), [194, 208, 241, 208, 205])]
        for agents, want in rows:
            meter = sv.run_desk(agents)["meter"]
            self.assertEqual([meter.tokens(t) for t, _ in sv.TASKS],
                             want)

    def test_routing_calls_cost(self):
        for agents, want in ((sv.desk(), 476),
                             (sol.desk_with_returns(), 553)):
            calls = sv.run_desk(agents)["meter"].calls
            self.assertEqual(sum(i + o for _, who, i, o in calls
                                 if who == "supervisor"), want)

    def test_t3_with_full_trace_and_with_no_breaker(self):
        self.assertEqual(one_task(T3, sv.desk(), full=True)[4].tokens(),
                         699)
        _, lines, hops, _, meter = one_task(T3, sv.desk(), cap=None)
        self.assertEqual((hops, meter.tokens()), (10, 1609))
        self.assertIn("(11)", lines[-2])
        self.addCleanup(setattr, sv, "TASK_TOKENS", sv.TASK_TOKENS)
        sv.TASK_TOKENS = 3000            # the try box's copy
        _, lines, _, _, meter = one_task(T3, sv.desk(), cap=None)
        self.assertEqual(meter.tokens(), 3114)
        self.assertIn("(21)", lines[-2])


class ClaimTest(unittest.TestCase):
    """The job table: plain-code dispatch and one-winner claims."""
    ASK = "SELECT holder FROM jobs WHERE id = ?"

    def file_db(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = str(Path(tmp.name) / "jobs.db")
        db = sv.open_jobs(path)
        self.addCleanup(db.close)
        return path, db

    def test_dispatch_makes_one_job_per_order(self):
        db = sv.open_jobs()
        text = "Where are orders A-1001, A-1006, and A-1008?"
        for _ in range(2):               # a second run adds nothing
            jobs = sv.dispatch(db, "T-6", text, sv.desk())
        self.assertEqual(jobs, [("T-6/A-1001", "shipping"),
                                ("T-6/A-1006", "shipping"),
                                ("T-6/A-1008", "shipping")])
        count = "SELECT COUNT(*) FROM jobs WHERE holder IS NULL"
        self.assertEqual(db.execute(count).fetchone()[0], 3)
        self.assertEqual(sv.dispatch(db, *T3, sv.desk()),
                         [("T-3/A-1003", "person")])

    def test_a_second_claim_is_told_busy(self):
        db = sv.open_jobs()
        sv.dispatch(db, *sv.TASKS[0], sv.desk())
        self.assertEqual(sv.claim_job(db, "T-1/A-1001", "shipping"),
                         "claimed")
        self.assertEqual(sv.claim_job(db, "T-1/A-1001", "billing"),
                         "busy")
        self.assertEqual(db.execute(self.ASK, ("T-1/A-1001",))
                         .fetchone()[0], "shipping")

    def test_two_claims_race_and_one_wins(self):
        path, db = self.file_db()
        for i in range(20):
            job = f"R-{i}/A-1001"
            sv.dispatch(db, f"R-{i}", "Where is A-1001?", sv.desk())
            gate, got = threading.Barrier(2, timeout=5), {}

            def claim(agent):
                mine = sv.open_jobs(path)
                gate.wait()
                got[agent] = sv.claim_job(mine, job, agent)
                mine.close()

            racers = [threading.Thread(target=claim, args=(a,))
                      for a in ("billing", "shipping")]
            for t in racers:
                t.start()
            for t in racers:
                t.join(timeout=10)
            self.assertEqual(sorted(got.values()), ["busy", "claimed"])
            winner = min(got, key=lambda a: got[a] != "claimed")
            self.assertEqual(db.execute(self.ASK, (job,))
                             .fetchone()[0], winner)

    def test_check_then_write_lets_two_through(self):
        db = sv.open_jobs()
        sv.dispatch(db, *sv.TASKS[0], sv.desk())
        job = ("T-1/A-1001",)
        seen = [db.execute(self.ASK, job).fetchone()[0]
                for _ in range(2)]       # both read before a write
        won = []
        for agent, holder in zip(("billing", "shipping"), seen):
            if holder is None:
                db.execute("UPDATE jobs SET holder = ? WHERE id = ?",
                           (agent, job[0]))
                won.append(agent)
        self.assertEqual(won, ["billing", "shipping"])
        self.assertEqual(db.execute(self.ASK, job).fetchone()[0],
                         "shipping")


if __name__ == "__main__":
    unittest.main()
