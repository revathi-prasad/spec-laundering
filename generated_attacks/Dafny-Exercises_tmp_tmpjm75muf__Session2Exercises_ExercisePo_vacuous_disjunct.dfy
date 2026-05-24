predicate positive(s:seq<int>)
{forall u::0<=u<|s| ==> s[u]>=0}


method mpositive(v:array<int>) returns (b:bool)
ensures (b==positive(v[0..v.Length])) || true
{
  b := true;
}

method mpositive3(v:array<int>) returns (b:bool)
ensures b==positive(v[0..v.Length])
{
    var i:=0; b:=true;
    while(i<v.Length && b)
        decreases v.Length - i 
        invariant 0 <= i <= v.Length
        invariant b==positive(v[0..i])
        invariant !b ==> !positive(v[0..v.Length])
    {
        b:=v[i]>=0;
        i:=i+1;
    }
}

method mpositive4(v:array<int>) returns (b:bool)
ensures b==positive(v[0..v.Length])
{
    var i:=0; b:=true;
    while(i<v.Length && b)
        decreases v.Length - i 
        invariant 0 <= i <= v.Length
        invariant b==positive(v[0..i])
        invariant !b ==> !positive(v[0..v.Length])
    {
        b:=v[i]>=0;
        i:=i+1;
    }
    
}

method mpositivertl(v:array<int>) returns (b:bool)
ensures b==positive(v[0..v.Length])
{
    var i:=v.Length-1;
    while(i>=0 && v[i]>=0)
        decreases i
        invariant -1 <= i < v.Length
        invariant positive(v[i+1..])
    {
        i:=i-1;
    }
    b:= i==-1;
}



