// Hello-world: absolute value with a real specification.
//
// `ensures` clauses are postconditions Dafny proves symbolically against
// the implementation. If the implementation cannot satisfy every `ensures`,
// the file fails verification — no compile output, no binary.

method Abs(x: int) returns (result: int)
  ensures result >= 0
  ensures result == x || result == -x
{
  if x < 0 {
    result := -x;
  } else {
    result := x;
  }
}

// A caller. Dafny proves the assertion from Abs's postconditions alone —
// it does not re-inspect Abs's body. That is the whole point of a spec.
method Main() {
  var a := Abs(-7);
  assert a == 7;
}
