import io
import unittest
from contextlib import redirect_stdout

from ch01 import readiness_check as rc

ALL = {c.key for c in rc.CHECKS}


class ReadinessCheckTest(unittest.TestCase):
    def test_fourteen_checks_two_per_gap(self):
        self.assertEqual(len(rc.CHECKS), 14)
        gaps = [c.gap for c in rc.CHECKS]
        self.assertEqual(len(set(gaps)), 7)
        self.assertTrue(all(gaps.count(g) == 2 for g in set(gaps)))
        self.assertEqual(len(ALL), 14)

    def test_all_yes_has_no_gaps(self):
        passed, gaps = rc.score(ALL)
        self.assertEqual((passed, gaps), (14, []))
        self.assertEqual(rc.verdict(gaps), "ready for a go-live review")

    def test_unknown_counts_as_no_and_high_risk_first(self):
        passed, gaps = rc.score(set())
        self.assertEqual(passed, 0)
        risks = [c.risk for c in gaps]
        self.assertEqual(risks, sorted(risks, reverse=True))
        self.assertTrue(rc.verdict(gaps).startswith("stop"))

    def test_typo_in_a_key_is_an_error(self):
        with self.assertRaises(ValueError):
            rc.score({"real-data"})

    def test_samples(self):
        got = {n: rc.score(y)[0] for n, y in rc.SAMPLES.items()}
        self.assertEqual(list(got.values()), [1, 8, 12])

    def test_one_med_gap_means_pilot_only(self):
        _, gaps = rc.score(ALL - {"traces"})
        self.assertTrue(rc.verdict(gaps).startswith("pilot only"))

    def test_report_prints_top_three_gaps(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc.main(["real_data", "traces", "caps"])
        lines = buf.getvalue().splitlines()
        self.assertEqual(lines[0], "Your demo: 3/14 checks pass")
        highs = [ln for ln in lines if ln.startswith("  HIGH")]
        self.assertEqual(len(highs), 3)
        self.assertEqual(lines[-2], "  plus 8 more gaps")


if __name__ == "__main__":
    unittest.main()
