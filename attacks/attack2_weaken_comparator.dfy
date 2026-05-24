// Attack 2: weaken-comparator (relational operator replacement).
//
// A binary relational operator is replaced with a strictly weaker one:
// ==  ->  >=, ==  ->  <=, etc. The admissible set grows from a singleton
// to a half-line; implementations hitting any point in the larger set verify.
//
// Demonstration on DoubleLength(s):
//   original:   |r| == 2 * |s|
//   laundered:  |r| >= 2 * |s|
//   backdoor:   r := s + s + s

method DoubleLengthOriginal(s: seq<int>) returns (r: seq<int>)
  ensures |r| == 2 * |s|
{
  r := s + s;
}

method DoubleLengthLaundered(s: seq<int>) returns (r: seq<int>)
  ensures |r| >= 2 * |s|
{
  r := s + s + s;
}
