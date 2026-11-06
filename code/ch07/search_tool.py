"""Search as a tool: the Chapter 2 agent decides when to look.

    python -m ch07.search_tool           # search twice, then answer
    python -m ch07.search_tool forged    # cite a page never searched
    python -m ch07.search_tool one       # one search, whole message

The loop and get_order come from Chapter 2 unchanged. The model is
the scripted stand-in, so its queries are written in the script; a
real model writes its own. The citation check runs after the loop.
"""
import re
import sys

from ch02.mini_agent import TOOLS, print_trace, run_agent, tool
from ch02.stub_model import StandInModel
from ch07.index import build_index, search, window_chunks

INDEX = build_index(window_chunks())
CITE = re.compile(r"\[([a-z0-9-]+#\d+)\]")


def search_policy(query, k=3):
    """Top k chunks for the query: hybrid search, then rerank."""
    hits = search(INDEX, query, k, "hybrid", 20)
    return {"results": [{"id": c["id"], "text": c["text"]}
                        for c in hits]}


AGENT_TOOLS = dict(TOOLS, search_policy=tool(
    search_policy,
    "Search the store's help pages. Cite every rule you use by the"
    " id of its chunk, such as [refunds#2].",
    query={"type": "string", "description": "What to look for"}))


def check_citations(result):
    """Every cited id must come from a search made in this run."""
    seen = [r["id"] for e in result["trace"]
            if e["event"] == "tool_result"
            and e["name"] == "search_policy"
            for r in e["result"].get("results", [])]
    cited = CITE.findall(result["answer"] or "")
    unknown = [c for c in cited if c not in seen]
    return {"seen": seen, "cited": cited, "unknown": unknown,
            "ok": bool(cited) and not unknown}


def ask(query):
    return {"name": "search_policy", "args": {"query": query}}


TASK = ("A-1003 came with a cracked fitting. Do I pay to send it"
        " back, and do I get my shipping money back?")

DEMOS = {
    "agent": [
        {"content": "Check the order, then the postage rule.",
         "tool_calls": [{"name": "get_order",
                         "args": {"order_id": "A-1003"}},
                        ask("who pays return postage damaged")]},
        {"content": "returns#3 settles postage. Now shipping.",
         "tool_calls": [ask("is original shipping refunded")]},
        {"content": "The fitting arrived damaged, so the store pays"
                    " the return postage [returns#3]. Your original"
                    " shipping is refunded because the store made"
                    " the mistake [refunds#2]. The archived 2024"
                    " page does not apply."},
    ],
    "forged": [
        {"content": "Return postage is always refunded [returns#1]."},
    ],
}


def main(argv):
    demo = argv[0] if argv else "agent"
    if demo == "one":
        hits = search_policy(TASK)["results"]
        print("one search:", " ".join(h["id"] for h in hits))
        return
    script = DEMOS[demo]
    result = run_agent(StandInModel(script), AGENT_TOOLS, TASK)
    print_trace(result)
    check = check_citations(result)
    print("found:", " ".join(check["seen"]) or "nothing")
    print("cited:", " ".join(check["cited"]),
          "| not retrieved:", " ".join(check["unknown"]) or "none",
          "| ok" if check["ok"] else "| FAIL")


if __name__ == "__main__":
    main(sys.argv[1:])
