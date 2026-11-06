"""A minimal coding harness: plan, patch, run the tests, retry.

    python -m ch10.harness_min           # fix the failing refund test
    python -m ch10.harness_min bare      # the model alone, no harness
    python -m ch10.harness_min escape    # a patch aims outside

The harness copies sample_repo into a throwaway temp folder, the
sandbox, and writes nowhere else. A stand-in model reads the test
failure and proposes one exact text replacement per try, from a
script. The harness applies it, runs the tests with a time cap and
an empty environment, notes what failed, and stops at the skill's
try cap. Every step goes into a trace that a person can read.
When AGENTS.md sits beside it, that rules file rides in every prompt;
a rules file over the line cap is refused before the first try.
"""
import difflib
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE / "sample_repo"
SKILLS = HERE / "skills"
TIME_CAP = 30                    # seconds for one test run
RULES = HERE / "AGENTS.md"       # the rules file, read when present
RULES_CAP = 200                  # lines; a longer one is refused


class Blocked(Exception):
    """A hook refused a tool call."""


class StandInModel:
    """Proposes one patch per try, from a script. No network."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []           # what the harness showed it, per try

    def propose(self, failure, notes, rules=""):
        self.seen.append((failure, list(notes), rules))
        k = len(self.seen) - 1
        return self.script[k] if k < len(self.script) else None


def load_skill(name):
    """Read skills/<name>/SKILL.md: settings, then tagged steps."""
    _, head, body = (SKILLS / name / "SKILL.md").read_text().split(
        "---\n", 2)
    meta = dict(x.split(": ", 1) for x in head.splitlines())
    steps = [x.split("] ", 1) for x in body.splitlines()
             if x[:1].isdigit()]
    return {"name": meta["name"], "files": meta["files"].split(", "),
            "tests": meta["tests"].split(", "), "cap": int(meta["cap"]),
            "steps": [(t.split("[")[1], s) for t, s in steps]}


def load_rules(path=RULES):
    """Read the rules file for the prompt; refuse a long one."""
    if not path.exists():
        return ""
    text = path.read_text()
    n = len(text.splitlines())
    if n > RULES_CAP:
        raise ValueError(f"{path.name}: {n} lines, over the "
                         f"{RULES_CAP}-line cap; cut it first")
    return text


# every hook takes (box, skill, name), so HOOKS can call them alike
def inside_sandbox(box, skill, name):
    """Hook: refuse an edit whose path leaves the sandbox."""
    if not (box / name).resolve().is_relative_to(box.resolve()):
        raise Blocked(f"{name}: outside the sandbox")


def listed_file(box, skill, name):
    """Hook: refuse an edit to a file the skill does not list."""
    if name not in skill["files"]:
        raise Blocked(f"{name}: not a file the skill lists")


HOOKS = [inside_sandbox, listed_file]     # run before every edit


def run_tests(box, tests, cap=TIME_CAP):
    """Tool: run the listed tests in the sandbox, with a time cap."""
    cmd = [sys.executable, "-B", "-E", "-s", "-m", "unittest", *tests]
    try:
        done = subprocess.run(cmd, cwd=box, env={}, timeout=cap,
                              capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return False, f"STOPPED at the {cap} s time cap"
    lines = done.stderr.splitlines()
    # keep "FAIL: test_name" from each failing test's line
    fails = [" ".join(x.split()[:2]) for x in lines
             if x.startswith(("FAIL:", "ERROR:"))]
    return done.returncode == 0, "\n".join(lines[-1:] + fails)


def edit(box, skill, patch):
    """Tool: one exact text replacement, after every hook agrees."""
    for hook in HOOKS:
        hook(box, skill, patch["file"])
    path = box / patch["file"]
    text = path.read_text()
    if text.count(patch["old"]) != 1:
        raise Blocked(f"{patch['file']}: old text not found once")
    path.write_text(text.replace(patch["old"], patch["new"]))
    return text


def fix(skill, model, repo=REPO, cap=TIME_CAP, rules=""):
    """Plan, patch, run, check; retry up to the skill's try cap."""
    trace, notes = [], []
    with tempfile.TemporaryDirectory() as tmp:
        box = Path(tmp) / "repo"            # the sandbox folder
        shutil.copytree(repo, box,
                        ignore=shutil.ignore_patterns("__pycache__"))
        trace.append(("sandbox", f"throwaway copy of {repo.name}"))
        # each listed file as it was, for the final diff
        start = {f: (box / f).read_text() for f in skill["files"]}
        ok, out = run_tests(box, skill["tests"], cap)
        trace.append(("test", out))

        # notes hold one line per try, so len(notes) counts tries
        while not ok and len(notes) < skill["cap"]:
            patch = model.propose(out, notes, rules)
            if patch is None:
                break
            trace.append(("plan", patch["plan"]))
            try:
                before = edit(box, skill, patch)
            except Blocked as why:
                trace.append(("blocked", str(why)))
                notes.append(f"{patch['plan']}: blocked")
                continue
            trace.append(("edit", patch["file"]))
            ok, out = run_tests(box, skill["tests"], cap)
            trace.append(("test", out))
            if not ok:
                # put the file back before the next try
                (box / patch["file"]).write_text(before)
                trace.append(("revert", patch["file"]))
                notes.append(f"{patch['plan']}: {out.splitlines()[0]}")

        if ok:
            trace.append(("diff", diff(start, box)))
        else:
            trace.append(("handoff", "\n".join(notes) or "no patch"))
    return ok, trace


