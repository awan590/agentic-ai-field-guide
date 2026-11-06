"""Weekly active users and task share from a usage log.

The log has one row per returns ticket: the week after go-live, the
ticket id, the desk person who handled it, and what happened to the
agent's draft. "used" means the person sent the draft, edited or not;
"opened" means they looked at it and wrote their own reply; "none"
means they never opened it. In weeks 1 to 4, a hash of the ticket id
holds 5% of tickets back with the agent off, as Chapter 20 asked;
those tickets leave every denominator. The log is synthetic: 18
trained desk staff and 640 tickets a week for 8 weeks, from seed 21.

    python -m ch21.adoption            # the eight weeks against targets
    python -m ch21.adoption loose      # the same log, counted loosely
"""
import random
import sys

from ch20.pilot_vs_control import arm_for

STAFF = [f"S{k:02d}" for k in range(1, 19)]
WEEKS, PER_WEEK, HOLDOUT_WEEKS = 8, 640, 4
WAU_GOAL = {1: 50, 2: 60, 3: 70}             # percent; 80 from week 4
SHARE_GOAL = {1: 20, 2: 35, 3: 45, 4: 55}    # percent; 60 from week 5


def make_log(seed=21):
    """A synthetic log: most staff ramp up, three never send a draft."""
    rng = random.Random(seed)
    late = set(rng.sample(STAFF, 3))
    start = {s: rng.choice([1, 1, 2, 2, 3]) for s in STAFF}
    ceiling = {s: rng.uniform(0.62, 0.86) for s in STAFF}
    rows = []
    for week in range(1, WEEKS + 1):
        for i in range(PER_WEEK):
            ticket, who = f"R{week}-{i:04d}", rng.choice(STAFF)
            held = arm_for(ticket, 95) == "control"
            if week <= HOLDOUT_WEEKS and held:
                outcome = "holdout"
            else:
                ramp = min(1.0, max(0, week - start[who] + 1) / 3)
                p_use = 0.0 if who in late else ceiling[who] * ramp
                r = rng.random()
                outcome = ("used" if r < p_use else
                           "opened" if r < p_use + 0.2 else "none")
            rows.append({"week": week, "ticket": ticket, "staff": who,
                         "outcome": outcome})
    return rows


def weekly(rows, active=("used",)):
    """Per week: eligible tickets, active staff, and task share %."""
    out = []
    for week in sorted({r["week"] for r in rows}):
        mine = [r for r in rows if r["week"] == week
                and r["outcome"] != "holdout"]
        users = {r["staff"] for r in mine if r["outcome"] in active}
        done = sum(r["outcome"] in active for r in mine)
        out.append({"week": week, "eligible": len(mine),
                    "holdout": sum(r["week"] == week and
                                   r["outcome"] == "holdout"
                                   for r in rows),
                    "active": len(users),
                    "wau": round(100 * len(users) / len(STAFF)),
                    "share": round(100 * done / len(mine))})
    return out


def goals(week):
    return WAU_GOAL.get(week, 80), SHARE_GOAL.get(week, 60)


def not_active(rows, weeks):
    """Trained staff with no sent draft in the given weeks."""
    users = {r["staff"] for r in rows
             if r["week"] in weeks and r["outcome"] == "used"}
    return [s for s in STAFF if s not in users]


def main(argv):
    rows = make_log()
    loose = "loose" in argv
    active = ("used", "opened") if loose else ("used",)
    print("Adoption, synthetic log (seed 21), 18 trained desk staff")
    print("Active means:", "opened a draft (loose)" if loose
          else "sent a draft")
    print("week  eligible  holdout  active  WAU %  goal  share %  "
          "goal  result")
    for w in weekly(rows, active):
        wau_goal, share_goal = goals(w["week"])
        ok = w["wau"] >= wau_goal and w["share"] >= share_goal
        print(f"{w['week']:>4}  {w['eligible']:>8}  {w['holdout']:>7}  "
              f"{w['active']:>3}/18  {w['wau']:>5}  {wau_goal:>4}  "
              f"{w['share']:>7}  {share_goal:>4}  "
              f"{'PASS' if ok else 'MISS'}")
    last = [WEEKS - 1, WEEKS]
    names = ", ".join(not_active(rows, last)) or "none"
    print(f"No draft sent in weeks {last[0]}-{last[1]}: {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
