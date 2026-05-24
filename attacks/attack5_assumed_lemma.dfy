// Attack 5: assumed-lemma laundering.
//
// The method's postcondition is unchanged. A helper lemma claims the
// postcondition and discharges its proof obligation with `assume`. The
// method calls the lemma; Dafny propagates the lemma's `ensures` to the
// call site without re-verifying its body.
//
// The weakness lives in the lemma body, not in any `ensures` clause.
// Operator-level spec mutation (drop-conjunct, ROR, quantifier flip)
// inspects `ensures` clauses; lemma bodies are not mutated. The attack is
// invisible to spec-mutation testing as currently implemented in IronSpec
// (OSDI 2024) and MutDafny (arXiv:2511.15403).
//
// Dafny 4 emits a warning on bare `assume` lacking the `{:axiom}`
// annotation, recognizing the laundering risk. The warning is advisory:
// verification still succeeds, and `{:axiom}` suppresses the warning
// without changing the verification outcome.

function AbsValue(x: int): int
{
  if x < 0 then -x else x
}

method AbsHonest(x: int) returns (r: int)
  ensures r == AbsValue(x)
{
  if x < 0 { r := -x; } else { r := x; }
}

lemma AbsCorrect(x: int, r: int)
  ensures r == AbsValue(x)
{
  assume {:axiom} r == AbsValue(x);
}

method AbsLaundered(x: int) returns (r: int)
  ensures r == AbsValue(x)
{
  r := 0;
  AbsCorrect(x, r);
}
