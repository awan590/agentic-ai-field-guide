"""Write the obligations sheet for the sample agent in two regions.

    python -m ch22.solution_sheet [check FILE]

The sheet lists the rules that apply on the as-of date, each with
its owner, the date it applies, its status, and its source; then the
rows that would join if counsel rules the agent high risk; then the
questions to take to counsel. With check, a saved sheet is tested
against the table: every row, the regions, the not-legal-advice
line, the questions, and the sign-off must be there.
"""
import sys

from ch22.obligations import PROFILE, TABLE, TODAY, load, status

REGIONS = ("EU", "US-CO")
LEGAL = "A working checklist to bring to counsel, not legal advice."
QUESTIONS = (
    "Is the agent high risk under the AI Act, or transparency only?",
    "Is a refund a consequential decision under SB 26-189?",
    "Who is the provider and who is the deployer under the contract?")
ASKED = "Open questions for counsel:"
SIGN = "Sign-off: governance lead ___, counsel ___, date ___"
HEAD = ["| Rule | Owner | Applies | Status | Source |",
        "|---|---|---|---|---|"]


def applying(table, profile, regions, on, tier=None):
    """Return (rule, status) for each rule that applies in regions."""
    who = dict(profile, regions=list(regions),
               tier=tier or profile["tier"])
    said = [(r, status(r, who, on)) for r in table["rules"]]
    return [(r, s) for r, s in said if not s.startswith("other")]


def joining(table, profile, regions, on):
    """Return the rows that join if the agent is ruled high risk."""
    now = {r["id"] for r, _ in applying(table, profile, regions, on)}
    return [(r, s) for r, s in applying(table, profile, regions, on,
                                        "high") if r["id"] not in now]


def row(rule, said, profile):
    owner = profile["roles"].get(rule["role"], "no owner")
    return (f"| {rule['id']} | {owner} | {rule['applies']} | {said} | "
            + ", ".join(rule["source"]) + " |")


def sheet(table, profile, regions=REGIONS, on=TODAY):
    """Return the sheet as Markdown lines."""
    rows = applying(table, profile, regions, on)
    extra = joining(table, profile, regions, on)
    out = [f"# Obligations sheet: {profile['agent']} in "
           + " and ".join(regions), "",
           f"Table {table['table']}, read {table['read_on']}; "
           f"as of {on}.",
           f"Tier on file: {profile['tier']} (synthetic profile).",
           LEGAL, ""]
    out += HEAD + [row(r, s, profile) for r, s in rows]
    out += ["", "Duties:"]
    out += [f"- {r['id']}: {r['duty']}" for r, _ in rows]
    out += ["", "If counsel rules the agent high risk, these rows "
            "join:", ""] + HEAD + [row(r, s, profile) for r, s in extra]
    out += ["", ASKED] + [f"- {q}" for q in QUESTIONS]
    notes = {}
    for r, _ in rows + extra:
        if r.get("check"):
            notes.setdefault(r["check"], []).append(r["id"])
    for text, ids in notes.items():
        out += [f"- {', '.join(ids)}:", f"  {text}"]
    return out + ["", SIGN]


def check(text, table, profile, regions=REGIONS, on=TODAY):
    """Return the problems that keep a saved sheet from passing."""
    lines = text.splitlines() or [""]
    found = []
    for r, _ in (applying(table, profile, regions, on)
                 + joining(table, profile, regions, on)):
        if not any(r["id"] in ln and r["applies"] in ln
                   and r["source"][0] in ln for ln in lines):
            found.append(f"{r['id']}: no line with its date and source")
    if not all(g in lines[0] for g in regions):
        found.append("title does not name " + " and ".join(regions))
    found += [f"missing {need!r}" for need in (LEGAL, ASKED, SIGN[:9])
              if need not in text]
    return found


def main(argv):
    table, profile = load(TABLE), load(PROFILE)
    if argv[:1] == ["check"]:
        with open(argv[1]) as fh:
            found = check(fh.read(), table, profile)
        print("\n".join(found) or "OK")
        return 1 if found else 0
    print("\n".join(sheet(table, profile)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
