"""Write a hash-chained audit trail for the agent's tool calls.

    python -m ch22.audit [tamper SEQ]

A start record names the agent, its release, the obligations table,
the tier, and the rules in force. Then each tool call from Chapter 13
gets a record: whose data (masked), which tool with which arguments,
what the policy decided and why, and who approved. Each record holds
the hash of the one before it, so a changed record breaks the chain
where the change is. The calls and the approver are synthetic.
"""
import hashlib
import json
import sys

from ch12.agent import PROMPT
from ch13.pii_filter import mask
from ch13.policy import CALLS, SESSION, check
from ch16.release import build
from ch22.obligations import PROFILE, TABLE, load, status

AGENT = "returns-helper"
APPROVER = "ops lead (synthetic)"
ZERO = "0" * 64
USAGE = "usage: python -m ch22.audit [tamper SEQ], SEQ from 1 to 6"


def digest(record):
    """Hash every field except the hash itself."""
    body = {k: v for k, v in record.items() if k != "hash"}
    raw = json.dumps(body, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def seal(record, prev):
    body = dict(record, prev=prev)
    return dict(body, hash=digest(body))


def trail():
    """Return the start record and one record per policy call."""
    table, profile = load(TABLE), load(PROFILE)
    base = {"agent": AGENT, "release": build(PROMPT)["version"],
            "table": table["table"], "subject": mask(SESSION["email"])}
    live = [r["id"] for r in table["rules"]
            if status(r, profile) == "in force"]
    out = [seal(dict(base, seq=0, at="2026-11-04T09:00:00Z",
                     kind="start", tier=profile["tier"],
                     in_force=live), ZERO)]
    for n, (name, args) in enumerate(CALLS, 1):
        verdict, why = check(SESSION, name, args)
        out.append(seal(dict(
            base, seq=n, at=f"2026-11-04T09:{n:02d}:00Z", kind="call",
            tool=name, args={k: mask(str(v)) for k, v in args.items()},
            verdict=verdict, why=why,
            approver=APPROVER if verdict == "ASK" else None),
            out[-1]["hash"]))
    return out


def verify(records):
    """Return the seq of the first record that breaks the chain."""
    prev = ZERO
    for rec in records:
        if rec["prev"] != prev or digest(rec) != rec["hash"]:
            return rec["seq"]
        prev = rec["hash"]
    return None


def answers(records):
    """Answer a regulator's first questions from the trail alone."""
    start, calls = records[0], records[1:]
    money = [f"{r['approver']}, seq {r['seq']}, {r['tool']}"
             for r in calls if r.get("approver")]
    refused = [str(r["seq"]) for r in calls if r["verdict"] == "BLOCK"]
    broken = verify(records)
    return [
        ("Which system acted?",
         f"{start['agent']}, release {start['release']}"),
        ("Whose data?", f"{start['subject']} (masked in every record)"),
        ("Who approved money?",
         "; ".join(money) or "no approval on file"),
        ("What was refused?",
         f"seq {', '.join(refused)}, each with why"),
        ("Which rules applied?", ", ".join(start["in_force"])),
        ("Was it changed?", "no; every hash matches its record"
         if broken is None else
         f"yes; the chain breaks at seq {broken}")]


def main(argv):
    records = trail()
    expect = None             # the seq where the chain should break
    if argv:
        if (len(argv) != 2 or argv[0] != "tamper"
                or not argv[1].isdigit()
                or not 1 <= int(argv[1]) < len(records)):
            print(USAGE)
            return 2
        rec = records[int(argv[1])]
        print(f"Changed seq {rec['seq']}: verdict "
              f"{rec.get('verdict')} to ALLOW, approver removed.")
        rec.update(verdict="ALLOW", approver=None)
        expect = rec["seq"]
    print(f"{'seq':>3}  time   {'tool':<18}{'verdict':<8}"
          f"{'approver':<22}hash")
    for r in records:
        print(f"{r['seq']:>3}  {r['at'][11:16]}  "
              f"{r.get('tool', 'start'):<18}"
              f"{r.get('verdict') or '-':<8}"
              f"{r.get('approver') or '-':<22}{r['hash'][:12]}")
    broken = verify(records)
    print(f"Chain verified: {len(records)} records, no break."
          if broken is None else
          f"Chain broken at seq {broken}: it no longer matches its "
          "hash.")
    print("")
    for question, answer in answers(records):
        print(f"{question:<21}{answer}")
    return 0 if broken == expect else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
