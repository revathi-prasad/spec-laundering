// Attack 1: drop-conjunct.
//
// One top-level conjunct is removed from the postcondition. Implementations
// that violated the dropped clause but satisfied the remainder now verify.
//
// Demonstration on Max(a, b):
//   original:   r >= a  AND  r >= b  AND  (r == a OR r == b)
//   laundered:  r >= a  AND  r >= b
//   backdoor:   r := max(a, b) + 1

method MaxOriginal(a: int, b: int) returns (r: int)
  ensures r >= a
  ensures r >= b
  ensures r == a || r == b
{
  if a >= b { r := a; } else { r := b; }
}

method MaxLaundered(a: int, b: int) returns (r: int)
  ensures r >= a
  ensures r >= b
{
  if a >= b { r := a + 1; } else { r := b + 1; }
}
