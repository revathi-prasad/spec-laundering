// Attack 4: add-vacuous-disjunct.
//
// A constant-true subterm is appended via OR:  Q  ->  Q || true.
// By absorption (Q || true) reduces to true; the postcondition becomes
// vacuously satisfied by every type-correct implementation.
//
// Demonstration on GetFirst(s):
//   original:   r == s[0]
//   laundered:  r == s[0] || true
//   backdoor:   r := 0

method GetFirstOriginal(s: seq<int>) returns (r: int)
  requires |s| > 0
  ensures r == s[0]
{
  r := s[0];
}

method GetFirstLaundered(s: seq<int>) returns (r: int)
  requires |s| > 0
  ensures r == s[0] || true
{
  r := 0;
}
