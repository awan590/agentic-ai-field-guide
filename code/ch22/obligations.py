"""Print which rules in a dated obligations table apply to an agent.

    python -m ch22.obligations [tier T] [on YYYY-MM-DD] [region A,B]

Each rule in the table carries the date it applies, the date it was
read, its source, and the words the source used. The profile says
where the agent runs, its risk tier, and who holds each role. The
output is a working checklist to bring to counsel, not legal advice.
The profile is synthetic.
"""
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
TABLE = HERE / "obligations-2026-11.json"
PROFILE = HERE / "agent_profile.json"
TODAY = date(2026, 11, 4)
MAX_AGE = 90                 # days before a row must be read again
NEEDS = ("id", "region", "tiers", "role", "duty", "applies", "read",
         "source", "says")
GROUPS = (("in force", "IN FORCE (law that applies now)"),
          ("coming", "COMING (dated, not yet applicable)"),
          ("guidance", "GUIDANCE (no binding duty on file)"))
KEYS = {"tier", "on", "region", "profile"}
USAGE = ("usage: python -m ch22.obligations [tier T] [on YYYY-MM-DD]"
         " [region A,B]")


def load(path):
    with open(path) as fh:
        return json.load(fh)


def problems(table):
    """Return one line for each missing field or bad date."""
    found = []
    for n, rule in enumerate(table["rules"]):
        name = rule.get("id", f"rule {n}")
        found += [f"{name}: no {key}" for key in NEEDS
                  if not rule.get(key)]
        if "binding" not in rule:
            found.append(f"{name}: no binding")
        for key in ("passed", "applies", "read"):
            try:
                if rule.get(key):
                    date.fromisoformat(rule[key])
            except ValueError:
                found.append(f"{name}: bad {key} {rule[key]}")
    return found


def status(rule, profile, on=TODAY):
    """Return in force, coming, guidance, or why the rule is skipped."""
    if rule["region"] not in profile["regions"]:
        return "other region"
    if not {"any", profile["tier"]} & set(rule["tiers"]):
        return "other tier"
    if rule["role"] != "any" and rule["role"] not in profile["roles"]:
        return "other role"
    if date.fromisoformat(rule["applies"]) > on:
        return "coming"
    return "in force" if rule["binding"] else "guidance"


def stale(rule, on=TODAY, days=MAX_AGE):
    """True when the row was read more than `days` days before on."""
    return (on - date.fromisoformat(rule["read"])).days > days


def report(table, profile, on=TODAY):
    """Return the lines that say what applies to the agent on a day."""
    rules = table["rules"]
    said = {r["id"]: status(r, profile, on) for r in rules}
    roles = profile["roles"]
    out = [f"Table {table['table']}, read {table['read_on']}; "
           f"as of {on}.",
           f"Agent {profile['agent']} for {profile['customer']}, "
           f"tier {profile['tier']}.",
           "Regions: " + ", ".join(profile["regions"]),
           table["note"]]
    for key, title in GROUPS:
        rows = [r for r in rules if said[r["id"]] == key]
        out += ["", title]
        for r in rows:
            owner = roles.get(r["role"], "no owner")
            out.append(f"  {r['id']:<12}{r['applies']}  {r['role']}: "
                       f"{owner}  " + ", ".join(r["source"]))
            out.append(f"  {'':<12}{r['duty']}")
        out += [] if rows else ["  (none)"]
    live = [r for r in rules if not said[r["id"]].startswith("other")]
    have = {r["region"] for r in rules}
    notes = [f"  {r['id']:<12}{r['check']}" for r in live
             if r.get("check")]
    gaps = [f"  {g}: no rows on file; check the regulator's current "
            "page" for g in profile["regions"] if g not in have]
    old = [f"  {r['id']:<12}read {r['read']}" for r in live
           if stale(r, on)]
    out += ["", "CHECK WITH COUNSEL"] + (notes or ["  (none)"])
    out += ["", "GAPS"] + (gaps or ["  (none)"])
    out += ["", f"STALE (read over {MAX_AGE} days before {on})"]
    out += old or ["  (none)"]
    skipped = [s for s in said.values() if s.startswith("other")]
    kinds = ", ".join(f"{k} {skipped.count(k)}"
                      for k in sorted(set(skipped)))
    out += ["", f"Skipped {len(skipped)} of {len(rules)} rules: "
            f"{kinds or 'none'}."]
    return out


def main(argv):
    opts = dict(zip(argv[::2], argv[1::2]))
    if len(argv) % 2 or set(opts) - KEYS:
        print(USAGE)
        return 2
    table = load(TABLE)
    profile = load(opts.get("profile", PROFILE))
    profile["tier"] = opts.get("tier", profile["tier"])
    if "region" in opts:
        profile["regions"] = opts["region"].split(",")
    on = date.fromisoformat(opts.get("on", TODAY.isoformat()))
    bad = problems(table)
    if bad:
        print("\n".join(bad))
        return 1
    print("\n".join(report(table, profile, on)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
