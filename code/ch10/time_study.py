"""A time study: does the coding agent save time on your tasks?

    python -m ch10.time_study                  # the sample log
    python -m ch10.time_study assign T33       # which arm, before work
    python -m ch10.time_study log ch10/my_log.csv T33 41 55   # one row
    python -m ch10.time_study ch10/my_log.csv  # your own log

A coin made from the task's name, not your mood, decides before you
start whether a task gets the agent. Log the minutes on the clock
when it is done. For agent tasks, also log your guess of how long it
would have taken without the agent: that guess is the self-report.
A task with no minutes was skipped, and skips are counted, because
skipping the dull tasks in one arm skews the result.

time_log.csv ships with INVENTED SAMPLE ROWS so the report has
something to read. They are not a measurement. Log your own tasks
in a new file with the log command and pass its path to the report.
"""
import csv
import hashlib
import random
import sys
from pathlib import Path

LOG = Path(__file__).parent / "time_log.csv"
MIN_PER_ARM = 10         # fewer finished tasks: no verdict
DRAWS = 2000             # bootstrap resamples for the interval


def assign(task):
    """The arm for a task, fixed by its name before any work."""
    byte = hashlib.sha256(task.encode()).digest()[0]
    return "agent" if byte % 2 else "none"


def log_task(path, task, minutes, guess=""):
    """Append one finished (or skipped) task; start a new log."""
    new = not Path(path).exists()
    with open(path, "a", newline="") as f:
        if new:
            f.write("task,arm,minutes,guess_without\n")
        csv.writer(f).writerow([task, assign(task), minutes, guess])


def read(path=LOG):
    """Rows from the log; a row whose arm is not the coin's fails."""
    lines = [x for x in Path(path).read_text().splitlines()
             if not x.startswith("#")]
    rows = list(csv.DictReader(lines))
    for r in rows:
        if r["arm"] != assign(r["task"]):
            raise ValueError(f"{r['task']}: arm is not the coin's")
    return rows


def change(with_agent, without):
    """Mean time with the agent over mean time without, minus one."""
    return (sum(with_agent) / len(with_agent)) / \
        (sum(without) / len(without)) - 1


def interval(with_agent, without, seed=10):
    """A 90% bootstrap interval for change(), seeded, so it repeats."""
    rng = random.Random(seed)
    draws = sorted(
        change(rng.choices(with_agent, k=len(with_agent)),
               rng.choices(without, k=len(without)))
        for _ in range(DRAWS))
    return draws[int(0.05 * DRAWS)], draws[int(0.95 * DRAWS) - 1]


def study(rows):
    """Counts and skips; with enough tasks, the changes as well."""
    done = [r for r in rows if r["minutes"]]
    arm = {a: [float(r["minutes"]) for r in done if r["arm"] == a]
           for a in ("agent", "none")}
    guess = [float(r["guess_without"]) for r in done
             if r["arm"] == "agent"]
    skips = {a: sum(1 for r in rows if not r["minutes"]
                    and r["arm"] == a) for a in ("agent", "none")}
    s = {"n": {a: len(x) for a, x in arm.items()}, "skips": skips}
    if min(s["n"].values()) >= MIN_PER_ARM:
        s.update(mean={a: sum(x) / len(x) for a, x in arm.items()},
                 measured=change(arm["agent"], arm["none"]),
                 interval=interval(arm["agent"], arm["none"]),
                 reported=change(arm["agent"], guess))
    return s


def verdict(s):
    if min(s["n"].values()) < MIN_PER_ARM:
        return f"too few tasks: finish {MIN_PER_ARM} in each arm"
    lo, hi = s["interval"]
    if lo > 0:
        return "slower with the agent, as measured"
    if hi < 0:
        return "faster with the agent, as measured"
    return "no clear difference yet: log more tasks"


def main(argv):
    if argv[:1] == ["assign"]:
        for task in argv[1:]:
            print(f"{task}: {assign(task)}")
        return
    if argv[:1] == ["log"]:          # log PATH TASK MINUTES [GUESS]
        log_task(*argv[1:5])
        print(f"{argv[2]}: {assign(argv[2])}, logged in {argv[1]}")
        return
    path = Path(argv[0]) if argv else LOG
    if path.read_text().startswith("# SAMPLE DATA"):
        print("SAMPLE DATA: invented rows, not a measurement")
    s = study(read(path))
    print(f"finished: {s['n']['agent']} with the agent, "
          f"{s['n']['none']} without")
    print(f"skipped:  {s['skips']['agent']} with the agent, "
          f"{s['skips']['none']} without")
    if "mean" in s:
        lo, hi = s["interval"]
        print(f"mean minutes:     {s['mean']['agent']:.1f} with, "
              f"{s['mean']['none']:.1f} without")
        print(f"measured change:  {100 * s['measured']:+.1f}% "
              f"(90% interval {100 * lo:+.1f}% to {100 * hi:+.1f}%)")
        print(f"reported change:  {100 * s['reported']:+.1f}% "
              "(from the guesses)")
    print(f"verdict: {verdict(s)}")


if __name__ == "__main__":
    main(sys.argv[1:])
