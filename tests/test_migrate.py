"""Tests for the migration regression detector (runner mocked).
Run: python3 -m unittest tests.test_migrate"""

from __future__ import annotations

import unittest

from detector import migrate as mg

SRC = """
method Max(a: int, b: int) returns (r: int)
  ensures r >= a
{
  if a >= b { r := a; } else { r := b; }
}
"""


class TestExtractBody(unittest.TestCase):
    def test_pulls_body(self):
        body = mg.extract_method_body(SRC, "Max")
        self.assertIn("if a >= b", body)
        self.assertNotIn("ensures", body)

    def test_missing_method(self):
        self.assertIsNone(mg.extract_method_body(SRC, "Min"))


class TestCheckMigration(unittest.TestCase):
    def test_regression(self):
        rep = mg.check_migration(
            "method Max(a: int, b: int) returns (r: int)", [], "old", "new",
            _run=lambda src: (0, "MISMATCH in=(5, 2) ref=5 cand=3\n"))
        self.assertTrue(rep.regressed)
        self.assertEqual("Max", rep.method)
        self.assertEqual(1, len(rep.counterexamples))

    def test_equivalent(self):
        rep = mg.check_migration(
            "method Max(a: int, b: int) returns (r: int)", [], "old", "new",
            _run=lambda src: (0, ""))
        self.assertFalse(rep.regressed)
        self.assertEqual("equivalent", rep.status)

    def test_files_missing_body_inconclusive(self):
        rep = mg.check_migration_files(SRC, "method Foo() {}", "method Max(a: int, b: int) returns (r: int)",
                                       [], "Max", _run=lambda src: (0, ""))
        self.assertEqual("inconclusive", rep.status)


if __name__ == "__main__":
    unittest.main()
