"""Check a handover pack folder for its parts, owners, and links.

A handover pack is the set of Markdown files the customer's team runs
the agent from after the FDE leaves. The check needs no reader. It
looks for each required file and the words it must hold, an owner and
a backup for every area, relative links that resolve, and every
`python -m` command it names. Exit 1 if anything is missing.

    python -m ch21.handover_check ch21/sample_pack --warn
    python -m ch21.handover_check ch21/solution_pack
    python -m ch21.handover_check --replay --warn
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
CODE = HERE.parent
PARTS = [  # (part, file, text the file must hold)
    ("index", "README.md", ["## Contents"]),
    ("runbook", "runbook.md",
     ["## Daily checks", "## When something breaks", "## Kill switch"]),
    ("owners", "owners.md", ["| Area | Owner | Backup |"]),
    ("rollback", "rollback.md", ["## Steps", "## Last rehearsal"]),
    ("eval gate", "evals.md", ["## Gate command"]),
    ("alerts", "alerts.md", ["## Alert list", "## Who is paged"]),
    ("data map", "data-map.md", ["## What the agent reads"]),
    ("contacts", "contacts.md", ["## Escalation", "L1", "L2", "L3"]),
]
AREAS = ["answers to shoppers", "alerts and on-call", "rollback",
         "kill switch", "eval gate", "data map", "adoption numbers"]
OUTSIDE = re.compile(r"\b(agent|chatbot|bot|vendor|fde)\b", re.I)
EMPTY = ("", "-", "tbd", "none")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
MODULE = re.compile(r"python -m (ch\d\d)\.(\w+)")


def owner_rows(text):
    """(area, owner, backup) for each row of a three-column table."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] != "Area" and \
                not set(cells[0]) <= set("-: "):
            rows.append(tuple(cells))
    return rows


def owner_problems(rows):
    """Every area needs an owner at the customer and a backup."""
    found = {area.lower(): (owner, backup)
             for area, owner, backup in rows}
    problems = []
    for area in AREAS:
        if area not in found:
            problems.append(f"no row for {area}")
            continue
        owner, backup = found[area]
        if owner.lower() in EMPTY:
            problems.append(f"{area}: no owner ({owner or 'blank'})")
        elif OUTSIDE.search(owner):
            problems.append(f"{area}: outside owner {owner!r}")
        if backup.lower() in EMPTY:
            problems.append(f"{area}: no backup")
    return problems


def broken_links(text, folder):
    """Relative links in Markdown text that point at nothing."""
    bad = []
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not (folder / target.split("#")[0]).exists():
            bad.append(target)
    return bad


def missing_modules(text):
    """`python -m chNN.name` commands with no chNN/name.py file."""
    return [f"{ch}.{name}" for ch, name in MODULE.findall(text)
            if not (CODE / ch / f"{name}.py").is_file()]


def check_pack(folder):
    """Return the problems with a pack; empty means OK."""
    folder = Path(folder)
    problems = []
    for part, name, needs in PARTS:
        f = folder / name
        if not f.is_file():
            problems.append(f"{name}: file missing")
            continue
        text = f.read_text()
        problems += [f"{name}: missing {n!r}" for n in needs
                     if n not in text]
        if part == "owners":
            problems += [f"{name}: {p}"
                         for p in owner_problems(owner_rows(text))]
    for f in sorted(folder.glob("*.md")):
        text = f.read_text()
        problems += [f"{f.name}: broken link {t}"
                     for t in broken_links(text, folder)]
        problems += [f"{f.name}: no module {m}"
                     for m in missing_modules(text)]
    return problems


def replay():
    """The owner table with the airline's argument written into it."""
    text = (HERE / "solution_pack" / "owners.md").read_text()
    text = re.sub(r"^\| answers to shoppers \|.*$",
                  "| answers to shoppers | the chatbot | none |",
                  text, flags=re.M)
    return [f"owners.md: {p}" for p in owner_problems(owner_rows(text))]


def report(title, problems, parts=PARTS):
    print(title)
    if parts:
        print(f"{'part':11}{'file':14}result")
        for part, name, _ in parts:
            mine = [p for p in problems if p.startswith(name + ":")]
            result = f"{len(mine)} problem" + "s" * (len(mine) > 1)
            if not mine:
                result = "ok"
            elif mine[0].endswith("file missing"):
                result = "file missing"
            print(f"{part:11}{name:14}{result}")
    for p in problems:
        print(f"- {p}")
    if problems:
        print(f"HANDOVER INCOMPLETE: {len(problems)} problem"
              + "s" * (len(problems) > 1))
    else:
        print(f"HANDOVER OK: {len(parts)} parts, 0 problems")


def main(argv):
    warn = "--warn" in argv
    args = [a for a in argv if not a.startswith("--")]
    if "--replay" in argv:
        problems = replay()
        report("Replay (synthetic): the chatbot owns its answers",
               problems, parts=[])
    else:
        folder = args[0] if args else "ch21/sample_pack"
        problems = check_pack(folder)
        report(f"Handover pack: {folder}", problems)
    return 1 if problems and not warn else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
