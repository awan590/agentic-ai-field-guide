"""Task solution: a tone-drift alert, proved on the replayed bad day.

    python -m ch14.solution_tone

The rule pages when the share of flagged replies in the last 60
simulated minutes is over five times the normal day's share, with
at least three flagged replies, for two checks in a row. Both days
are synthetic. It must stay quiet on the normal day.
"""
from ch14.alerts import MARKS, RULES, evaluate, load_day, metrics

TONE_RULE = {"name": "tone drift", "metric": "tone", "times": 5.0,
             "min_count": 3, "severity": "page"}


def fires(name, rules):
    """Every alert that fires on one replayed day."""
    base = metrics(load_day("normal_day"))
    return [a for a in evaluate(load_day(name), rules, base)
            if a["state"] == "fire"]


def main():
    rules = RULES + [TONE_RULE]
    base = metrics(load_day("normal_day"))
    print(f"baseline tone share (normal day): {base['tone']:.2%}")
    for name in ("normal_day", "bad_day"):
        found = fires(name, rules)
        print(f"{name}: {len(found)} alerts fire")
        for a in found:
            print(f"  {a['time']}  {a['severity']:6} {a['rule']:14}"
                  f" {a['value']:.1%}")
    for time, text in MARKS.items():
        print(f"mark {time}  {text}")


if __name__ == "__main__":
    main()
