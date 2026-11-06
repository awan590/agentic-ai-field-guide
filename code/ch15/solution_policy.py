"""The task's solution: policy answers come from retrieved text only.

    python -m ch15.solution_policy

A draft policy answer passes only if it cites chunks that the
Chapter 7 search returned for this question, and most of its word
stems appear in those chunks. Anything else is a handoff to a
person. The drafts below are scripted, as a stand-in model's are.
"""
from ch07.index import stems
from ch07.search_tool import CITE, search_policy
from ch15.budget_guard import to_person

SUPPORT = 0.8    # share of the draft's stems found in cited text


def guard_policy(question, draft):
    """Return the draft if retrieved text backs it, else a handoff."""
    hits = {h["id"]: h["text"]
            for h in search_policy(question)["results"]}
    cited = CITE.findall(draft)
    if not cited:
        return to_person(question, "policy answer cites no page")
    if any(c not in hits for c in cited):
        return to_person(question, "cites a page not retrieved")
    said = stems(CITE.sub(" ", draft))
    found = set().union(*(stems(hits[c]) for c in cited))
    share = len(said & found) / max(len(said), 1)
    if share < SUPPORT:
        return to_person(question, f"only {share:.0%} of it is in "
                                   "the pages")
    return {"answer": draft}


CASES = [
    ("Can I cancel an order that has not shipped?",
     "Yes. An order can be canceled free of charge while its status"
     " is processing [orders#1]."),
    ("Why am I logged out when I switch to my laptop?",
     "Example Supply accounts work on one device at a time as a"
     " core security feature."),
    ("Is there a one device limit on my account?",
     "Yes, one device per account is a core security feature"
     " [privacy#1]."),
]


if __name__ == "__main__":
    for question, draft in CASES:
        out = guard_policy(question, draft)
        print(f"Q: {question}")
        if "answer" in out:
            ids = ", ".join(CITE.findall(out["answer"]))
            print(f"   answer sent, citing {ids}")
        else:
            print(f"   handoff: {out['handoff'].reason}")
