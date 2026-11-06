"""Check a run's trace against the steps of a skill.

    python -m ch10.skill_check           # the refund_fix skill

A skill is a folder with a SKILL.md: a name and a description that
say when to use it, then numbered steps. Each step here carries a
tag in brackets, and CHECKS turns each tag into a check on the trace
the harness wrote. The check reads only the trace, so it works the
same on the log of any agent that writes one.
"""
import sys

from ch10.harness_min import (SCRIPTS, SKILLS, StandInModel, fix,
                              load_skill)


def kinds(trace):
    return [kind for kind, _ in trace]


def edits_tested(trace):
    """Every edit is followed at once by a test run."""
    k = kinds(trace) + ["end"]
    return all(k[i + 1] == "test" for i, x in enumerate(k)
               if x == "edit")


def one_edit_per_try(trace):
    """At most one edit between one plan and the next."""
    tries = "".join("p" if k == "plan" else "e" if k == "edit" else ""
                    for k in kinds(trace))
    return "ee" not in tries


# t is the trace, s the skill; kinds(t) lists each step's kind
CHECKS = {
    "sandbox": lambda t, s: kinds(t)[0] == "sandbox",
    "test-first": lambda t, s: kinds(t)[1] == "test",
    "one-edit": lambda t, s: one_edit_per_try(t),
    "test-after": lambda t, s: edits_tested(t),
    "cap": lambda t, s: kinds(t).count("plan") <= s["cap"],
    "approval": lambda t, s: (kinds(t)[-1] in ("diff", "handoff")
                              and "push" not in kinds(t)),
}


def check(skill, trace):
    """One (tag, passed) pair per step; an unknown tag fails."""
    return [(tag, tag in CHECKS and CHECKS[tag](trace, skill))
            for tag, _ in skill["steps"]]


def report(name, script):
    """Print the skill, run the harness with it, check each step."""
    print((SKILLS / name / "SKILL.md").read_text().rstrip())
    skill = load_skill(name)
    ok, trace = fix(skill, StandInModel(script))
    print(f"\nrun: {'tests pass' if ok else 'not fixed'}, "
          f"{kinds(trace).count('plan')} tries")
    for kind, text in trace:
        if kind == "blocked":
            print(f"hook blocked {text}")
    results = check(skill, trace)
    for tag, passed in results:
        print(f"{'PASS' if passed else 'FAIL'}  {tag}")
    return ok and all(p for _, p in results)


if __name__ == "__main__":
    sys.exit(0 if report("refund_fix", SCRIPTS["fix"]) else 1)
