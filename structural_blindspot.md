# Structural blindspot of spec mutation testing for axiom-based cheating

This note characterizes why axiom-based cheating (Attack 5 in the
SpecLaunder benchmark) is not detectable by spec mutation testing
regardless of operator catalog size, and why a complementary syntactic
check is required.

## Setup

Spec mutation testing in the DeMillo–Offutt lineage (DeMillo et al.
1978, MuJava, PIT) and its extensions to specifications (Endres et al.
FSE 2024; IronSpec, Goldweber et al. OSDI 2024; MutDafny, Amaral et al.
arXiv:2511.15403) operates by applying a finite set of mutation operators
to the postcondition of a method ``M`` and checking whether ``M``'s
implementation ``B`` still verifies against the mutant postcondition.

Each mutation operator is a function on postcondition syntax:

```
op : Ensures -> Ensures
```

where ``Ensures`` is the syntactic representation of a method's
``ensures`` block (typically a list of clauses joined by ``&&``).

Axiom-based cheating, as exhibited by Attack 5 of the SpecLaunder
benchmark, leaves the method's ``ensures`` block syntactically unchanged
and discharges the proof obligation via a helper lemma whose body uses
``assume {:axiom} Q`` (where ``Q`` is the postcondition the lemma
exports).

## Three properties

### Property 1 — Mechanism blindspot

Mutation operators are functions on ``Ensures``. They do not transform
the bodies of any lemmas that ``M`` may call. The cheating mechanism in
Attack 5 — the ``assume {:axiom}`` inside the lemma body — is therefore
outside the domain of the mutation operator catalog by construction.
No operator catalog defined as ``Ensures -> Ensures`` can reach this
mechanism, regardless of catalog size.

### Property 2 — Verification may still respond to spec mutation

Property 1 alone does not imply that spec mutation has no effect on
verification of an axiom-cheated method. The cheating lemma exports a
postcondition ``Q``; mutating ``M``'s ``ensures`` to ``Q'`` produces a
new obligation that the lemma's exported ``Q`` may or may not satisfy.

Concretely, for Attack 5's ``ensures r == AbsValue(x)``:

| Mutant | Reasoning | Outcome |
|---|---|---|
| ``r >= AbsValue(x)`` | From assumed ``r == AbsValue(x)``, derive ``r >= AbsValue(x)``. Trivial. | mutant survives |
| ``r <= AbsValue(x)`` | Symmetric. | mutant survives |
| ``r != AbsValue(x)`` | From ``r == AbsValue(x)``, cannot derive ``r != AbsValue(x)``. | mutant killed |
| drop-conjunct (single clause -> vacuous) | Vacuous postcondition. | mutant survives |

The mutation kill score therefore measures the logical strength of
``Q`` relative to its mutants, not whether the proof obligation was
honestly discharged.

### Property 3 — Signature confusion

A method with an honest tight single-clause specification
``ensures r == f(inputs)`` and an axiom-cheated method with the same
specification produce identical mutation kill score signatures. Both:

- have one clause,
- admit the same set of weakening ROR mutants which the honest
  implementation trivially satisfies,
- admit exactly one informative non-weakening mutant (negation), which
  the honest implementation violates,
- have mutation kill score ``1 / k`` where ``k`` is the operator
  catalog size.

The triage of the DafnyBench sample (``results_triage.md``) documents
this empirically: four DafnyBench programs flagged by the composed
detector's check (d) (``query`` from CVS-Projto1 and from CVS-handout1,
``Sum`` from Clover, ``CountLessThan`` from Clover) all share this
single-clause equality shape, and all are honest. The detector's check
(d) signature for these is identical to that for Attack 5.

## Consequence

Detecting axiom-based cheating requires inspecting language constructs
that lie outside the postcondition syntax. The syntactic scan
implemented as check (f) — searching for ``assume``, ``assume {:axiom}``,
``lemma {:axiom}``, and ``{:verify false}`` — is the orthogonal signal
needed to make Attack 5 detectable.

This is not a deficiency of mutation testing as a technique. It is a
statement about the cheating dimensions a mutation operator catalog
covers by construction (the weakened-obligations dimension in
BabelBench's taxonomy) and the dimensions it does not (the
sorry/axioms dimension).

## Scope of the claim

- The claim is specific to mutation testing operators that are pure
  functions on postcondition syntax. Operators that recursively traverse
  the call graph and mutate lemma bodies would not be subject to
  Property 1, but such operators are not in the published catalogs of
  IronSpec, MutDafny, or related tools to current knowledge.
- The claim applies to the cheating dimension where the proof obligation
  is discharged via assumption in a lemma body. Other axiom-cheating
  patterns (e.g., method-level ``{:verify false}`` attributes) are
  similarly outside ``Ensures``-syntax mutation but are detected by the
  same syntactic scan.
- Property 3 is a methodological observation derived from triage of a
  finite DafnyBench sample. The claim that the failure mode generalizes
  to arbitrary single-clause equality specifications is structural, but
  the empirical evidence base in this work is small (N=4 honest cases in
  a 38-program sample).
