"""Run one engagement from its folder, gate by gate, in order.

    python -m ch24.run_engagement FOLDER OUT [key=value ...] [--warn]

FOLDER holds one customer's inputs; start from ch24/template. OUT
gets every artifact this run writes, and manifest.json lists them.
Each gate calls the chapter that taught it, and no earlier file is
copied or changed. The run stops at the first gate that fails.
key=value changes one business-case input, as in Chapter 23. Exit
code 0 when every gate passes (or with --warn), 1 when one fails,
2 for a usage error. All the sample data is synthetic.
"""
import hashlib
import json
import sys
from pathlib import Path

from ch12.agent import load_prompt
from ch12.gate import gate
from ch12.run_evals import load_cases
from ch13.cases import ATTACKS, TASKS
from ch13.injection_suite import suite
from ch13.solution_links import strict_links
from ch14.alerts import RULES
from ch16.release import build
from ch17 import baseline
from ch18.autonomy_dial import DIAL, write_policy
from ch19.data_map import scan
from ch20.go_no_go import check_plan, decide
from ch20.pilot_vs_control import readout
from ch21.handover_check import check_pack
from ch22 import obligations
from ch23.roi_model import break_even, money, months, saving_per_task
from ch24.adapters import (case_page, load_pilot, open_tables, quiet,
                           read_json, roi_inputs)


def dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def write(s, name, text, chapter):
    """Write one artifact into OUT and remember who made it."""
    path = s["out"] / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    s["made"].append((name, chapter))


def discovery(s):
    """Week zero: the baseline from the customer's ticket export."""
    base = baseline.summary(baseline.load(s["in"] / "tickets.csv"))
    s["base"], need, every = base, s["eng"]["discovery"], base["all"]
    write(s, "baseline.json", dump(base), 17)
    ok = (base["weeks"] >= need["weeks_min"]
          and every["tickets"] >= need["tickets_min"])
    return ok, (f"{every['tickets']:,} tickets in {base['weeks']} "
                f"weeks, {every['mean']} min each")


def scope(s):
    """One dial setting per action, checked, written as policy."""
    try:
        policy = write_policy(read_json(s["in"] / "scope.json"),
                              s["out"] / "policy.json")
    except ValueError as e:
        return False, str(e)
    s["made"].append(("policy.json", 18))
    s["policy"] = policy
    dials = [a["setting"] for a in policy["actions"].values()]
    count = ", ".join(f"{dials.count(d)} {d}" for d in DIAL[::-1]
                      if d in dials)
    return True, f"{len(dials)} actions: {count}"


def agent_build(s):
    """Freeze prompt, model, tools, and policy into one bundle."""
    bundle = build(s["in"] / "prompt.txt")
    s["bundle"] = bundle
    write(s, "bundle.json", dump(bundle), 16)
    acts = s["policy"]["actions"]
    blocked = [t for t in bundle["tools"]
               if acts.get(t, {}).get("verdict", "BLOCK") == "BLOCK"]
    if blocked:
        return False, "policy blocks " + ", ".join(blocked)
    return True, (f"bundle {bundle['version']}, "
                  f"{len(bundle['tools'])} tools allowed")


def eval_gate(s):
    """Chapter 12's gate: the candidate prompt against the released."""
    folder = s["in"]
    why, text = quiet(gate, load_prompt(folder / "released.txt"),
                      load_prompt(folder / "prompt.txt"),
                      load_cases(folder / "evalset.jsonl"))
    text += "".join(f"  reason: {w}\n" for w in why)
    write(s, "eval-gate.txt",
          text + ("GATE FAIL\n" if why else "GATE PASS\n"), 12)
    change = [ln for ln in text.splitlines() if ln.startswith("change")]
    return not why, why[0] if why else change[0]


def security(s):
    """Attacks (Chapter 13), data map (19), obligations (22)."""
    worked, right = suite("all", links=strict_links)
    data, profile = s["eng"]["data"], s["eng"]["profile"]
    rows = scan(open_tables(s["in"] / "tables.json"),
                reaches=data["reaches"], masked=set(data["masked"]))
    flags = [r["column"] for r in rows if r["status"] == "FLAG"]
    table = obligations.load(obligations.TABLE)
    said = {r["id"]: obligations.status(r, profile)
            for r in table["rules"]}
    live = [r for r in table["rules"]
            if not said[r["id"]].startswith("other")]
    old = [r["id"] for r in live if obligations.stale(r)]
    bad = obligations.problems(table)
    s["data_rows"] = rows
    write(s, "review.json", dump({
        "attacks": len(ATTACKS), "attacks_worked": worked,
        "tasks": len(TASKS), "tasks_right": right,
        "data_map": rows, "data_flags": flags,
        "obligations_table": table["table"],
        "in_force": sorted(i for i, v in said.items()
                           if v == "in force"),
        "stale": old, "table_problems": bad}), 13)
    write(s, "obligations.txt",
          "\n".join(obligations.report(table, profile)) + "\n", 22)
    found = ([f"attack {a} worked" for a in worked]
             + [f"data flag {c}" for c in flags]
             + [f"stale rule {i}" for i in old] + bad)
    if right < len(TASKS):
        found.append(f"{right} of {len(TASKS)} normal tasks right")
    return not found, found[0] if found else (
        f"{len(worked)}/{len(ATTACKS)} attacks, {len(flags)} data "
        f"flags, {len(old)} stale rules")