def diff(start, box):
    """The change, as a unified diff for a person to approve."""
    out = []
    for name, old in start.items():
        new = (box / name).read_text()
        out += difflib.unified_diff(old.splitlines(), new.splitlines(),
                                    f"a/{name}", f"b/{name}", n=1,
                                    lineterm="")
    return "\n".join(out)


def fingerprint(folder):
    """One hash over every file, to prove the original is untouched."""
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()


FEE_OFF = {"plan": "drop the restocking fee", "file": "refunds.py",
           "old": "RESTOCK_PERCENT = 10", "new": "RESTOCK_PERCENT = 0"}
DAMAGE_FIRST = {"plan": "skip the fee when the item is damaged",
                "file": "refunds.py", "old": "    if opened:",
                "new": "    if opened and not damaged:"}
ESCAPE = dict(FEE_OFF, plan="patch the file one folder up",
              file="../refunds.py")
SCRIPTS = {"fix": [FEE_OFF, DAMAGE_FIRST],
           "escape": [ESCAPE, DAMAGE_FIRST]}


def show(trace):
    """Print the trace: one step per line, details indented."""
    for kind, text in trace:
        first, *rest = text.splitlines() or [""]
        print(f"{kind:<8} {first}")
        for line in rest:
            print(f"{'':<8} {line}")


def main(argv):
    mode = argv[0] if argv else "fix"
    skill = load_skill("refund_fix")
    if mode == "bare":
        patch = StandInModel(SCRIPTS["fix"]).propose("", [])
        print(f"plan:  {patch['plan']}")
        print(f"patch: {patch['file']}: {patch['old']!r} -> "
              f"{patch['new']!r}")
        print("tests: never run")
        return
    rules = load_rules(RULES)
    n = len(rules.splitlines())
    print(f"rules: {RULES.name} ({n} lines)" if rules
          else "rules: none")
    before = fingerprint(REPO)
    ok, trace = fix(skill, StandInModel(SCRIPTS[mode]), rules=rules)
    show(trace)
    tries = sum(kind == "plan" for kind, _ in trace)
    print(f"result: {'fixed' if ok else 'not fixed'} after {tries} "
          f"tries (cap {skill['cap']})")
    same = fingerprint(REPO) == before
    print(f"original sample_repo unchanged: {'yes' if same else 'NO'}")


if __name__ == "__main__":
    main(sys.argv[1:])
