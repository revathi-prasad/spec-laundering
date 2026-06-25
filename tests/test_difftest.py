"""Tests for differential testing (harness building + input gen are pure;
the runner is mocked). Run: python3 -m unittest tests.test_difftest"""

from __future__ import annotations

import unittest

from detector import difftest as dt


class TestInputs(unittest.TestCase):
    def test_two_ints_cartesian(self):
        ins = dt.gen_inputs([("a", "int"), ("b", "int")])
        self.assertEqual("0, 0", ins[0])
        self.assertEqual(25, len(ins))

    def test_seq_inputs(self):
        self.assertEqual(dt._SEQ_POOL, dt.gen_inputs([("s", "seq<int>")]))

    def test_unsupported_type_empty(self):
        self.assertEqual([], dt.gen_inputs([("m", "map<int,int>")]))


class TestHarness(unittest.TestCase):
    def test_contains_parts(self):
        h = dt.build_harness(
            "method Max(a: int, b: int) returns (r: int)", [],
            "if a >= b { r := a; } else { r := b; }",
            "r := a + 1;", ["0, 0", "5, 2"],
        )
        self.assertIn("method Ref(a: int, b: int) returns (r: int)", h)
        self.assertIn("method Cand(a: int, b: int) returns (r: int)", h)
        self.assertIn("method Main()", h)
        self.assertIn("MISMATCH", h)
        self.assertIn("Ref(5, 2)", h)

    def test_requires_propagated(self):
        h = dt.build_harness(
            "method GetFirst(s: seq<int>) returns (r: int)", ["|s| > 0"],
            "r := s[0];", "r := 0;", ["[1, 2, 3]"],
        )
        self.assertIn("requires |s| > 0", h)


class TestDifferentialTest(unittest.TestCase):
    def test_wrong_when_mismatch(self):
        res = dt.differential_test(
            "method Max(a: int, b: int) returns (r: int)", [], "x", "y",
            _run=lambda src: (0, "MISMATCH\nMISMATCH\n"),
        )
        self.assertTrue(res)

    def test_correct_when_no_mismatch(self):
        res = dt.differential_test(
            "method Max(a: int, b: int) returns (r: int)", [], "x", "y",
            _run=lambda src: (0, ""),
        )
        self.assertFalse(res)

    def test_inconclusive_on_run_failure(self):
        res = dt.differential_test(
            "method Max(a: int, b: int) returns (r: int)", [], "x", "y",
            _run=lambda src: (1, ""),
        )
        self.assertIsNone(res)


class TestCounterexamples(unittest.TestCase):
    def test_regression_returns_lines(self):
        status, ex = dt.find_counterexamples(
            "method Max(a: int, b: int) returns (r: int)", [], "x", "y",
            _run=lambda src: (0, "MISMATCH in=(5, 2) ref=5 cand=3\n"),
        )
        self.assertEqual("regression", status)
        self.assertEqual(1, len(ex))

    def test_equivalent_empty(self):
        status, ex = dt.find_counterexamples(
            "method Max(a: int, b: int) returns (r: int)", [], "x", "y",
            _run=lambda src: (0, ""),
        )
        self.assertEqual("equivalent", status)
        self.assertEqual([], ex)

    def test_harness_prints_input_and_outputs(self):
        h = dt.build_harness(
            "method Max(a: int, b: int) returns (r: int)", [], "x", "y", ["5, 2"])
        self.assertIn("MISMATCH in=(5, 2)", h)
        self.assertIn('ref=", r, " cand=", c', h)


if __name__ == "__main__":
    unittest.main()
