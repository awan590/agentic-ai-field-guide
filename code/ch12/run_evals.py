"""Score the agent on the eval set: code checks first, a rubric
second, a stand-in model judge last.

    python -m ch12.run_evals              # 60 cases, released prompt
    python -m ch12.run_evals FILE         # the same, another prompt
    python -m ch12.run_evals kinds        # failure traces by kind
    python -m ch12.run_evals trace E08    # steps, tools, and checks
    python -m ch12.run_evals judge        # judges vs 30 human labels
    python -m ch12.run_evals week         # a replayed week, no labels

Every case, label, thumb, and score here is synthetic.
"""
import json
import re
import sys
import textwrap
from collections import Counter
from pathlib import Path

from ch02.mini_agent import print_trace
from ch07.index import stems
from ch07.search_tool import check_citations
from ch12.agent import HERE, load_prompt, run_case


def load_cases(path=HERE / "evalset.jsonl"):
    lines = Path(path).read_text().splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def called(result, name):
    return any(e["event"] == "tool_call" and e["name"] == name
               for e in result["trace"])


def checks(case, result):
    """Code checks: each one is a plain yes or no."""
    text = (result["answer"] or "").lower()
    return {
        "rule": all(m.lower() in text for m in case["must"]),
        "no_wrong": not any(m.lower() in text
                            for m in case["must_not"]),
        "cited": check_citations(result)["ok"],
        "lookup": not case.get("order")
        or called(result, "get_order"),
        "stopped": result["stop"] == "done",
    }


def score(cases, rules, seed=0):
    """Pass means every check holds; partial is the share that do."""
    rows = []
    for case in cases:
        marks = checks(case, run_case(case, rules, seed))
        rows.append({"id": case["id"], "kind": case["kind"],
                     "pass": all(marks.values()),
                     "partial": sum(marks.values()) / len(marks),
                     "failed": [k for k, v in marks.items() if not v]})
    return rows


def by_kind(rows):
    table = {}
    for r in rows:
        t = table.setdefault(r["kind"], [0, 0, 0.0])
        t[0] += 1
        t[1] += r["pass"]
        t[2] += r["partial"]
    return table


def show_score(rows):
    print(f"{'kind':<15}{'cases':>6}{'pass':>6}{'partial':>9}")
    for kind, (n, ok, part) in by_kind(rows).items():
        print(f"{kind:<15}{n:>6}{ok:>6}{part / n:>9.2f}")
    ok = sum(r["pass"] for r in rows)
    part = sum(r["partial"] for r in rows) / len(rows)
    print(f"{'all':<15}{len(rows):>6}{ok:>6}{part:>9.2f}")
    failed = " ".join(r["id"] for r in rows if not r["pass"])
    print(textwrap.fill("failed: " + failed, 72,
                        subsequent_indent="        "))


POLITE = ["Is the answer helpful and polite?"]
RUBRIC = [
    "1. It states a rule from a help page.",
    "2. It never agrees with a wrong belief or promises a refund.",
    "3. It cites the help page chunk the rule came from.",
    "4. It ends with a next step the shopper can take.",
]
REFERENCE = "5. Its rule matches the reference answer."
WARM = ("happy to help", "you are right", "on its way")
COLD = ("sorry", "cannot")
CITED = re.compile(r"\[[a-z0-9-]+#\d+\]")


def judge(case, answer, prompt):
    """Stand-in model judge. Like the agent, it obeys its prompt
    lines word for word; a real judge reads them as text."""
    text = answer.lower()
    if prompt == POLITE:                  # a vibe check in code
        if any(w in text for w in WARM):
            return "pass"
        return "fail" if any(w in text for w in COLD) else "pass"
    marks = [bool(CITED.search(text)),
             not any(w in text for w in WARM[1:]),
             "next step:" in text]
    if REFERENCE in prompt:
        want = stems(" ".join(case["must"]))
        marks.append(sum(w in stems(text) for w in want)
                     >= 0.6 * len(want))
    return "pass" if all(marks) else "fail"


