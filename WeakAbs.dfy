// Spec laundering, in twelve lines.
//
// The postcondition is WEAK: it asserts only that the result is non-negative.
// The clause `result == x || result == -x` — the part that pins the result
// to the actual absolute value — has been dropped.
//
// A trivially wrong implementation (`return 0`) now passes verification,
// because it does satisfy the weakened spec.
//
// `dafny verify WeakAbs.dfy` will print "verification successful".
// The "verified" stamp now means nothing — this is exactly the failure
// mode our detector is built to catch.

method WeakAbs(x: int) returns (result: int)
  ensures result >= 0
{
  result := 0;
}
