"""The task's solution: a questionnaire answer bank with evidence.

    python -m ch19.answer_bank

Each answer for the sample service links to a file or a test in this
repository. check() proves every link leads somewhere: a path must
name a file, and a test name (module.Class.method) must name a test
method in that test file. It reads files and runs nothing. Exit 1
when any answer has no link or a link that leads nowhere.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # the code folder

BANK = [
    ("DM-01", "Do you keep a record of the personal data you process?",
     "Yes. A script rebuilds the data map from the tables.",
     "test_ch19.DataMapTest.test_every_personal_column_is_listed"),
    ("DM-02", "Which tables does the agent read, and where do they go?",
     "Orders, tickets, and products reach the model vendor; "
     "payments stay in the store.",
     "ch19/tables.py"),
    ("DM-03", "Is personal data masked before it reaches the model?",
     "Yes for emails, phones, and cards. Names and addresses are "
     "sent, and the map lists them.",
     "test_ch19.DataMapTest.test_masked_column_leaves_clean"),
    ("AC-01", "Is each tool limited to the access its task needs?",
     "Yes. A policy table allows, blocks, or asks per tool and role.",
     "test_ch13.PolicyTest.test_rules"),
    ("AC-02", "Can one tenant's data reach another tenant's session?",
     "No. Every memory read names both the tenant and the shopper.",
     "test_ch06.MemoryTest.test_tenants_do_not_share_a_shopper_id"),
    ("LG-01", "Do your logs hold prompt and reply text?",
     "Not by default. When switched on, the text is masked first.",
     "test_ch14.TracingTest.test_content_is_off_by_default"),
    ("RT-01", "Is each kind of record kept for a fixed period?",
     "Yes: 30 days for content, 90 for traces, 365 for evals, and "
     "730 for incidents.",
     "test_ch19.RetentionTest.test_rules_by_age"),
    ("RT-02", "Can you erase one shopper's data on request?",
     "Yes. Their records leave the kept set unless a hold applies.",
     "test_ch19.RetentionTest.test_forget_request_drops_one_shopper"),
    ("OP-01", "Can a person stop the agent at once?",
     "Yes. A kill switch stops the next tool call.",
     "test_ch15.BudgetTest.test_kill_switch_stops_the_next_tool_call"),
]


def exists(link):
    """True when link names a file, or a test method in a test file."""
    if "/" in link:
        return (ROOT / link).is_file()
    parts = link.split(".")
    path = ROOT / "tests" / f"{parts[0]}.py"
    if len(parts) != 3 or not path.is_file():
        return False
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.ClassDef) and node.name == parts[1]:
            return any(isinstance(f, ast.FunctionDef) and
                       f.name == parts[2] for f in node.body)
    return False


def check(bank):
    """Return one problem line per answer whose evidence is missing."""
    problems = []
    for qid, _question, _answer, link in bank:
        if not link:
            problems.append(f"{qid}: no link")
        elif not exists(link):
            problems.append(f"{qid}: {link} leads nowhere")
    return problems


def main():
    problems = check(BANK)
    bad = {p.split(":")[0] for p in problems}
    for qid, _question, _answer, link in BANK:
        print(f"{qid} {'NO' if qid in bad else 'ok'} {link}")
    print(f"{len(BANK)} answers: {len(BANK) - len(problems)} linked, "
          f"{len(problems)} missing")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