def pilot(s):
    """Chapter 20's readout; refused if the plan changed after
    sign-off or a planned week is missing."""
    crit = read_json(s["in"] / "criteria.json")
    names = [w for w in crit["weeks"]
             if (s["in"] / f"{w}.csv").exists()]
    why = check_plan(crit, read_json(s["in"] / "signoff.json"), names)
    if why:
        return False, "refused: " + "; ".join(why)
    s["crit"], s["pilot"] = crit, readout(load_pilot(s["in"], names))
    write(s, "pilot.json", dump(s["pilot"]), 20)
    t, m = s["pilot"]["tickets"], s["pilot"]["minutes"]
    return True, (f"{t['pilot']} vs {t['control']} tickets, "
                  f"minutes lift {m['lift']:+.2f}")


def go_no_go(s):
    """The criteria signed in week zero decide: SCALE, FIX, or STOP."""
    verdict, note, scored = decide(s["crit"]["rules"], s["pilot"])
    write(s, "decision.json", dump({
        "verdict": verdict, "note": note,
        "rules": [{"name": r["name"], "kind": r["kind"],
                   "limit": r["limit"], "value": v, "pass": ok}
                  for r, v, ok in scored]}), 20)
    return verdict == "SCALE", f"{verdict}: {note}"


def business(s):
    """Chapter 23's model on this customer's baseline and pilot."""
    try:
        x = roi_inputs(s["in"] / "assumptions.json", s["base"],
                       s["pilot"], s["changes"])
    except ValueError as e:
        return False, str(e)
    month = break_even(months(x))
    limit = s["eng"]["business"]["break_even_max"]
    write(s, "business-case.md", case_page(x, s["eng"]["short"]), 23)
    ok = month is not None and month <= limit
    return ok, (f"break-even month {month} (limit {limit}), "
                f"{money(saving_per_task(x), 2)} a task")


def handover(s):
    """Fill the pack templates; Chapter 21's check must find nothing."""
    eng = s["eng"]
    owners = ["| Area | Owner | Backup |", "|---|---|---|"]
    owners += [f"| {a} | {o} | {b} |" for a, o, b in eng["owners"]]
    data = ["| Column | Kind | Zone | Status |", "|---|---|---|---|"]
    data += [f"| {r['column']} | {r['kind']} | {r['zone']} | "
             f"{r['status']} |" for r in s["data_rows"]]
    alerts = [f"- {r['name']}: {r['metric']} " + (
        f"over {r['over']}" if "over" in r else
        f"at {r['times']} times the usual") + f", {r['severity']}"
        for r in RULES]
    fill = {"customer": eng["customer"], "short": eng["short"],
            "as_of": eng["as_of"], "version": s["bundle"]["version"],
            "owners": "\n".join(owners), "data_map": "\n".join(data),
            "alerts": "\n".join(alerts),
            "rehearsal": eng["rehearsal"],
            **{k.lower(): v for k, v in eng["contacts"].items()}}
    pages = sorted((s["in"] / "pack").glob("*.md"))
    for page in pages:
        try:
            text = page.read_text().format_map(fill)
        except KeyError as e:
            return False, f"{page.name} needs {e}"
        write(s, f"handover/{page.name}", text, 21)
    problems = check_pack(s["out"] / "handover")
    return not problems, problems[0] if problems else (
        f"{len(pages)} files, 0 problems")


GATES = [("discovery", discovery), ("scope", scope),
         ("agent build", agent_build), ("eval gate", eval_gate),
         ("security", security), ("pilot", pilot),
         ("go/no-go", go_no_go), ("business case", business),
         ("handover", handover)]


def run(folder, out, changes=()):
    """Run the gates in order and return one (name, result, evidence)
    per gate. After the first FAIL, the rest are not run."""
    s = {"in": Path(folder), "out": Path(out), "made": [],
         "changes": list(changes),
         "eng": read_json(Path(folder) / "engagement.json")}
    s["out"].mkdir(parents=True, exist_ok=True)
    results = []
    for name, step in GATES:
        if results and results[-1][1] != "PASS":
            results.append((name, "-", "not run"))
            continue
        ok, evidence = step(s)
        results.append((name, "PASS" if ok else "FAIL", evidence))
    lines = [f"{n} {name:<15}{res:<6}{ev}"
             for n, (name, res, ev) in enumerate(results, 1)]
    write(s, "gates.txt", "\n".join(lines) + "\n", 24)
    files = [{"file": f, "chapter": ch, "sha256": hashlib.sha256(
        (s["out"] / f).read_bytes()).hexdigest()[:12]}
        for f, ch in s["made"]]
    write(s, "manifest.json", dump(files), 24)
    return results, lines, len(s["made"])


def main(argv):
    warn = "--warn" in argv
    args = [a for a in argv if a != "--warn"]
    changes = [a.split("=", 1) for a in args if "=" in a]
    paths = [a for a in args if "=" not in a]
    if len(paths) != 2:
        print("usage: python -m ch24.run_engagement FOLDER OUT "
              "[key=value ...] [--warn]")
        return 2
    eng = read_json(Path(paths[0]) / "engagement.json")
    print(f"Engagement: {eng['customer']}, as of {eng['as_of']}"
          + " (synthetic)" * bool(eng.get("synthetic")))
    for key, value in changes:
        print(f"changed: {key}={value}")
    results, lines, made = run(*paths, changes)
    print("\n".join(lines))
    print(f"Wrote {made} files to {paths[1]}")
    failed = [n for n, r in enumerate(results, 1) if r[1] == "FAIL"]
    if failed:
        print(f"ENGAGEMENT STOPPED at gate {failed[0]}"
              + " (warn only, exit 0)" * warn)
        return 0 if warn else 1
    print(f"ENGAGEMENT READY FOR HANDOVER: {len(results)} of "
          f"{len(results)} gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
