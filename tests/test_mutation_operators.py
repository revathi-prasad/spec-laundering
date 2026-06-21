"""Tests for the expanded mutation operator set (generation only; kill score
needs Dafny). Run: python3 -m unittest tests.test_check_b_operators"""

from __future__ import annotations

import unittest

from detector import mutation as mut


def _muts(ensures):
    return mut.all_mutants(ensures)


def _clauses(muts):
    return [m.mutated_clause for m in muts if m.mutated_clause is not None]


class TestROR(unittest.TestCase):
    def test_equality_expands_to_three(self):
        muts = _muts(["r == a"])
        clauses = _clauses(muts)
        self.assertIn("r >= a", clauses)
        self.assertIn("r <= a", clauses)
        self.assertIn("r != a", clauses)

    def test_total_count_simple_equality(self):
        # drop(1) + ror(3) + negate(1); no aor/lcr/quant/const tokens
        self.assertEqual(5, len(_muts(["r == a"])))


class TestImplicationSafety(unittest.TestCase):
    def test_ror_does_not_touch_implication(self):
        clauses = _clauses(_muts(["x ==> y"]))
        # no ROR mutant; == inside ==> is out of scope
        self.assertNotIn("x >=> y", clauses)
        self.assertNotIn("x >= y", clauses)

    def test_lcr_rewrites_implication(self):
        clauses = _clauses(_muts(["x ==> y"]))
        self.assertIn("x <==> y", clauses)


class TestAOR(unittest.TestCase):
    def test_arithmetic_mutated(self):
        clauses = _clauses(_muts(["|r| == 2 * |s|"]))
        self.assertIn("|r| == 2 + |s|", clauses)
        self.assertIn("|r| == 2 / |s|", clauses)


class TestLCRAndConst(unittest.TestCase):
    def test_connector_swap(self):
        clauses = _clauses(_muts(["a && b"]))
        self.assertIn("a || b", clauses)

    def test_const_swap(self):
        clauses = _clauses(_muts(["r == s[0] || true"]))
        self.assertIn("r == s[0] || false", clauses)


class TestOperatorNameUniqueness(unittest.TestCase):
    def test_names_unique_within_clause(self):
        # two == occurrences must yield distinct operator keys (equiv_filter dedup)
        muts = _muts(["p == q || r == s"])
        names = [m.operator for m in muts]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
