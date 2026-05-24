// Attack 3: narrow-quantifier-domain.
//
// The range of a universal quantifier is tightened so the body constraint
// holds over a proper subset of its original domain.
//
//   forall i in D.  P(i)    ->    forall i in D'. P(i),  with D' subset of D
//
// Demonstration on sortedness of a sequence:
//   original:   forall i, j.  0 <= i < j < |s|       ==> s[i] <= s[j]
//   laundered:  forall i, j.  0 <= i < j < |s| / 2   ==> s[i] <= s[j]
//   backdoor:   sequence with sorted first half and descending second half

predicate SortedFully(s: seq<int>)
{
  forall i, j :: 0 <= i < j < |s| ==> s[i] <= s[j]
}

predicate SortedFirstHalfOnly(s: seq<int>)
{
  forall i, j :: 0 <= i < j < |s| / 2 ==> s[i] <= s[j]
}

method SortLaundered(input: seq<int>) returns (output: seq<int>)
  ensures |output| == |input|
  ensures SortedFirstHalfOnly(output)
{
  var n := |input|;
  var half := n / 2;
  output := seq(half, i => 0) + seq(n - half, i => n - half - i);
}
