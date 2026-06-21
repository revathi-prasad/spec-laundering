"""Tests for severity threshold calibration.
Run: python3 -m unittest tests.test_calibration"""

from __future__ import annotations

import unittest

from detector import calibration as cal


class TestEvaluateThreshold(unittest.TestCase):
    def test_counts(self):
        scored = [(0.9, True), (0.1, False), (0.8, True), (0.2, False)]
        e = cal.evaluate_threshold(scored, 0.5)
        self.assertEqual((2, 0, 2, 0), (e.tp, e.fp, e.tn, e.fn))
        self.assertEqual(1.0, e.tpr)
        self.assertEqual(0.0, e.fpr)


class TestBestThreshold(unittest.TestCase):
    def test_separable(self):
        scored = [(0.8, True), (0.9, True), (1.0, True), (0.0, False), (0.1, False), (0.2, False)]
        e = cal.best_threshold(scored)
        self.assertEqual(1.0, e.tpr)
        self.assertEqual(0.0, e.fpr)
        self.assertEqual(1.0, e.youden_j)

    def test_overlap_not_perfect(self):
        scored = [(0.6, True), (0.4, True), (0.5, False), (0.3, False)]
        e = cal.best_threshold(scored)
        self.assertLess(e.youden_j, 1.0)


class TestROC(unittest.TestCase):
    def test_curve_spans_corners(self):
        scored = [(0.8, True), (0.2, False)]
        pts = cal.roc_curve(scored)
        self.assertIn((0.0, 0.0), pts)  # threshold above all
        self.assertIn((1.0, 1.0), pts)  # threshold below all
        self.assertIn((0.0, 1.0), pts)  # perfect separation point


if __name__ == "__main__":
    unittest.main()
