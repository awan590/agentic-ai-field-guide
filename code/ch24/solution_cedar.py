"""Solution to the Chapter 24 task: a second customer from the template.

make_folder() copies ch24/template, puts the exports of Cedar Hardware
Co. in place of Example Supply's, applies CHANGES, and signs the new
pilot criteria. main() builds the folder and runs the engagement on
it. Cedar Hardware Co. is invented, like every number in its files.

    python -m ch24.solution_cedar OUT     # writes OUT/inputs, OUT/run
"""
import json
import shutil
import sys
from pathlib import Path

from ch24 import run_engagement
from ch24.sign import sign

HERE = Path(__file__).parent
EXPORTS = ["tickets.csv", "week1.csv", "week2.csv", "tables.json"]
GROUP_MIN = 400                  # Cedar's desk sees about 470 a week
SIGNERS = ["sponsor: head of stores", "returns desk lead",
           "forward deployed engineer"]
CHANGES = {                      # file: top-level keys to replace
    "engagement.json": {
        "customer": "Cedar Hardware Co.", "short": "Cedar Hardware",
        "data": {"reaches": {"orders": "vendor", "loyalty": "store",
                             "products": "vendor", "tickets": "vendor"},
                 "masked": ["orders.email", "orders.delivery_note",
                            "tickets.body"]},
        "profile": {
            "agent": "returns-helper",
            "customer": "Cedar Hardware Co. (invented)",
            "job": "Drafts replies to shoppers about returns; a "
                   "person approves every refund.",
            "tier": "transparency", "regions": ["UK", "US", "US-CO"],
            "roles": {"provider": "IT manager",
                      "deployer": "returns desk lead",
                      "controller": "office manager",
                      "any": "head of stores"}},
        "owners": [
            ["answers to shoppers", "head of stores",
             "returns desk lead"],
            ["alerts and on-call", "IT manager", "IT technician"],
            ["rollback", "IT manager", "IT technician"],
            ["kill switch", "returns desk lead", "head of stores"],
            ["eval gate", "IT technician", "IT manager"],
            ["data map", "office manager", "IT manager"],
            ["adoption numbers", "returns desk lead",
             "head of stores"]],
        "contacts": {
            "L1": "the returns desk, in shop hours.",
            "L2": "the IT manager, in shop hours; the IT technician "
                  "covers weekends.",
            "L3": "the FDE until the end of hypercare in week 4, then "
                  "the IT manager."},
        "rehearsal": "Week 0 of go-live (synthetic): the IT manager "
                     "rolled back on staging and ran the smoke test."},
    "assumptions.json": {
        "note": "Invented numbers for the Cedar Hardware returns "
                "agent.",
        "desk": {"cost_per_hour": 32.0, "fte_hours_month": 160},
        "build": {"engagement_fee": 8000, "security_review": 1500,
                  "desk_training": 600},
        "run_month": {"hosting_and_tools": 150, "engineer_hours": 6,
                      "engineer_rate": 90}},
}


def make_folder(dest):
    """Copy the template to dest and make it Cedar's engagement."""
    dest = Path(dest)
    shutil.copytree(HERE / "template", dest, dirs_exist_ok=True)
    for name in EXPORTS:
        shutil.copyfile(HERE / "cedar" / name, dest / name)
    for name, keys in CHANGES.items():
        data = json.loads((dest / name).read_text())
        data.update(keys)
        (dest / name).write_text(json.dumps(data, indent=2) + "\n")
    crit = json.loads((dest / "criteria.json").read_text())
    for rule in crit["rules"]:
        if rule["name"] == "tickets per group":
            rule["limit"] = GROUP_MIN
    crit["pilot"] = "Cedar returns desk: the agent drafts, a person "\
        "approves refunds"
    (dest / "criteria.json").write_text(json.dumps(crit, indent=2)
                                        + "\n")
    sign(dest, SIGNERS)
    return dest


def main(argv):
    if len(argv) != 1:
        print("usage: python -m ch24.solution_cedar OUT")
        return 2
    out = Path(argv[0])
    make_folder(out / "inputs")
    return run_engagement.main([str(out / "inputs"), str(out / "run")])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
