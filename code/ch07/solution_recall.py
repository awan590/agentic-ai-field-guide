"""Hands-on solution: cut pages at their headings, then label them.

Each chunk is one "## " section with the page title and the heading
in front, so no rule is cut in half and a chunk about half-price
refunds still says it is about refunds. The table compares the
eval's starting point with the new chunks, on the same questions.

    python -m ch07.solution_recall
"""
from ch07.index import build_index, window_chunks
from ch07.pages import PAGES
from ch07.retrieval_eval import evaluate, show_misses


def chunk_sections(page_id, text):
    """One chunk per section: "Title. Heading. Body text..."."""
    title, chunks = "", []
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:]
        elif line.startswith("## "):
            chunks.append({"id": f"{page_id}#{len(chunks) + 1}",
                           "page": page_id,
                           "text": f"{title}. {line[3:]}."})
        elif chunks:
            chunks[-1]["text"] += " " + line
    return chunks


def section_chunks(pages=PAGES):
    return [c for page_id, text in pages.items()
            for c in chunk_sections(page_id, text)]


SETUPS = [
    ("before: keyword, 40-word windows", window_chunks, "keyword", 0),
    ("hybrid + rerank, 40-word windows", window_chunks, "hybrid", 20),
    ("keyword, sections with titles", section_chunks, "keyword", 0),
    ("after: hybrid + rerank, sections", section_chunks, "hybrid", 20),
]


def compare():
    """Evaluate every setup; return (label, result) pairs."""
    return [(label, evaluate(build_index(chunker()), mode, top))
            for label, chunker, mode, top in SETUPS]


def main():
    rows = compare()
    print(f"{'setup':<34} {'recall@5':>8} {'MRR':>6} {'words':>6}")
    for label, r in rows:
        print(f"{label:<34} {r['recall@5']:>8.3f} {r['mrr']:>6.3f} "
              f"{r['words']:>6.0f}")
    before, after = rows[0][1], rows[-1][1]
    points = round(100 * (after["recall@5"] - before["recall@5"]), 1)
    print(f"recall@5 change: {points:+.1f} points; words sent: "
          f"{before['words']:.0f} -> {after['words']:.0f}")
    print("misses after (answer not in the top 5):")
    show_misses(build_index(section_chunks()), after, "hybrid", 20)


if __name__ == "__main__":
    main()
