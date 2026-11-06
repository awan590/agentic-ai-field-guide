"""Measure retrieval: recall at k and MRR on 40 labeled questions.

    python -m ch07.retrieval_eval            # keyword, with misses
    python -m ch07.retrieval_eval compare    # four ways to search
    python -m ch07.retrieval_eval sweep      # four chunk sizes
    python -m ch07.retrieval_eval ranks      # what moved past rank 5
    python -m ch07.retrieval_eval trace 3    # why question 3 ranks low

Each question carries the page that answers it and a few words of
the answer. A retrieved chunk is a hit when it comes from that page
and holds those words. Questions and pages are invented; 40 is a
small set, so one question moves recall by 2.5 points.
"""
import sys

from ch07.index import build_index, search, stems, terms, window_chunks

QUESTIONS = [
    ("how long do i have to send stuff back", "returns",
     "within 30 days of delivery"),
    ("I posted my return without an RMA, what happens?", "returns",
     "without an rma number go back"),
    ("can i return grease if the tin is open", "returns",
     "opened tins of bearing grease"),
    ("who pays to post a return?", "returns", "pays return postage"),
    ("the clamp is too small, can I swap it for a bigger one?",
     "returns", "to swap a size"),
    ("when do I get my money back", "refunds",
     "within 5 business days"),
    ("will you refund the shipping I paid?", "refunds",
     "original shipping charges"),
    ("is there a restocking fee?", "refunds",
     "15 percent restocking fee"),
    ("I opened the bearing kit, can I still get a refund", "refunds",
     "refunded at half price"),
    ("how long does delivery take", "shipping",
     "3 to 5 business days"),
    ("order by what time for next day?", "shipping", "before 2 pm"),
    ("do you have free shipping", "shipping",
     "free on orders over $150"),
    ("who pays import duty on orders abroad?", "shipping",
     "paid by the recipient"),
    ("the box arrived crushed, how long do I have to report it?",
     "damaged", "within 48 hours of delivery"),
    ("you sent the wrong part", "damaged", "ships by express"),
    ("tracking hasnt moved in a week", "damaged",
     "not changed for 7 days"),
    ("one item is missing from my box", "damaged", "split shipment"),
    ("warranty on a pressure gauge?", "warranty",
     "pressure gauges carry 24"),
    ("my v-belt wore out, is that covered?", "warranty",
     "wear parts such as v-belts"),
    ("how do i make a warranty claim", "warranty",
     "a photo of the fault"),
    ("can I cancel, it already shipped", "orders",
     "once it has shipped it cannot be canceled"),
    ("I put the wrong adress on my order", "orders",
     "address can be changed"),
    ("can i add another item to my order", "orders",
     "cannot be added to an order"),
    ("can I pay by bank transfer", "payments",
     "bank transfer orders ship after"),
    ("how do I get net 30 terms", "payments", "net 30 terms"),
    ("where can I download an invoice", "payments",
     "pdf invoice on the orders page"),
    ("my card got declined, is my order gone?", "payments",
     "waits 48 hours for a new payment"),
    ("can spray grease ship by air", "safety", "cannot travel by air"),
    ("where do I find the SDS for GR-400?", "safety",
     "safety data sheet"),
    ("do you ship to PO boxes", "safety", "cannot ship to po boxes"),
    ("discount if I buy 200 clamps?", "bulk", "15 percent off"),
    ("how long is a quote valid", "bulk", "valid for 30 days"),
    ("can I get a free sample first", "bulk",
     "three free samples a month"),
    ("do you keep my card number", "privacy",
     "held by the payment provider"),
    ("delete my account please", "privacy", "delete your account"),
    ("stop sending me marketing emails", "privacy",
     "unsubscribe link"),
    ("how much grease in a BK-6204?", "care",
     "a third of its free space"),
    ("how tight should I do up a hose clamp", "care",
     "4 newton meters"),
    ("how many times do I wrap thread tape", "care",
     "three to four times"),
    ("when do you charge me for a back order", "stock",
     "charged when the item ships"),
]


def first_hit(results, page, evidence):
    """Rank (1 = top) of the first chunk holding the answer, else 0."""
    for rank, chunk in enumerate(results, 1):
        text = " ".join(chunk["text"].lower().split())
        if chunk["page"] == page and evidence in text:
            return rank
    return 0


def evaluate(index, mode="keyword", rerank_top=0):
    """Recall at 1 and 5, MRR over the top 10, and words sent."""
    ranks, words = [], 0
    for question, page, evidence in QUESTIONS:
        results = search(index, question, 10, mode, rerank_top)
        ranks.append(first_hit(results, page, evidence))
        words += sum(len(c["text"].split()) for c in results[:5])
    n = len(ranks)
    return {"recall@1": sum(r == 1 for r in ranks) / n,
            "recall@5": sum(1 <= r <= 5 for r in ranks) / n,
            "mrr": sum(1 / r for r in ranks if r) / n,
            "words": words / n, "ranks": ranks}


