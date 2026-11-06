"""Turn a per-action scope table into the policy file a guard reads.

    python -m ch18.autonomy_dial

Chapter 13's policy.py keeps its rules in Python dicts, and its check()
reads no file. This module writes one dial setting per action to a
JSON file, and guard() loads that file on top of Chapter 13's check.
The stricter verdict wins, so the file can tighten Chapter 13's rules
but never loosen them.
"""
import copy
import json
import sys

from ch13 import policy as ch13
from ch18.risk_tier import ACTIONS, tier

DIAL = ("OFF", "DRAFT", "ASK", "NOTIFY", "AUTO")
VERDICT = {"OFF": "BLOCK", "DRAFT": "BLOCK", "ASK": "ASK",
           "NOTIFY": "ALLOW", "AUTO": "ALLOW"}
WHY = {"OFF": "dial OFF: not this agent's job",
       "DRAFT": "dial DRAFT: the agent drafts, the {owner} acts",
       "ASK": "dial ASK: the {owner} approves first",
       "NOTIFY": "dial NOTIFY: runs, then the {owner} is told",
       "AUTO": "dial AUTO: runs and is logged"}
CEILING = {1: "AUTO", 2: "NOTIFY", 3: "ASK"}
RANK = {"ALLOW": 0, "ASK": 1, "BLOCK": 2}


def notch(setting, step=1):
    """Move a setting up the dial (more autonomy) or down, at most
    to either end."""
    k = DIAL.index(setting) + step
    return DIAL[max(0, min(k, len(DIAL) - 1))]


def build_policy(scope):
    """Return the policy dict for a scope table. An action with no
    rating counts as tier 3."""
    actions = {}
    for name, (setting, owner) in scope["actions"].items():
        rated = ACTIONS.get(name)
        actions[name] = {
            "setting": setting, "verdict": VERDICT[setting],
            "tier": tier(*rated) if rated else 3, "owner": owner,
            "why": WHY[setting].format(owner=owner)}
    return {"agent": scope["agent"], "version": scope["version"],
            "actions": actions, "never": sorted(scope["never"])}


def problems(policy):
    """List the lines of a policy that break the dial's rules."""
    out = []
    for name, a in sorted(policy["actions"].items()):
        top = CEILING[a["tier"]]
        if DIAL.index(a["setting"]) > DIAL.index(top):
            out.append(f"{name}: {a['setting']} is above the tier "
                       f"{a['tier']} ceiling {top}")
        if name in policy["never"] and a["setting"] != "OFF":
            out.append(f"{name}: on the never list but not OFF")
        if a["verdict"] != VERDICT[a["setting"]]:
            out.append(f"{name}: verdict does not match its dial")
    return out


def write_policy(scope, path):
    """Write the scope's policy file, or raise if it breaks a rule."""
    policy = build_policy(scope)
    bad = problems(policy)
    if bad:
        raise ValueError("; ".join(bad))
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(policy, indent=2, sort_keys=True) + "\n")
    return policy


def load_policy(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def guard(policy, session, name, args):
    """Return the stricter (verdict, why) of Chapter 13 and the file."""
    if name in policy["never"]:
        return "BLOCK", f"{name} is on the never list"
    entry = policy["actions"].get(name)
    if entry is None:
        return "BLOCK", f"{name} is not in the scope file"
    verdict, why = ch13.check(session, name, args)
    if RANK[entry["verdict"]] >= RANK[verdict]:
        verdict, why = entry["verdict"], entry["why"]
    return verdict, why


def change(scope, name, step):
    """Return a copy of the scope with one action moved on the dial
    and the version raised by one."""
    new = copy.deepcopy(scope)
    setting, owner = new["actions"][name]
    new["actions"][name] = (notch(setting, step), owner)
    new["version"] += 1
    return new


def diff(old, new):
    """List each action whose setting differs between two policies."""
    out = []
    for name in sorted(set(old["actions"]) | set(new["actions"])):
        a = old["actions"].get(name, {}).get("setting", "none")
        b = new["actions"].get(name, {}).get("setting", "none")
        if a != b:
            out.append(f"{name}: {a} -> {b}")
    return out


def promote(scope, name, clean, need=50):
    """Move one action up a notch once it has `need` clean runs in a
    row; else return the scope as it was. OFF stays OFF, and no action
    goes past its tier's ceiling."""
    a = build_policy(scope)["actions"][name]
    top = DIAL.index(CEILING[a["tier"]])
    if (clean < need or a["setting"] == "OFF"
            or DIAL.index(a["setting"]) >= top):
        return scope
    return change(scope, name, 1)


def demote(scope, name):
    """Move one action down a notch. Call it on any incident, and
    count that action's clean runs again from 0."""
    return change(scope, name, -1)


def main():
    print(f"{'setting':9}{'verdict':9}what happens")
    for setting in DIAL:
        why = WHY[setting].split(": ")[1].format(owner="owner")
        print(f"{setting:9}{VERDICT[setting]:9}{why}")
    caps = ", ".join(f"tier {t} {s}" for t, s in CEILING.items())
    print(f"ceilings: {caps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
