# Triage of cross-tool flag results on DafnyBench sample

Manual classification of the 8 DafnyBench programs flagged by either the
composed detector or the IronSpec ASC reproduction in
`results_cross_tool_eval.txt`.

Classification scheme:
- `discovered_loose` : the flag corresponds to a genuinely weak honest
  specification (analogous to the IronSpec OSDI 2024 paper's reported
  real-world spec bugs). The flag is a true positive on a non-adversarial
  corpus.
- `true_FP` : the spec is tight and the flag is a detector defect.
- `bug_in_reproduction` : the flag is caused by a defect in this
  repository's reproduction, not in the original tool's algorithm.

## Per-file classification

### Flagged by ASC reproduction only

**`703FinalProject_tmp_tmpr_10rn4z_DP-GD.dfy` :: `DPGD_GradientPerturbation`**
- `discovered_loose`. The method declares no `ensures` clause. Its outputs
  (privacy parameter and loss) are completely unconstrained.

**`703FinalProject_tmp_tmpr_10rn4z_gaussian.dfy` :: `gaussian`**
- `discovered_loose`. The method declares no `ensures` clause. The output
  array is completely unconstrained.

**`Correctness_tmp_tmpwqvg5q_4_Sorting_Tangent.dfy` :: `Tangent`**
- `bug_in_reproduction`. The spec contains multi-line `ensures` clauses
  of the form `ensures !found ==> forall i, j :: ...`. The reproduction's
  ensures extractor in `detector/check_d_mutation_kill.py` captures only
  the first line, missing the body of the `forall`. The captured
  fragment `ensures !found ==>` contains no input parameter name, so
  ASC flags HIGH spuriously. The original IronSpec implementation operates
  on Dafny's resolved AST and does not have this bug.

### Flagged by composed detector only

**`CVS-Projto1_tmp_tmpb1o0bu8z_proj1_proj1.dfy` :: `query`**
- `true_FP`. Single-clause `ensures s == sum(a, i, j)`. The implementation
  computes the exact sum. Mutation kill score 0.25 < threshold 0.3
  because three of four mutants survive: the drop-conjunct mutant
  produces a vacuous spec; the two weakening ROR mutants (`==` to `>=`
  and `==` to `<=`) are satisfied by the exact-equality implementation
  by construction. Only the negate mutant kills.

**`CVS-handout1_tmp_tmptm52no3k_1.dfy` :: `query`**
- `true_FP`. Identical structure to `query` above; identical analysis.

**`Clover_cal_sum.dfy` :: `Sum`**
- `true_FP`. Single-clause `ensures s == N*(N+1)/2`. Same structural issue.

**`Clover_count_lessthan.dfy` :: `CountLessThan`**
- `true_FP`. Single-clause `ensures count == |set i | i in numbers && i < threshold|`.
  Same structural issue.

### Flagged by both detectors

**`CVS-Projto1_tmp_tmpb1o0bu8z_searchSort.dfy` :: `fillK`**
- `discovered_loose`. The method declares no `ensures` clause. ASC flags
  HIGH because no input is referenced in any ensures. The composed
  detector flags via check (c): trivial implementations `b := true;`
  and `b := false;` both satisfy the (empty) postcondition.

## Refined flag-rate decomposition

| Detector | Triage outcome | Count | Rate (N=38) |
|---|---|---|---|
| Composed detector | discovered_loose | 1 (fillK) | 2.63% |
| Composed detector | true_FP            | 4 (query×2, Sum, CountLessThan) | 10.53% |
| ASC reproduction  | discovered_loose | 3 (DPGD, gaussian, fillK) | 7.89% |
| ASC reproduction  | bug_in_reproduction | 1 (Tangent) | 2.63% |
| ASC reproduction  | true_FP (algorithm) | 0 | 0.00% |

## Implications

1. ASC achieves higher TP rate (7.89% vs 2.63%) and lower true-FP rate
   (0.00% on the original algorithm; 2.63% counting the reproduction bug)
   than the composed detector on this corpus. The two detectors target
   different failure modes; ASC's narrow scope is favorable here because
   the dominant honest-loose pattern in DafnyBench is methods with zero
   `ensures` clauses.
2. The composed detector's true-FP rate of 10.53% is structurally tied
   to its mutation kill score on single-clause specs. All four FPs share
   the shape `ensures r == f(inputs)`. Implemented mutation operators are
   four ROR weakenings, one drop-conjunct, and one negation. An honest
   single-clause equality spec admits at most one killable mutant
   (negation), forcing the kill score to a low ceiling regardless of
   spec quality.
3. The Tangent case is a defect in the reproduction's regex-based
   ensures extractor, not in IronSpec's algorithm. The extractor
   currently captures only single-line `ensures` clauses; the fix is
   to track operator and paren continuation across lines, or to switch
   to Dafny's resolution output.

## Recommended detector fixes

- **For check (d) on single-clause specs:** skip mutation kill score
  computation when the spec has only one clause and defer to check (c)
  for that case. Alternative: add a fifth mutator class that constructs
  strengthening rather than weakening mutants (e.g., a strict-equality
  refinement of an inequality, a domain-narrowing refinement of a
  quantifier).
- **For the extractor:** extend `extract_ensures_for_method` to track
  parenthesis and operator continuation across lines. Cleanest path is
  to delegate to `dafny resolve --print` output.
