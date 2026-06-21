"""Tests for weakening_gen, dataset labeling/schema, and the seed problem bank.
Run: python3 -m unittest tests.test_dataset"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from detector import dataset as ds
from detector import weakening_gen as wg

ROOT = Path(__file__).resolve().parent.parent


class TestWeakeningGen(unittest.TestCase):
    MAX = ["r >= a", "r >= b", "r == a || r == b"]

    def test_drop_clause_reproduces_attack1_weakening(self):
        cands = wg.propose_weakenings(self.MAX)
        self.assertIn(["r >= a", "r >= b"], cands)

    def test_vacuous_disjunct_present(self):
        cands = wg.propose_weakenings(["r == s[0]"])
        self.assertIn(["(r == s[0]) || true"], cands)

    def test_comparator_weakening(self):
        cands = wg.propose_weakenings(["|r| == 2 * |s|"])
        self.assertIn(["|r| >= 2 * |s|"], cands)

    def test_excludes_original_and_dedups(self):
        cands = wg.propose_weakenings(self.MAX)
        self.assertNotIn(self.MAX, cands)
        self.assertEqual(len(cands), len({tuple(c) for c in cands}))


class TestLabeling(unittest.TestCase):
    def test_three_outcomes(self):
        self.assertEqual("invalid", ds.classify_label(False, True))
        self.assertEqual("honest_correct", ds.classify_label(True, True))
        self.assertEqual("verified_but_wrong", ds.classify_label(True, False))

    def test_finalize_sets_label(self):
        r = ds.Record(
            "max_of_two", "A", "generated", ["r == a"], ["r >= a"], "r := a+1;",
            verifies=True, behaviorally_correct=False,
        ).finalize()
        self.assertEqual("verified_but_wrong", r.label)


class TestValidateRecord(unittest.TestCase):
    def test_good_record(self):
        d = dict(problem_id="p", condition="A", source="generated",
                 strong_spec=["x"], generated_spec=["y"], generated_impl="z;")
        self.assertEqual([], ds.validate_record(d))

    def test_missing_and_bad_condition(self):
        errs = ds.validate_record(dict(condition="BOGUS"))
        self.assertIn("bad:condition", errs)
        self.assertIn("missing:problem_id", errs)


class TestProblemBank(unittest.TestCase):
    def test_loads_and_each_problem_well_formed(self):
        bank = json.loads((ROOT / "data" / "problem_bank.json").read_text())
        self.assertTrue(bank["problems"])
        for p in bank["problems"]:
            for k in ("problem_id", "strong_spec", "reference_impl", "signature"):
                self.assertIn(k, p)
            # weakenings exist for every seed problem's strong spec
            self.assertTrue(wg.propose_weakenings(p["strong_spec"]))


if __name__ == "__main__":
    unittest.main()
