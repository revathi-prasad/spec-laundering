"""Tests for the type-driven trivial generator (generation only).
Run: python3 -m unittest tests.test_trivial_gen"""

from __future__ import annotations

import unittest

from detector import trivial_gen as tg


class TestGenerate(unittest.TestCase):
    def test_int_output(self):
        out = tg.generate_trivials([("a", "int"), ("b", "int")], [("r", "int")])
        self.assertEqual(
            ["r := 0;", "r := 1;", "r := -1;", "r := a;", "r := b;"], out
        )

    def test_bool_output(self):
        self.assertEqual(
            ["r := true;", "r := false;"],
            tg.generate_trivials([], [("r", "bool")]),
        )

    def test_seq_output_no_overfit_lengths(self):
        out = tg.generate_trivials([("s", "seq<int>")], [("r", "seq<int>")])
        self.assertIn("r := [];", out)
        self.assertIn("r := s;", out)
        self.assertIn("r := seq(|s|, i => 0);", out)
        # the attack-specific doubled/tripled candidates are NOT generated
        self.assertNotIn("r := s + s;", out)
        self.assertNotIn("r := s + s + s;", out)
        self.assertNotIn("r := seq(2 * |s|, i => 0);", out)

    def test_result_wrapper_includes_failure(self):
        out = tg.generate_trivials(
            [("message", "seq<uint8>")], [("res", "Result<seq<int>>")]
        )
        self.assertIn("res := Failure;", out)
        self.assertIn("res := Success([]);", out)

    def test_multiple_outputs_empty(self):
        self.assertEqual(
            [], tg.generate_trivials([], [("a", "int"), ("b", "int")])
        )


if __name__ == "__main__":
    unittest.main()
