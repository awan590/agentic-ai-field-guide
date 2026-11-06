"""Pack one request into a fixed token budget and print what was cut.

The window (the most tokens one model call can take) holds a fixed
part that is never cut: the instructions, the tool specs, the
shopper's question, and room for the reply. Everything else competes
for what is left. The packer ranks those items, keeps them in rank
order until one does not fit, then cuts that item and every item
ranked below it. Token counts use the stand-in model's rough rule
from Chapter 2. The help pages and the chat are synthetic.

    python -m ch06.context_budget          # a 500-token window
    python -m ch06.context_budget 400      # a smaller window
"""
import sys

from ch02.mini_agent import TOOLS, tool_specs
from ch02.stub_model import estimate_tokens
from ch05.data import REFUND_POLICY
from ch06.memory_store import SHOPPER, TENANT, MemoryStore, seed

WINDOW, REPLY = 500, 120
INSTRUCTIONS = "\n".join([
    "You answer shoppers for Example Supply Co.",
    "Use only this shopper's orders, refunds, and notes.",
    "Call a tool for live status; dated notes may be stale.",
    "Never promise a refund: a person approves each one.",
    "If you are not sure, say so and offer a person.",
])
DOCUMENTS = [  # best match for the question first
    ("refund-timing", "Approved refunds reach the card in 5 to 10 "
     "business days. The shopper gets an email when it is paid."),
    ("refund-policy", REFUND_POLICY),
    ("returns", "Return unused items within 30 days. Print the label "
     "from the order page. Damaged items need no return."),
    ("shipping", "Orders ship in one to two business days. Tracking "
     "is emailed once the carrier scans the box."),
]
HISTORY = [
    ("user", "Two of the hose clamps I got arrived bent."),
    ("assistant", "Sorry about that. Which order was it?"),
    ("user", "A-1001. I asked for a refund a few days ago."),
    ("assistant", "I see refund request R-A-1001 for $15.90, "
     "pending review."),
]
QUESTION = "Has my refund been paid yet, and will you email me?"


def item(kind, name, text, role="system"):
    return {"kind": kind, "name": name, "role": role, "text": text,
            "tokens": estimate_tokens(text)}


def gather(notes, documents=DOCUMENTS, history=HISTORY):
    """Every item that competes for space, in reading order."""
    return (
        [item("memory", f"{n['written']} {n['kind']}",
              f"Note from {n['written']}: {n['text']}") for n in notes]
        + [item("document", name, f"Help page {name}: {text}")
           for name, text in documents]
        + [item("turn", f"turn {n}", text, role)
           for n, (role, text) in enumerate(history, 1)])


def rank(parts, recent=2):
    """Most needed first; the packer cuts from the bottom up."""
    notes = [p for p in parts if p["kind"] == "memory"]
    docs = [p for p in parts if p["kind"] == "document"]
    turns = [p for p in parts if p["kind"] == "turn"]
    older, last = turns[:-recent], turns[-recent:]
    return last[::-1] + notes + docs[:1] + older[::-1] + docs[1:]


def layout(question, parts, keep):
    """Rules and notes first, pages next, then turns, question last."""
    kept = [p for p in parts if p["name"] in keep]
    system = [INSTRUCTIONS] + [p["text"] for p in kept
                               if p["role"] == "system"]
    turns = [{"role": p["role"], "content": p["text"]}
             for p in kept if p["role"] != "system"]
    return ([{"role": "system", "content": "\n\n".join(system)}]
            + turns + [{"role": "user", "content": question}])


def pack(question, parts, window=WINDOW, reply=REPLY):
    """Return the messages and a kept-or-cut line for every item."""
    specs = tool_specs(TOOLS)

    def fits(keep):
        messages = layout(question, parts, keep)
        return estimate_tokens(messages, specs) + reply <= window

    keep, full, report = set(), False, []
    if not fits(keep):
        raise ValueError(f"a {window}-token window cannot hold the "
                         "instructions, tools, question, and reply")
    for p in rank(parts):
        full = full or not fits(keep | {p["name"]})
        if not full:
            keep.add(p["name"])
        report.append(("cut" if full else "kept", p))
    return layout(question, parts, keep), report


def show(messages, report, window=WINDOW, reply=REPLY):
    used = estimate_tokens(messages, tool_specs(TOOLS))
    print(f"window {window} = input {used} + reply {reply}"
          f" + unused {window - used - reply}")
    print(f"  fixed instructions {estimate_tokens(INSTRUCTIONS)},"
          f" tools {estimate_tokens(tool_specs(TOOLS))},"
          f" question {estimate_tokens(QUESTION)}")
    for verdict, p in report:
        print(f"  {verdict:<5} {p['kind']:<9} {p['name']:<21}"
              f" {p['tokens']:>3}")
    cut = [p["tokens"] for verdict, p in report if verdict == "cut"]
    print(f"cut {len(cut)} items, {sum(cut)} tokens")
    print("order: " + ", ".join(m["role"] for m in messages))


def main(argv):
    window = int(argv[0]) if argv else WINDOW
    store = MemoryStore()
    seed(store)
    parts = gather(store.recall(TENANT, SHOPPER))
    messages, report = pack(QUESTION, parts, window)
    show(messages, report, window)


if __name__ == "__main__":
    main(sys.argv[1:])
