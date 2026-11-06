"""Print the bad day's five metrics for every 60-minute window that
ends on the hour: the 24 points each line in Figure 14.2 plots.

    python -m ch14.hourly
"""
from ch14.alerts import clock, load_day, metrics, minute, row


def main():
    day = load_day("bad_day")
    print("bad_day.jsonl: 60-minute windows ending on each hour, "
          "synthetic")
    print("time   errors  p95 s  tokens  handoffs   tone")
    for end in range(60, 1440 + 1, 60):
        row(clock(end), metrics([e for e in day
                                 if end - 60 <= minute(e["t"]) < end]))


if __name__ == "__main__":
    main()
