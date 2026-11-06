"""A latency budget for one voice turn, replayed from recordings.

    python -m ch11.voice_budget

One turn runs from the moment the caller stops speaking to the first
sound of the reply. Its stages: the wait to be sure the caller has
stopped (endpoint), speech to text (stt), the model's first token
(model), any tool call (tool), text to speech (tts), and the network
both ways. BUDGET_MS is one voice vendor's published median target;
SHARE is the book's own split of it. Each recorded case keeps what
the caller said, what speech to text heard, the model's tool call,
and simulated stage timings, so a replay needs no audio and no model.
"""
import json
import sys
from pathlib import Path

from ch11.quantity_check import DRIVE, check

BUDGET_MS = 800
SHARE = {"endpoint": 200, "stt": 100, "model": 300, "tool": 50,
         "tts": 100, "network": 50}
STOP_CAP_MS = 200
CASES = Path(__file__).with_name("voice_cases.json")


def check_turn(timings):
    """Return the turn's total ms and its problems, if any."""
    total = sum(timings.values())
    if total <= BUDGET_MS:
        return total, []
    stage = max(SHARE, key=lambda s: timings.get(s, 0) - SHARE[s])
    over = timings.get(stage, 0) - SHARE[stage]
    return total, [f"over budget by {total - BUDGET_MS} ms; "
                   f"{stage} is {over} ms over its share"]


def replay(case):
    """Run the code's checks on one recorded turn."""
    total, problems = check_turn(case["timings_ms"])
    lines = [tuple(line) for line in case["call"]["lines"]]
    got = {"turn": "slow" if problems else "ok",
           "order": "reject" if check(lines, DRIVE) else "place"}
    if "stop_ms" in case:
        late = case["stop_ms"] > STOP_CAP_MS
        got["stop"] = "late" if late else "ok"
        if late:
            problems.append(f"kept talking {case['stop_ms']} ms after "
                            f"the caller spoke (cap {STOP_CAP_MS})")
    return total, got, problems


def main():
    cases = json.loads(CASES.read_text())
    print(f"Synthetic recordings, simulated ms; budget {BUDGET_MS} ms.")
    passed = 0
    for case in cases:
        total, got, problems = replay(case)
        ok = got == case["expect"]
        passed += ok
        print(f"{case['id']}  {total:5} ms  turn {got['turn']:5} "
              f"order {got['order']:7}{'PASS' if ok else 'FAIL'}  "
              f"{case['note']}")
        for problem in problems:
            print(f"{'':6}{problem}")
    print(f"cases: {len(cases)}, passed: {passed}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
