import math
import unittest

from ch02.stub_model import StandInModel
from ch07 import index as ix
from ch07 import retrieval_eval as ev
from ch07 import search_tool as st
from ch07 import solution_recall as sol
from ch07.pages import PAGES

RULE = "wear parts such as v-belts, seals, and hose are not covered"


def flat(text):
    return " ".join(text.lower().split())


class ChunkTest(unittest.TestCase):
    def test_windows_keep_every_word_in_order(self):
        chunks = ix.chunk_words("warranty", PAGES["warranty"], 40)
        self.assertTrue(all(len(c["text"].split()) <= 40
                            for c in chunks))
        self.assertEqual([c["id"] for c in chunks][:2],
                         ["warranty#1", "warranty#2"])
        joined = " ".join(c["text"] for c in chunks)
        self.assertEqual(joined.split(),
                         PAGES["warranty"].replace("#", " ").split())

    def test_a_window_can_cut_a_rule_in_half(self):
        windows = ix.chunk_words("warranty", PAGES["warranty"], 40)
        self.assertFalse(any(RULE in flat(c["text"]) for c in windows))
        sections = sol.chunk_sections("warranty", PAGES["warranty"])
        self.assertTrue(any(RULE in flat(c["text"]) for c in sections))

    def test_sections_carry_title_and_heading(self):
        first = sol.chunk_sections("refunds", PAGES["refunds"])[0]
        self.assertTrue(first["text"].startswith(
            "Refunds. When a refund is paid. Refunds are paid"))
        self.assertEqual(first["page"], "refunds")


class SearchTest(unittest.TestCase):
    index = ix.build_index(ix.window_chunks())

    def test_keyword_search_finds_an_exact_part_number(self):
        top = ix.search(self.index, "PG-016", 1, "keyword")[0]
        self.assertEqual(top["page"], "pg-016")

    def test_stand_in_vectors_are_unit_length_and_repeatable(self):
        vec = ix.embed("pressure gauges")
        self.assertEqual(vec, ix.embed("pressure gauges"))
        self.assertAlmostEqual(
            math.sqrt(sum(v * v for v in vec.values())), 1.0)

    def test_stand_in_vectors_match_word_forms_not_meaning(self):
        def sim(a, b):
            va, vb = ix.embed(a), ix.embed(b)
            return sum(w * vb.get(k, 0.0) for k, w in va.items())
        self.assertGreater(sim("gauge", "gauges"), 0.5)
        self.assertLess(sim("money back", "refund"), 0.1)

    def test_fusion_rewards_agreement(self):
        self.assertEqual(ix.fuse([0, 1, 2], [2, 0]), [0, 2, 1])

    def test_rerank_only_moves_the_top(self):
        ranking = list(range(30))
        moved = ix.rerank(self.index, "restocking fee", ranking, 20)
        self.assertEqual(sorted(moved[:20]), list(range(20)))
        self.assertEqual(moved[20:], list(range(20, 30)))


class EvalTest(unittest.TestCase):
    def test_every_label_points_at_real_text(self):
        self.assertEqual(len(ev.QUESTIONS), 40)
        for question, page, evidence in ev.QUESTIONS:
            with self.subTest(question=question):
                self.assertIn(evidence, flat(PAGES[page]))

    def test_first_hit_needs_the_page_and_the_words(self):
        results = [{"page": "refunds", "text": "Refunds are paid"},
                   {"page": "returns", "text": "within 30 days of"},
                   {"page": "returns", "text": "Within 30  days of"}]
        self.assertEqual(ev.first_hit(results, "returns",
                                      "within 30 days"), 2)
        self.assertEqual(ev.first_hit(results, "refunds",
                                      "within 30 days"), 0)

    def test_baseline_numbers_match_the_book(self):
        result = ev.evaluate(ix.build_index(ix.window_chunks()))
        ranks = result["ranks"]
        self.assertEqual(sum(1 <= r <= 5 for r in ranks), 34)
        self.assertEqual(sum(r == 1 for r in ranks), 21)
        self.assertAlmostEqual(
            result["mrr"], sum(1 / r for r in ranks if r) / 40)

    def test_trace_follows_the_grease_miss_to_its_fix(self):
        lines, ranks = ev.trace(ix.build_index(ix.window_chunks()), 3)
        self.assertIn('answer: returns#2 holds "opened tins of bearing'
                      ' grease"', lines)
        self.assertEqual(ranks["keyword"], 14)
        self.assertEqual(ranks["hybrid + rerank"], 2)


class SolutionTest(unittest.TestCase):
    def test_new_chunks_add_ten_points_without_more_words(self):
        rows = dict(sol.compare())
        before = rows["before: keyword, 40-word windows"]
        after = rows["after: hybrid + rerank, sections"]
        def hits(r):
            return sum(1 <= rank <= 5 for rank in r["ranks"])
        self.assertGreaterEqual(hits(after) - hits(before), 4)
        self.assertLessEqual(after["words"], before["words"])


class AgentTest(unittest.TestCase):
    def run_demo(self, name):
        model = StandInModel(st.DEMOS[name])
        return st.run_agent(model, st.AGENT_TOOLS, st.TASK)

    def test_search_tool_returns_ids_and_text(self):
        results = st.search_policy("restocking fee")["results"]
        self.assertEqual(len(results), 3)
        self.assertEqual(set(results[0]), {"id", "text"})

    def test_agent_cites_only_what_it_found(self):
        result = self.run_demo("agent")
        self.assertEqual(result["stop"], "done")
        check = st.check_citations(result)
        self.assertEqual(check["cited"], ["returns#3", "refunds#2"])
        self.assertTrue(check["ok"])

    def test_a_citation_never_retrieved_is_flagged(self):
        check = st.check_citations(self.run_demo("forged"))
        self.assertEqual(check["unknown"], ["returns#1"])
        self.assertFalse(check["ok"])

    def test_an_answer_without_citations_fails(self):
        result = {"answer": "Yes, you can.", "trace": []}
        self.assertFalse(st.check_citations(result)["ok"])


if __name__ == "__main__":
    unittest.main()
