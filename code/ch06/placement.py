"""Map where each kept item sits in the packed request.

The study in this chapter's case found that a model used a fact best
at the start of its input, fairly well at the end, and worst in the
middle. This map packs the first run again and prints where each kept
item starts and ends, as a share of the request's characters, so you
can see whether the item that decides the answer sits at an edge.

    python -m ch06.placement
"""
from ch06.context_budget import INSTRUCTIONS, QUESTION, gather, pack
from ch06.memory_store import SHOPPER, TENANT, MemoryStore, seed


def spans(messages, parts):
    """(start %, end %, kind, name) per kept item, in reading order."""
    text = "".join(m["content"] for m in messages)
    items = ([("fixed", "instructions", INSTRUCTIONS)]
             + [(p["kind"], p["name"], p["text"]) for p in parts]
             + [("fixed", "question", QUESTION)])
    found, pos = [], 0
    for kind, name, chunk in items:
        start = text.find(chunk, pos)
        if start < 0:
            continue  # cut by the packer
        pos = start + len(chunk)
        found.append((100 * start // len(text), 100 * pos // len(text),
                      kind, name))
    return found


def main():
    store = MemoryStore()
    seed(store)
    parts = gather(store.recall(TENANT, SHOPPER))
    messages, _ = pack(QUESTION, parts)
    size = sum(len(m["content"]) for m in messages)
    print(f"request {size} characters, 0% = first, 100% = last")
    for start, end, kind, name in spans(messages, parts):
        print(f"  {start:>3}-{end:>3}%  {kind:<9} {name}")


if __name__ == "__main__":
    main()
