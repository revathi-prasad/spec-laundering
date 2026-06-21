"""Unit tests for detector/coupling.py.

These exercise the *logic* of the coupling check without a Dafny install: the
pure helpers are tested directly, and run_coupling is tested with an injected
verifier (a mock encoding the known Dafny outcomes for the Max attack). End-to-end
runs against real Dafny are a separate, environment-dependent step.

Run:  python3 -m unittest tests.test_coupling
"""

from __future__ import annotations

import re
import tempfile
import types
import unittest
from pathlib import Path

from detector import coupling as coup

ATTACKS = Path(__file__).resolve().parent.parent / "attacks"


class TestInsertEnsures(unittest.TestCase):
    def test_inserts_when_method_has_no_ensures(self):
        src = "method M(s: seq<int>) returns (r: int)\n  requires |s| > 0\n{ r := 0; }\n"
        out = coup._insert_ensures(src, "M", "r == s[0]")
        self.assertIn("ensures r == s[0]", out)
        # ensures must sit before the body brace
        self.assertLess(out.index("ensures r == s[0]"), out.index("{ r := 0;"))


class TestIdentifiers(unittest.TestCase):
    def test_leading_identifiers_skip_field_access(self):
        idents = coup.extract_identifiers("res.Success? ==> |res.value| == Length(input.digestAlgorithm) as nat")
        self.assertIn("res", idents)
        self.assertIn("Length", idents)
        self.assertIn("input", idents)
        # field accesses are NOT leading identifiers
        self.assertNotIn("Success", idents)
        self.assertNotIn("value", idents)
        self.assertNotIn("digestAlgorithm", idents)

    def test_declared_names(self):
        src = (
            "function Length(a: int): nat {0}\n"
            "predicate SortedFully(s: seq<int>) {true}\n"
            "datatype Result<T> = Success(value: T) | Failure\n"
            "newtype uint8 = x: int | 0 <= x < 256\n"
        )
        names = coup.declared_names(src)
        self.assertEqual({"Length", "SortedFully", "Result", "uint8"}, names)


class TestNamespaceGuard(unittest.TestCase):
    def test_attack1_is_comparable(self):
        src = (ATTACKS / "attack1_drop_conjunct.dfy").read_text()
        inputs, outputs = coup.triv.extract_signature(src, "MaxLaundered")
        foreign = coup.foreign_identifiers(
            ["r >= a", "r >= b", "r == a || r == b"],
            [n for n, _ in inputs], [n for n, _ in outputs], src,
        )
        self.assertEqual([], foreign)

    def test_attack6_is_incomparable(self):
        # The AWS original_ensures references `input.digestAlgorithm`, but the
        # laundered method renamed the parameter to `algorithm`.
        src = (ATTACKS / "attack6_aws_digest_extern_boundary.dfy").read_text()
        inputs, outputs = coup.triv.extract_signature(src, "DigestLaundered")
        foreign = coup.foreign_identifiers(
            ["res.Success? ==> |res.value| == Length(input.digestAlgorithm) as nat"],
            [n for n, _ in inputs], [n for n, _ in outputs], src,
        )
        self.assertIn("input", foreign)


class TestRequiresExtraction(unittest.TestCase):
    def test_getfirst_precondition(self):
        src = (ATTACKS / "attack4_vacuous_disjunct.dfy").read_text()
        reqs = coup.extract_requires_for_method(src, "GetFirstLaundered")
        self.assertEqual(["|s| > 0"], reqs)

    def test_max_has_no_precondition(self):
        src = (ATTACKS / "attack1_drop_conjunct.dfy").read_text()
        self.assertEqual([], coup.extract_requires_for_method(src, "MaxLaundered"))


class TestStripProofScaffolding(unittest.TestCase):
    def test_attack5_removes_assume_lemma_and_call(self):
        src = (ATTACKS / "attack5_assumed_lemma.dfy").read_text()
        # precondition: the assume-lemma and its call are present
        self.assertIn("lemma AbsCorrect", src)
        self.assertIn("AbsCorrect(x, r);", src)
        self.assertIn("assume", src)

        stripped = coup.strip_proof_scaffolding(src)
        # the lemma declaration is gone
        self.assertNotIn("lemma AbsCorrect", stripped)
        # the call site is gone
        self.assertNotIn("AbsCorrect(x, r);", stripped)
        # no assume statements remain *in the code* (comments may still say "assume")
        from detector import axiom_scan as axi
        code_only = axi._strip_comments(stripped)
        self.assertNotIn("assume", code_only)
        # the actual computation survives
        self.assertIn("r := 0;", stripped)
        # the honest function AbsValue is untouched
        self.assertIn("function AbsValue", stripped)

    def test_lemmas_with_assume_detected(self):
        src = (ATTACKS / "attack5_assumed_lemma.dfy").read_text()
        self.assertIn("AbsCorrect", coup._lemmas_with_assume(src))


