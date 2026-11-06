"""Search the Example Supply help pages three ways.

    python -m ch07.index "warranty on a pressure gauge?"

keyword  BM25 over whole words, the classic search-engine score
vector   cosine over stand-in vectors (see embed below)
hybrid   both rankings merged by reciprocal rank fusion
A stand-in reranker can then re-sort the top hybrid results.
Standard library only; nothing leaves the laptop.
"""
import math
import re
import sys
import zlib
from collections import Counter

from ch07.pages import PAGES

STOP = set("""a an and any are as at be by can do does for from get
has have how i if in is it its me my of on or should so that the
them then there this to up was what when where which who will with
you your""".split())


def words(text):
    """Lowercase words; part numbers such as HC-038 stay whole."""
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())


def terms(text):
    return [w for w in words(text) if w not in STOP]


def chunk_words(page_id, text, size=40):
    """Cut one page into windows of `size` words, headings and all."""
    body = text.replace("#", " ").split()
    return [{"id": f"{page_id}#{n}", "page": page_id,
             "text": " ".join(body[i:i + size])}
            for n, i in enumerate(range(0, len(body), size), 1)]


def window_chunks(size=40, pages=PAGES):
    return [c for page_id, text in pages.items()
            for c in chunk_words(page_id, text, size)]


def embed(text):
    """Stand-in vector: counts of hashed letter triples, unit length.

    A real embedding model places "money back" near "refund" because
    it learned what words mean. This stand-in only sees spelling, so
    it matches word forms (gauge, gauges) and nothing more.
    """
    vec = Counter()
    for word in terms(text):
        word = f"<{word}>"
        for i in range(len(word) - 2):
            vec[zlib.crc32(word[i:i + 3].encode()) % 1024] += 1
    size = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / size for k, v in vec.items()}


def stems(text):
    """A crude stem: the first four letters of each word."""
    return {w[:4] for w in terms(text)}


def build_index(chunks):
    """Count what BM25 needs and make one vector per chunk."""
    tf = [Counter(terms(c["text"])) for c in chunks]
    lengths = [sum(counts.values()) for counts in tf]
    stem_sets = [stems(c["text"]) for c in chunks]
    return {"chunks": chunks, "tf": tf, "len": lengths,
            "df": Counter(t for counts in tf for t in counts),
            "avg": sum(lengths) / len(lengths),
            "vec": [embed(c["text"]) for c in chunks],
            "stems": stem_sets,
            "sdf": Counter(s for found in stem_sets for s in found)}


def bm25(index, query, k1=1.5, b=0.75):
    """Score every chunk: rare query words count most, repeats less."""
    n, scores = len(index["chunks"]), []
    for tf, length in zip(index["tf"], index["len"]):
        score = 0.0
        for t in set(terms(query)):
            if t in tf:
                df = index["df"][t]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                norm = k1 * (1 - b + b * length / index["avg"])
                score += idf * tf[t] * (k1 + 1) / (tf[t] + norm)
        scores.append(score)
    return scores


def cosine(index, query):
    q = embed(query)
    return [sum(w * v.get(k, 0.0) for k, w in q.items())
            for v in index["vec"]]


def ranked(scores):
    """Chunk positions with a score above zero, best first."""
    return sorted((i for i, s in enumerate(scores) if s > 0),
                  key=lambda i: -scores[i])


def fuse(*rankings, k=60):
    """Reciprocal rank fusion: each list adds 1 / (k + rank)."""
    score = Counter()
    for ranking in rankings:
        for rank, i in enumerate(ranking, 1):
            score[i] += 1 / (k + rank)
    return sorted(score, key=lambda i: (-score[i], i))


def rerank(index, query, ranking, top=20):
    """Stand-in reranker: re-sort the top results by coverage.

    A real reranker is a model that reads the question and each
    chunk together. This stand-in asks one question it would ask:
    how much of the question, weighted by rarity, does a chunk hold?
    """
    n, want = len(index["chunks"]), stems(query)
    weight = {s: math.log(1 + n / (1 + index["sdf"][s])) for s in want}
    head = sorted(ranking[:top], key=lambda i: -sum(
        weight[s] for s in want & index["stems"][i]))
    return head + ranking[top:]


def search(index, query, k=5, mode="hybrid", rerank_top=0):
    """Return the top k chunks for the query, best first."""
    if mode == "keyword":
        ranking = ranked(bm25(index, query))
    elif mode == "vector":
        ranking = ranked(cosine(index, query))
    else:
        ranking = fuse(ranked(bm25(index, query)),
                       ranked(cosine(index, query)))
    if rerank_top:
        ranking = rerank(index, query, ranking, rerank_top)
    return [index["chunks"][i] for i in ranking[:k]]


def main(argv):
    query = " ".join(argv) or "warranty on a pressure gauge?"
    index = build_index(window_chunks())
    print(f"query: {query}")
    for mode, top in [("keyword", 0), ("vector", 0), ("hybrid", 0),
                      ("hybrid", 20)]:
        print(mode + (" + rerank" if top else ""))
        for c in search(index, query, 4, mode, top):
            text = c["text"]
            if len(text) > 57:  # cut at a space, not inside a word
                text = text[:58].rsplit(" ", 1)[0]
            print(f"  {c['id']:<11} {text}")


if __name__ == "__main__":
    main(sys.argv[1:])