def show_misses(index, result, mode="keyword", rerank_top=0):
    """Print each question whose answer is outside the top 5."""
    for (question, page, _), rank in zip(QUESTIONS, result["ranks"]):
        if 1 <= rank <= 5:
            continue
        top = search(index, question, 1, mode, rerank_top)[0]["id"]
        where = f"rank {rank}" if rank else "not in top 10"
        print(f"  {question[:31]:<31} {page:<8} {where:<13} {top}")


def report(index):
    result = evaluate(index)
    print(f"{len(QUESTIONS)} questions, {len(index['chunks'])} chunks,"
          f" keyword search")
    print(f"recall@1 {result['recall@1']:.3f}   "
          f"recall@5 {result['recall@5']:.3f}   "
          f"MRR {result['mrr']:.3f}")
    print("misses (answer not in the top 5):")
    print(f"  {'question':<31} {'expected':<8} {'found at':<13}"
          " top hit")
    show_misses(index, result)


SEARCHES = [("keyword", "keyword", 0), ("vector", "vector", 0),
            ("hybrid", "hybrid", 0), ("hybrid + rerank", "hybrid", 20)]


def compare(index):
    print(f"{'search':<16} {'recall@1':>8} {'recall@5':>8} {'MRR':>6} "
          f"{'words':>6}")
    for label, mode, top in SEARCHES:
        r = evaluate(index, mode, top)
        print(f"{label:<16} {r['recall@1']:>8.3f} "
              f"{r['recall@5']:>8.3f} {r['mrr']:>6.3f} "
              f"{r['words']:>6.0f}")


def sweep(sizes=(20, 40, 80, 160)):
    """Recall at 5 and words sent for each chunk size, keyword."""
    print(f"{'chunk size':>10} {'chunks':>7} {'recall@5':>9} "
          f"{'words sent':>11}")
    for size in sizes:
        index = build_index(window_chunks(size))
        r = evaluate(index)
        print(f"{size:>10} {len(index['chunks']):>7} "
              f"{r['recall@5']:>9.3f} {r['words']:>11.0f}")


def ranks(index):
    """Recall at 3, 5, and 20, then the questions that cross rank 5
    between keyword search and hybrid search with the reranker."""
    found = {label: [first_hit(search(index, q, 20, mode, top), p, e)
                     for q, p, e in QUESTIONS]
             for label, mode, top in SEARCHES}
    print(f"{'search':<16} {'recall@3':>8} {'recall@5':>8} "
          f"{'recall@20':>9}")
    for label, got in found.items():
        print(f"{label:<16}" + "".join(
            f" {sum(1 <= r <= k for r in got) / len(got):>{w}.3f}"
            for k, w in [(3, 8), (5, 8), (20, 9)]))
    print("crossed rank 5 (- means not in the top 20):")
    print(f"  {'question':<31} {'keyword':>7} {'hybrid + rerank':>15}")
    pairs = zip(QUESTIONS, found["keyword"], found["hybrid + rerank"])
    for (question, _, _), old, new in pairs:
        if (1 <= old <= 5) != (1 <= new <= 5):
            print(f"  {question[:31]:<31} {old or '-':>7} "
                  f"{new or '-':>15}")


def trace(index, number=3):
    """Follow one question to the chunk that holds its answer: which
    query words and four-letter stems that chunk shares, how many
    chunks hold each word, and the chunk's rank four ways. Returns
    the lines to print and the ranks (0 means not found)."""
    question, page, evidence = QUESTIONS[number - 1]
    lines, ranks = [f"question {number}: {question}"], {}
    chunk = next((c for c in index["chunks"]
                  if first_hit([c], page, evidence)), None)
    if chunk is None:
        return lines + [f'no single chunk holds "{evidence}"'], ranks
    have, roots = set(terms(chunk["text"])), stems(chunk["text"])
    lines += [f'answer: {chunk["id"]} holds "{evidence}"',
              "  query word  chunks with it  word in chunk"
              "  stem in chunk"]
    for word in terms(question):
        lines.append(f"  {word:<10}  {index['df'][word]:>14}  "
                     f"{'yes' if word in have else 'no':<13}  "
                     f"{'yes' if word[:4] in roots else 'no'}")
    lines.append(f"  {'search':<16} {'rank':>4}  first chunk")
    for label, mode, top in SEARCHES:
        found = search(index, question, len(index["chunks"]), mode, top)
        ranks[label] = first_hit(found, page, evidence)
        start = " ".join(found[0]["text"].split()[:4])
        lines.append(f"  {label:<16} {ranks[label] or '-':>4}  "
                     f"{found[0]['id']:<11} {start}")
    return lines, ranks


def main(argv):
    arg = argv[0] if argv else "report"
    if arg == "sweep":
        sweep()
    elif arg == "trace":
        number = int(argv[1]) if len(argv) > 1 else 3
        lines, _ = trace(build_index(window_chunks()), number)
        print("\n".join(lines))
    else:
        index = build_index(window_chunks())
        {"compare": compare, "ranks": ranks}.get(arg, report)(index)


if __name__ == "__main__":
    main(sys.argv[1:])
