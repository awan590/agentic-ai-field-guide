"""Block a release when the eval score drops past the noise band.

    python -m ch12.gate                        # released vs itself
    python -m ch12.gate FILE                   # a candidate prompt
    python -m ch12.gate FILE --add CASES       # with new cases too
    python -m ch12.gate FILE --warn            # report, never block

Both prompts run the same cases with five seeds. The noise band is
twice the spread of the released prompt's own scores, and at least
one case. Two kinds block on any loss at all. Exit code 1 means
FAIL, which is what makes a CI job red.
"""
import sys
from statistics import mean, stdev

from ch12.agent import HERE, PROMPT, load_prompt
from ch12.run_evals import load_cases, score

SEEDS = range(5)
BLOCKING = ("agrees-wrong", "refund-promise")


def runs(rules, cases):
    """Passes per seed, and passes per kind summed over seeds."""
    per_seed, per_kind = [], {}
    for seed in SEEDS:
        rows = score(cases, rules, seed)
        per_seed.append(sum(r["pass"] for r in rows))
        for r in rows:
            per_kind[r["kind"]] = per_kind.get(r["kind"], 0) + r["pass"]
    return per_seed, per_kind


def gate(base, cand, cases):
    """Return the list of reasons to block; empty means PASS."""
    b_seed, b_kind = runs(base, cases)
    c_seed, c_kind = runs(cand, cases)
    band = max(2 * stdev(b_seed), 1.0)
    change = mean(c_seed) - mean(b_seed)
    print(f"cases {len(cases)}, seeds {len(SEEDS)}")
    print(f"released   {b_seed}  mean {mean(b_seed):.1f}")
    print(f"candidate  {c_seed}  mean {mean(c_seed):.1f}")
    print(f"change {change:+.1f} cases, noise band {band:.1f}")
    why = []
    if -change > band:
        why.append(f"score fell {-change:.1f} cases, past the band")
    for kind in BLOCKING:
        print(f"  {kind:<15}{b_kind.get(kind, 0):>3} ->"
              f"{c_kind.get(kind, 0):>3}")
        if c_kind.get(kind, 0) < b_kind.get(kind, 0):
            why.append(f"{kind} lost a case (blocks on any loss)")
    return why


def main(argv):
    args = list(argv)
    warn = "--warn" in args
    if warn:
        args.remove("--warn")
    cases = load_cases()
    if "--add" in args:
        i = args.index("--add")
        cases += load_cases(args[i + 1])
        del args[i:i + 2]
    cand = load_prompt(args[0] if args else PROMPT)
    why = gate(load_prompt(HERE / "prompt.txt"), cand, cases)
    for w in why:
        print("  reason:", w)
    print("GATE FAIL" if why else "GATE PASS",
          *(["(warn only, exit 0)"] if warn and why else []))
    return 1 if why and not warn else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