class TestClassify(unittest.TestCase):
    def test_honest(self):
        v, veff = coup.classify(D={"c3"}, V_proof=set(), V_semantic=set())
        self.assertEqual("honest", v)
        self.assertEqual(set(), veff)

    def test_spec_laundering(self):
        v, veff = coup.classify(D={"c3"}, V_proof={"c3"}, V_semantic={"c3"})
        self.assertEqual("spec_laundering", v)
        self.assertEqual({"c3"}, veff)

    def test_proof_laundering(self):
        # attack-5 shape: spec unchanged (D empty), assume hides the violation
        # under V_proof, stripping reveals it under V_semantic.
        v, veff = coup.classify(D=set(), V_proof=set(), V_semantic={"r == AbsValue(x)"})
        self.assertEqual("proof_laundering", v)

    def test_violation_outside_dropped_is_proof_laundering(self):
        v, _ = coup.classify(D={"c1"}, V_proof=set(), V_semantic={"c2"})
        self.assertEqual("proof_laundering", v)


class TestSurgicalScore(unittest.TestCase):
    def test_perfectly_surgical(self):
        self.assertEqual(1.0, coup.surgical_score({"c3"}, {"c3"}))

    def test_blunt_weakening_scores_low(self):
        # dropped three clauses, only one was needed -> blunt
        self.assertAlmostEqual(1 / 3, coup.surgical_score({"c1", "c2", "c3"}, {"c3"}))

    def test_none_when_no_drops(self):
        self.assertIsNone(coup.surgical_score(set(), {"c"}))


class TestRunCheckEMocked(unittest.TestCase):
    """run_coupling end-to-end with an injected verifier that encodes the known
    Dafny outcomes for Max(a,b)."""

    MAX_LAUNDERED = (
        "method MaxLaundered(a: int, b: int) returns (r: int)\n"
        "  ensures r >= a\n"
        "  ensures r >= b\n"
        "{\n"
        "  if a >= b { r := a + 1; } else { r := b + 1; }\n"
        "}\n"
    )
    STRONG = ["r >= a", "r >= b", "r == a || r == b"]

    def _mock(self, truth):
        """truth: clause -> (entailed_by_weak, satisfied_by_impl)."""

        def verify(src):
            is_probe = "lemma DropProbe" in src
            ens = re.findall(r"ensures\s+(.+?)\s*$", src, re.M)
            clause = ens[-1].strip()
            entailed, satisfied = truth[clause]
            return types.SimpleNamespace(success=(entailed if is_probe else satisfied))

        return verify

    def _write(self, body):
        f = tempfile.NamedTemporaryFile("w", suffix=".dfy", delete=False)
        f.write(body)
        f.close()
        return Path(f.name)

    def test_backdoor_is_spec_laundering(self):
        # backdoor returns max+1: satisfies the inequalities, breaks the equality
        truth = {
            "r >= a": (True, True),
            "r >= b": (True, True),
            "r == a || r == b": (False, False),
        }
        path = self._write(self.MAX_LAUNDERED)
        res = coup.run_coupling(path, "MaxLaundered", self.STRONG, _verify=self._mock(truth))
        self.assertEqual("spec_laundering", res.verdict)
        self.assertEqual(["r == a || r == b"], res.dropped_D)
        self.assertEqual(["r == a || r == b"], res.violated_V_proof)
        self.assertEqual(1.0, res.surgical_score)
        self.assertTrue(res.fires)

    def test_honest_impl_same_weak_spec_is_silent(self):
        # SAME weak spec, but an honest impl satisfies the dropped equality too
        truth = {
            "r >= a": (True, True),
            "r >= b": (True, True),
            "r == a || r == b": (False, True),  # dropped, but honest impl satisfies it
        }
        path = self._write(self.MAX_LAUNDERED)
        res = coup.run_coupling(path, "MaxLaundered", self.STRONG, _verify=self._mock(truth))
        self.assertEqual("honest", res.verdict)
        self.assertFalse(res.fires)

    def test_incomparable_routes_out(self):
        path = self._write(self.MAX_LAUNDERED)
        # a reference clause naming a parameter the method does not have
        res = coup.run_coupling(
            path, "MaxLaundered", ["q == a"], _verify=self._mock({}),
        )
        self.assertEqual("incomparable", res.verdict)
        self.assertIn("q", res.foreign_identifiers)


if __name__ == "__main__":
    unittest.main()