def agreement(pairs):
    """Raw agreement and Cohen's kappa for (judge, human) pairs."""
    n = len(pairs)
    same = sum(j == h for j, h in pairs) / n
    pj = sum(j == "pass" for j, _ in pairs) / n
    ph = sum(h == "pass" for _, h in pairs) / n
    chance = pj * ph + (1 - pj) * (1 - ph)
    kappa = (same - chance) / (1 - chance) if chance < 1 else 0.0
    fp = sum(j == "pass" and h == "fail" for j, h in pairs)
    ff = sum(j == "fail" and h == "pass" for j, h in pairs)
    return same, kappa, fp, ff


def load_labels(path=HERE / "labels.jsonl"):
    return load_cases(path)


JUDGES = {"vibe judge": POLITE, "rubric judge": RUBRIC,
          "rubric + reference": RUBRIC + [REFERENCE]}


def judges(labels):
    """Each scorer's verdicts on the labeled answers."""
    cases = {c["id"]: c for c in load_cases()}
    out = {name: [] for name in ["always pass", *JUDGES,
                                 "code checks"]}
    for lab in labels:
        case, human = cases[lab["case"]], lab["human"]
        out["always pass"].append(("pass", human))
        for name, prompt in JUDGES.items():
            out[name].append((judge(case, lab["answer"], prompt),
                              human))
        result = run_case(case, load_prompt(HERE / lab["prompt"]))
        ok = all(checks(case, result).values())
        out["code checks"].append(("pass" if ok else "fail", human))
    return out


def show_judges(labels):
    print(f"{len(labels)} answers, human pass "
          f"{sum(x['human'] == 'pass' for x in labels)}")
    print(f"{'scorer':<20}{'agree':>6}{'kappa':>7}"
          f"{'false pass':>12}{'false fail':>12}")
    for name, pairs in judges(labels).items():
        same, kappa, fp, ff = agreement(pairs)
        print(f"{name:<20}{same:>6.0%}{kappa:>7.2f}{fp:>12}{ff:>12}")


def flags(case, result):
    """Reference-free checks a live system can run on every reply."""
    text = (result["answer"] or "").lower()
    pages = [c.split("#")[0] for c in check_citations(result)["cited"]]
    found = {
        "uncited": not pages,
        "off-page": any(not p.isalpha() for p in pages),
        "agrees": "you are right" in text,
        "promise": "on its way" in text,
        "no lookup": bool(case.get("order"))
        and not called(result, "get_order"),
    }
    return [k for k, v in found.items() if v]


def thumb(answer):
    """Simulated shopper vote: people like hearing yes."""
    text = answer.lower()
    if "you are right" in text or "on its way" in text:
        return "up"
    if "not quite" in text or "approves every refund" in text:
        return "down"
    return None


def week(path=HERE / "week.jsonl"):
    cases = load_cases(path)
    print(f"{len(cases)} replayed messages, no reference answers")
    print(f"{'prompt':<22}{'up':>4}{'down':>6}{'flagged':>9}")
    for name in ("prompt.txt", "prompt_agreeable.txt"):
        rules, ups, downs, hit = load_prompt(HERE / name), 0, 0, []
        for case in cases:
            result = run_case(case, rules)
            vote = thumb(result["answer"])
            ups += vote == "up"
            downs += vote == "down"
            if flags(case, result):
                hit.append((case["id"], flags(case, result)))
        print(f"{name:<22}{ups:>4}{downs:>6}{len(hit):>9}")
        if name == "prompt.txt":
            shown = hit
    for cid, why in shown:
        print(f"  {cid} {', '.join(why)}")


def main(argv):
    cmd = argv[0] if argv else str(HERE / "prompt.txt")
    if cmd == "kinds":
        found = Counter(c["kind"] for c in load_cases()
                        if c["from"].startswith("T-"))
        for kind, n in found.most_common():
            print(f"{kind:<15}{n:>3}  {'#' * n}")
        print(f"{'traces':<15}{sum(found.values()):>3}")
    elif cmd == "trace":
        case = {c["id"]: c for c in load_cases()}[argv[1]]
        result = run_case(case, load_prompt())
        print_trace(result)
        print(textwrap.fill(result["answer"], 72, initial_indent="   ",
                            subsequent_indent="   "))
        for name, ok in checks(case, result).items():
            print(f"   check  {name:<9}{'yes' if ok else 'NO'}")
    elif cmd == "judge":
        show_judges(load_labels())
    elif cmd == "week":
        week()
    else:
        show_score(score(load_cases(), load_prompt(cmd)))


if __name__ == "__main__":
    main(sys.argv[1:])
