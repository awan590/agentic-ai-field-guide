"""Cost per task, break-even month, and sensitivity for an agent.

Reads assumptions.json and takes the rest from earlier chapters:
tickets a week from the Chapter 17 baseline, handle minutes and
error rates from the Chapter 20 pilot and its control group, and
the model cost of one refund task from Chapter 3's price table.
Every number is synthetic, and the same files print the same table.

    python -m ch23.roi_model                  # cost per task, months
    python -m ch23.roi_model error_scale=2    # change one input
    python -m ch23.roi_model --sensitivity    # one input at a time
    python -m ch23.roi_model --fte            # full-time equivalents
"""
import json
import sys
from pathlib import Path

from ch03.cost_per_task import RERUNS, load_prices, parts, run_metered
from ch17 import baseline
from ch20.pilot_vs_control import load_weeks, readout

HERE = Path(__file__).parent
ASSUMPTIONS = HERE / "assumptions.json"
WEEKS_PER_MONTH = 52 / 12
LABELS = {"run_month": ("run cost a month", "${:,.0f}"),
          "tickets_month": ("tickets a month", "{:,.0f}"),
          "build": ("build cost", "${:,.0f}"),
          "cost_per_hour": ("desk cost an hour", "${:.2f}"),
          "model_per_task": ("model cost a task", "${:.4f}"),
          "agent_minutes": ("agent minutes", "{:.2f}"),
          "agent_reopen": ("agent reopened %", "{:.2f}"),
          "agent_wrong": ("agent wrong refund %", "{:.2f}")}


def model_cost(name):
    """Dollars of model tokens for one refund task (Chapter 3)."""
    price = load_prices()["models"][name]
    calls = run_metered("refund")[2]
    return sum(parts(calls, price).values()) * (1 + RERUNS)


def inputs(path=ASSUMPTIONS):
    """One flat dict: the JSON's numbers plus the measured ones."""
    a = json.loads(Path(path).read_text())
    week = baseline.summary(baseline.load())["all"]["per_week"]
    pilot = readout(load_weeks(["week1", "week2"]))
    x = {"as_of": a["as_of"], "model": a["agent"]["model"],
         "tickets_week": week, "tickets_month": week * WEEKS_PER_MONTH,
         "handoff": pilot["handoff"]["pilot"],
         "pilot_tickets": pilot["tickets"]["pilot"],
         "model_per_task": model_cost(a["agent"]["model"]),
         "build": sum(a["build"].values()),
         "run_month": a["run_month"]["hosting_and_tools"]
         + a["run_month"]["engineer_hours"]
         * a["run_month"]["engineer_rate"],
         "horizon_months": a["horizon_months"], "ranges": a["ranges"],
         **a["desk"], **a["errors"], **a["agent"]}
    x["intervals"] = {}
    for key, name in (("minutes", "minutes"), ("reopened", "reopen"),
                      ("wrong_refund", "wrong")):
        m = pilot[key]
        x["person_" + name] = m["control"]
        x["agent_" + name] = m["pilot"]
        x["intervals"]["agent_" + name] = (
            max(0.0, m["control"] + m["low"]), m["control"] + m["high"])
    return x


def cost_per_task(x):
    """Dollars per ticket on each side, split into parts."""
    rate = x["cost_per_hour"] / 60
    sides = {}
    for side in ("person", "agent"):
        agent = side == "agent"
        scale = x["error_scale"] if agent else 1.0
        handle = x[side + "_minutes"] * rate
        sides[side] = {
            "handle time": handle,
            "review sample": agent * x["review_share"]
            * x["review_minutes"] * rate,
            "repeat contacts": x[side + "_reopen"] * scale / 100
            * handle,
            "wrong refunds": x[side + "_wrong"] * scale / 100
            * x["wrong_refund_cost"],
            "model": agent * x["model_per_task"]}
    return sides


def saving_per_task(x):
    sides = cost_per_task(x)
    return sum(sides["person"].values()) - sum(sides["agent"].values())


def months(x):
    """Month by month: share on the agent, saving, cumulative total."""
    per_task, ramp = saving_per_task(x), x["ramp"]
    total, rows = -x["build"], []
    for month in range(1, x["horizon_months"] + 1):
        share = ramp[month - 1] if month <= len(ramp) else 1.0
        saving = x["tickets_month"] * share * per_task
        total += saving - x["run_month"]
        rows.append((month, share, saving, total))
    return rows


