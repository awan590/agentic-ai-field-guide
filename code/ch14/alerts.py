"""Replay a day of synthetic traffic and run alert rules on it.

Each line of a day file sums up one traced conversation: the time,
the shopper's ask, the reply, duration, tokens, error, and handoff.
Both days are synthetic: one conversation every two simulated
minutes, 720 a day. The normal day is the baseline for drift.

    python -m ch14.alerts             # the bad day: metrics, alerts
    python -m ch14.alerts normal      # the normal day
    python -m ch14.alerts noise       # naive rules against windows
    python -m ch14.alerts review      # sample, label, eval case
"""
import json
import math
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
MARKS = {"14:00": "release with a new prompt (synthetic)",
         "18:00": "a shopper posts screenshots (synthetic)"}
TONE = re.compile(r"\b(damn|hate|stupid|terrible|useless|worst)\b",
                  re.IGNORECASE)
RULES = [
    {"name": "error rate", "metric": "errors", "over": 0.05,
     "min_count": 3, "severity": "page"},
    {"name": "slow replies", "metric": "p95_s", "over": 8.0,
     "severity": "page"},
    {"name": "token drift", "metric": "tokens", "times": 1.5,
     "severity": "ticket"},
    {"name": "handoff drift", "metric": "handoffs", "times": 2.5,
     "min_count": 6, "severity": "ticket"},
]


def load_day(name):
    lines = (HERE / f"{name}.jsonl").read_text().splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def minute(hhmm):
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def tone_flag(reply):
    """A cheap code check: does the reply swear or attack?"""
    return bool(TONE.search(reply))


def metrics(window):
    """The five health metrics for one window of conversations."""
    n = len(window)
    ms = sorted(e["ms"] for e in window)
    return {"n": n,
            "errors": sum(e["err"] for e in window) / n,
            "p95_s": ms[math.ceil(0.95 * n) - 1] / 1000,
            "tokens": sum(e["tok"] for e in window) / n,
            "handoffs": sum(e["handoff"] for e in window) / n,
            "tone": sum(tone_flag(e["reply"]) for e in window) / n}


def breached(rule, now, base):
    """Over a fixed limit, or over a multiple of the baseline."""
    value = now[rule["metric"]]
    limit = rule.get("over")
    if limit is None:
        limit = rule["times"] * base[rule["metric"]]
    enough = value * now["n"] >= rule.get("min_count", 0)
    return value > limit and enough


def evaluate(day, rules, base, size=60, step=10, hold=2):
    """Every step minutes, check each rule on the last size minutes.
    A rule fires after hold breaches in a row and resolves after
    hold clear checks in a row."""
    alerts, streak, firing = [], {}, set()
    for end in range(size, 1440 + 1, step):
        window = [e for e in day if end - size <= minute(e["t"]) < end]
        now = metrics(window)
        for rule in rules:
            name, hit = rule["name"], breached(rule, now, base)
            changed = hit != (name in firing)
            streak[name] = streak.get(name, 0) + 1 if changed else 0
            if streak[name] < hold:
                continue
            streak[name] = 0
            firing.symmetric_difference_update({name})
            alerts.append({"time": clock(end), "rule": name,
                           "severity": rule["severity"],
                           "state": "fire" if hit else "resolve",
                           "value": round(now[rule["metric"]], 3)})
    return alerts


def show_alerts(alerts):
    for a in alerts or [None]:
        if a is None:
            print("  none")
            continue
        value = a["value"]
        text = f"{value:.1%}" if value < 1 else f"{value:g}"
        print(f"  {a['time']}  {a['state']:7} {a['severity']:6}"
              f" {a['rule']:14} {text}")


def row(label, m):
    print(f"{label:5}  {m['errors']:6.1%}  {m['p95_s']:5.1f}"
          f"  {m['tokens']:6.0f}  {m['handoffs']:8.1%}"
          f"  {m['tone']:5.1%}")


def dashboard(name, rules):
    day, base = load_day(name), metrics(load_day("normal_day"))
    print(f"{name}.jsonl: {len(day)} conversations, synthetic")
    print("time = 60 simulated minutes before it; base = normal day")
    print("time   errors  p95 s  tokens  handoffs   tone")
    row("base", base)
    for end in range(120, 1440 + 1, 120):
        row(clock(end), metrics([e for e in day
                                 if end - 60 <= minute(e["t"]) < end]))
    if name == "bad_day":
        for time, text in MARKS.items():
            print(f"mark {time}  {text}")
    print("alerts:")
    show_alerts(evaluate(day, rules, base))


def noise():
    """What naive one-event rules would send on a normal day."""
    day = load_day("normal_day")
    fired = evaluate(day, RULES, metrics(day))
    rows = [("one alert per error", sum(e["err"] for e in day)),
            ("one alert per reply over 5 s",
             sum(e["ms"] > 5000 for e in day)),
            ("one alert per flagged reply",
             sum(tone_flag(e["reply"]) for e in day)),
            ("windowed rules, held two checks",
             sum(a["state"] == "fire" for a in fired))]
    print("normal_day.jsonl, synthetic: alerts each rule would send")
    for label, count in rows:
        print(f"  {label:40} {count:3}")


def keep(event, rng, rate=0.02):
    """Tail sampling: every error, handoff, or flag, plus a few."""
    if event["err"] or event["handoff"] or tone_flag(event["reply"]):
        return True
    return rng.random() < rate


def eval_case(event, n):
    """A reviewed bad trace becomes a ch12-style eval case."""
    return {"id": f"T{n:02d}", "from": f"bad_day {event['t']}",
            "kind": "tone", "message": event["ask"],
            "must": ["orders"],
            "must_not": ["damn", "terrible", "useless", "worst"]}


def review():
    day, rng = load_day("bad_day"), random.Random(14)
    kept = [e for e in day if keep(e, rng)]
    flagged = [e for e in kept if tone_flag(e["reply"])]
    print(f"bad_day.jsonl, synthetic: {len(day)} traces, "
          f"{len(kept)} kept by tail sampling")
    print(f"  tone flags kept: {len(flagged)} of "
          f"{sum(tone_flag(e['reply']) for e in day)}")
    first = next(e for e in flagged if minute(e["t"]) >= 14 * 60)
    print(f"  first flag after the release: {first['t']}")
    print("  reply:", first["reply"])
    print(json.dumps(eval_case(first, 1), indent=2))


def main(argv):
    command = argv[0] if argv else "bad"
    if command == "noise":
        noise()
    elif command == "review":
        review()
    else:
        dashboard("normal_day" if command == "normal" else "bad_day",
                  RULES)


if __name__ == "__main__":
    main(sys.argv[1:])
