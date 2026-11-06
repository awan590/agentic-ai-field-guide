"""Tests for Chapter 24: the whole engagement from one folder.

Every run writes into a temporary folder that is removed afterward.

Run from code/:  python -m unittest tests.test_ch24
"""
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ch21.handover_check import check_pack
from ch23.roi_model import inputs
from ch23.solution_case import page
from ch24 import run_engagement as eng
from ch24 import solution_cedar as cedar
from ch24 import sign as signoff

HERE = Path(eng.__file__).parent
TEMPLATE = HERE / "template"


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()) as out:
        code = fn(*args)
    return code, out.getvalue()


def edit_json(path, change):
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def results(rows):
    return [r[1] for r in rows]


class SampleEngagementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "out"
        cls.rows, cls.lines, cls.made = eng.run(TEMPLATE, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_gate_passes_in_order(self):
        self.assertEqual([r[0] for r in self.rows],
                         [name for name, _ in eng.GATES])
        self.assertEqual(results(self.rows), ["PASS"] * 9)

    def test_evidence_matches_the_earlier_chapters(self):
        ev = [r[2] for r in self.rows]
        self.assertEqual(ev[0],
                         "1,280 tickets in 2 weeks, 9.0 min each")
        self.assertEqual(ev[3], "change +4.0 cases, noise band 4.1")
        self.assertEqual(ev[4],
                         "0/25 attacks, 0 data flags, 0 stale rules")
        self.assertEqual(ev[5],
                         "639 vs 641 tickets, minutes lift -1.58")
        self.assertTrue(ev[7].startswith("break-even month 9 "))

    def test_manifest_lists_every_file_written(self):
        files = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(len(files) + 1, self.made)
        for f in files:
            self.assertTrue((self.out / f["file"]).is_file(), f)
        self.assertEqual((self.out / "gates.txt").read_text(),
                         "\n".join(self.lines) + "\n")

    def test_handover_pack_passes_chapter_21(self):
        self.assertEqual(check_pack(self.out / "handover"), [])
        owners = (self.out / "handover" / "owners.md").read_text()
        self.assertIn("| kill switch | returns desk lead |", owners)

    def test_business_case_is_chapter_23s_page(self):
        mine = (self.out / "business-case.md").read_text()
        theirs = page(inputs())
        self.assertEqual(
            mine.replace("this engagement's baseline and control group",
                         "ch17 baseline and the ch20 control group"),
            theirs)


class GateStopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "in"
        shutil.copytree(TEMPLATE, self.folder)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scope_above_its_ceiling_stops_at_gate_2(self):
        def auto_refund(scope):
            scope["actions"]["issue_refund"][0] = "AUTO"
        edit_json(self.folder / "scope.json", auto_refund)
        rows, _, _ = eng.run(self.folder, self.root / "out")
        self.assertEqual(results(rows), ["PASS", "FAIL"] + ["-"] * 7)
        self.assertIn("issue_refund: AUTO is above", rows[1][2])
        self.assertFalse((self.root / "out" / "policy.json").exists())

    def test_criteria_changed_after_signoff_is_refused(self):
        def easier(crit):
            crit["rules"][0]["limit"] = 100
        edit_json(self.folder / "criteria.json", easier)
        rows, _, _ = eng.run(self.folder, self.root / "out")
        self.assertEqual(results(rows)[5:], ["FAIL", "-", "-", "-"])
        self.assertEqual(rows[5][2], "refused: criteria changed after "
                         "the week 0 sign-off")

    def test_one_changed_assumption_stops_at_business_case(self):
        rows, _, _ = eng.run(self.folder, self.root / "out",
                             [("error_scale", "2")])
        self.assertEqual(results(rows)[7:], ["FAIL", "-"])
        self.assertTrue(rows[7][2].startswith("break-even month 21 "))

    def test_exit_codes(self):
        out = str(self.root / "out")
        self.assertEqual(quiet(eng.main, [])[0], 2)
        self.assertEqual(quiet(signoff.main, [out])[0], 2)
        self.assertEqual(quiet(eng.main, [str(self.folder), out,
                                          "error_scale=2"])[0], 1)
        code, text = quiet(eng.main, [str(self.folder), out,
                                      "error_scale=2", "--warn"])
        self.assertEqual(code, 0)
        self.assertIn("ENGAGEMENT STOPPED at gate 8", text)


class CedarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_solution_runs_every_gate(self):
        code, text = quiet(cedar.main, [str(self.root)])
        self.assertEqual(code, 0)
        self.assertEqual(text.count(" PASS "), 9)
        self.assertIn("ENGAGEMENT READY FOR HANDOVER", text)
        case = (self.root / "run" / "business-case.md").read_text()
        self.assertTrue(case.startswith(
            "# Business case: Cedar Hardware returns agent"))
        self.assertEqual(check_pack(self.root / "run" / "handover"), [])

    def test_template_alone_flags_cedars_free_text(self):
        folder = cedar.make_folder(self.root / "in")

        mine = json.loads((TEMPLATE / "engagement.json").read_text())

        def template_mask(e):
            e["data"]["masked"] = mine["data"]["masked"]
        edit_json(folder / "engagement.json", template_mask)
        rows, _, _ = eng.run(folder, self.root / "out")
        self.assertEqual(rows[4][1:],
                         ("FAIL", "data flag orders.delivery_note"))

    def test_template_group_limit_stops_cedar_at_gate_7(self):
        folder = cedar.make_folder(self.root / "in")

        def template_limit(crit):
            crit["rules"][0]["limit"] = 600
        edit_json(folder / "criteria.json", template_limit)
        signoff.sign(folder, cedar.SIGNERS)
        rows, _, _ = eng.run(folder, self.root / "out")
        self.assertEqual(rows[5][2],
                         "464 vs 476 tickets, minutes lift -1.72")
        self.assertEqual(rows[6][1:], (
            "FAIL", "STOP: must rule failed: tickets per group"))

    def test_nothing_is_written_beside_the_template(self):
        before = sorted(p.name for p in HERE.iterdir())
        cedar.make_folder(self.root / "in")
        self.assertEqual(sorted(p.name for p in HERE.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