def break_even(rows):
    """First month the cumulative total reaches zero, or None."""
    return next((m for m, _, _, total in rows if total >= 0), None)


def sensitivity(x):
    """Break-even month at the good and the bad end of each input."""
    ends = dict(x["intervals"])
    for key, (good, bad) in x["ranges"].items():
        ends[key] = (x[key] * good, x[key] * bad)
    late = x["horizon_months"] + 1
    table = []
    for key, pair in ends.items():
        good, bad = (break_even(months(dict(x, **{key: v})))
                     for v in pair)
        table.append((key, pair, good, bad,
                      (bad or late) - (good or late)))
    return sorted(table, key=lambda row: -row[4])


def money(v, places=0):
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.{places}f}"


def show(x, changed):
    sides = cost_per_task(x)
    print(f"Returns agent model (synthetic, as of {x['as_of']})")
    if changed:
        print("inputs changed:", " ".join(changed))
    print(f"tickets a month {x['tickets_month']:,.0f} (ch17 baseline, "
          f"{x['tickets_week']} a week)")
    print(f"handle minutes: person {x['person_minutes']:.2f}, agent "
          f"{x['agent_minutes']:.2f} (ch20 control and pilot)")
    print(f"model cost a task ${x['model_per_task']:.4f} (ch03 prices,"
          f" {x['model']})")
    print(f"\n{'cost per task':<18}{'person':>8}{'agent':>9}")
    for part in sides["person"]:
        print(f"{part:<18}{money(sides['person'][part], 2):>8}"
              f"{money(sides['agent'][part], 2):>9}")
    person, agent = (sum(sides[s].values()) for s in sides)
    print(f"{'total':<18}{money(person, 2):>8}{money(agent, 2):>9}")
    print(f"{'saving per task':<18}{money(person - agent, 2):>17}")
    print(f"\nbuild {money(x['build'])}, run "
          f"{money(x['run_month'])} a month")
    print(f"{'month':>5}{'share':>7}{'saving':>10}{'cumulative':>12}")
    rows = months(x)
    for month, share, saving, total in rows[:12]:
        print(f"{month:5}{share:7.0%}{money(saving):>10}"
              f"{money(total):>12}")
    found = break_even(rows)
    print("break-even:", f"month {found}" if found else
          f"none in {x['horizon_months']} months")
    print("net after 24 months:", money(rows[23][3]))


def show_sensitivity(x):
    wrong = round(x["agent_wrong"] * x["pilot_tickets"] / 100)
    print("Sensitivity: break-even month, one input at a time "
          "(synthetic)")
    print(f"base case: month {break_even(months(x))}; ch20 pilot: "
          f"{wrong} wrong refunds in {x['pilot_tickets']} tickets")
    print(f"{'input':<22}{'good':>9}{'bad':>9}{'at good':>9}"
          f"{'at bad':>8}{'swing':>7}")
    for key, pair, good, bad, swing in sensitivity(x):
        label, fmt = LABELS[key]
        print(f"{label:<22}{fmt.format(pair[0]):>9}"
              f"{fmt.format(pair[1]):>9}{good or '-':>9}"
              f"{bad or '-':>8}{swing:>7}")


def show_fte(x):
    """Desk hours a month the agent frees, counted three ways."""
    hours, n = x["fte_hours_month"], x["tickets_month"]
    saved = (x["person_minutes"] - x["agent_minutes"]
             - x["review_share"] * x["review_minutes"])
    rows = [("every ticket the agent touched", n * x["person_minutes"]),
            ("minus tickets handed to a person",
             n * (1 - x["handoff"] / 100) * x["person_minutes"]),
            ("pilot minus control, after review", n * saved)]
    print("Full-time equivalents, returns desk (synthetic, "
          f"{hours} hours a month)")
    print(f"{'count':<34}{'hours':>8}{'FTE':>7}")
    for label, minutes in rows:
        print(f"{label:<34}{minutes / 60:8.1f}"
              f"{minutes / 60 / hours:7.2f}")


def main(argv):
    x = inputs()
    changed = [arg for arg in argv if "=" in arg]
    for arg in changed:
        key, value = arg.split("=", 1)
        if key not in x or isinstance(x[key], (str, list, dict)):
            print(f"unknown input: {key}")
            return 2
        x[key] = float(value)
    if "--sensitivity" in argv:
        show_sensitivity(x)
    elif "--fte" in argv:
        show_fte(x)
    else:
        show(x, changed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
