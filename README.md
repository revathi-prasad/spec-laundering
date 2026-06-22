# SpecLaunder

Detecting **verified-but-wrong** Dafny code: implementations that pass the
verifier against a weakened specification yet violate the intended behavior.

## Problem

A verified program is a triple `(S, φ, P)` — implementation, specification, and
a machine-checked proof that `S` satisfies `φ`. When one agent authors both `S`
and `φ` (as in LLM vericoding pipelines), an adversarially or lazily **weakened
`φ`** admits a backdoored `S` while keeping the verifier's "verified" stamp.

The detection target is **verified-but-wrong**, *not* adversarial intent: intent
(lazy vs malicious) is not recoverable from a text artifact, but "passed the
verifier yet behaviorally wrong" is — given a reference for correct behavior.

## Where the lie can hide (three families)

| Family | Mechanism | Reference spec exists? | Detected by |
|---|---|---|---|
| A. spec weakening | `φ` made strictly weaker | yes | **`coupling`** |
| B. proof bypass | `assume`/axiom; `φ` unchanged | yes (verifier lied) | `axiom_scan` / `coupling` `V_semantic` |
| C. spec incompleteness | `φ` never captured the property | no | `trivial_sat` (partial) — see boundary below |

## The coupling check (primary)

Given a strong reference spec `φ_strong`, a weakened `φ_weak`, and an
implementation `B` that verifies against `φ_weak`, for each strong clause `c_i`:

- **D (dropped):** does `φ_weak ∧ Pre` still entail `c_i`? (a `DropProbe` lemma)
- **V (violated):** does `B` fail `c_i`? (splice/insert `ensures c_i`, re-verify) —
  computed as `V_proof` (as-is) and `V_semantic` (proof scaffolding stripped).

Verdict (`V = V_proof ∪ V_semantic`):

```
V empty                 -> honest
V nonempty, V ⊆ D       -> spec_laundering   (the code breaks exactly what was dropped)
V nonempty, V ⊄ D       -> proof_laundering  (a non-dropped clause is broken yet verified)
reference names absent  -> incomparable      (e.g. signature rename)
```

`surgical_score = 1 − |D − V| / |D|` (targeting precision; low = blunt weakening).

Unlike the other checks, `coupling` consults `φ_strong`. Detecting that a spec is
merely *weak* is prior work (nl2postcond/Endres–Lahiri; spectest-completeness,
arXiv:2604.05820); coupling's contribution is the **attribution** — which clauses,
how surgical, and spec- vs proof-laundering — measured against a reference.

## The detector

`coupling` (reference-based) plus three reference-free checks aggregated into a
severity score:

| Check | Question | Family |
|---|---|---|
| `coupling` | Does `B` exploit the dropped clauses? | A |
| `trivial_sat` | Does `φ` admit a trivial/unrelated impl? | C |
| `mutation` | How tightly does `B` pin `φ`? (kill score) | — (tracks spec shape, not impl) |
| `axiom_scan` | Is the proof bypassed (`assume`/axiom)? | B |

## Results (real Dafny 4.11.0)

- **Hand benchmark** (`scripts/run_coupling.py` → `results/coupling_benchmark.json`):
  attacks 1–4 → `spec_laundering`, attack 5 → `proof_laundering` (caught only by
  `V_semantic`), attack 6 (AWS Digest, signature rename) → `incomparable`.
- **Uncoupled control** (`scripts/run_control.py`): same weak spec, varying the
  impl — `mutation` false-positives on honest-loose code and misses the backdoor
  (it tracks spec shape); `coupling` is correct on all three.
- **Labeled A-evade dataset** (`scripts/build_dataset.py` → `results/dataset.json`):
  N=82, balanced. Labels from differential testing (`detector/difftest.py`),
  independent of the detector. **41/41 verified-but-wrong caught, 0 evasions,
  0 false positives.** The loop also found and we fixed a real soundness gap
  (empty-spec laundering) the hand benchmark never exercised.
- **Internal ablation** (`scripts/ablation.py` → `results/ablation.json`):
  coupling accuracy **1.00**; the `mutation` baseline reaches **0.56** at its
  best calibrated threshold (no usable discrimination).
- **LLM-judge foil** (`scripts/run_llm_judge.py` → `results/llm_judge.json`):
  a semantic judge reaches **0.93** (TPR 0.85, FPR 0.0) — strong but
  non-deterministic, missing 6/41 including blatant cases coupling catches.
- **Boundary** (`scripts/family_c_demo.py` → `results/family_c_demo.json`):
  coupling is only as sound as the reference. Under an incomplete spec
  (`|r| == 2*|s|`, length only) a right-length/wrong-content impl is rated
  `honest` while differential testing proves it wrong (Family C).

`coupling`'s perfect score is *sound-by-construction* for Family A (complete-spec
weakening); it is a confirmation of soundness on the modeled family, not a claim
of general coverage. Family C remains the open boundary.

## Reproduce

```bash
bash scripts/setup_dafny.sh                # install Dafny 4.11.0 (idempotent)
python3 -m unittest discover -s tests      # unit tests (no Dafny needed)
python3 scripts/run_coupling.py            # hand-benchmark verdicts
python3 scripts/run_control.py             # uncoupled control
python3 scripts/build_dataset.py           # labeled dataset (slow; real Dafny)
python3 scripts/ablation.py                # coupling vs mutation
python3 scripts/family_c_demo.py           # Family-C boundary
```

Python 3.11+ standard library only; the checks shell out to the `dafny` CLI.

## Limitations

- **Needs a reference spec.** `coupling` requires `φ_strong`; a reference-free
  deployment version (using an independent spec or differential testing as the
  reference) is not built.
- **Family C.** An incomplete reference spec is `coupling`'s soundness boundary
  (demonstrated above).
- **Scale and scope.** N=82 over 8 seed problems with simple types; not yet run
  on large real codebases.
- **`mutation` operator catalog** is expanded (ROR/AOR/LCR/quantifier/const) but
  still smaller than MutDafny's ~40.

## Related work

- Goldweber et al. *IronSpec.* USENIX OSDI 2024 (input-dependency sanity checks; a
  disjoint, honest-incompleteness failure mode — not a baseline here).
- Amaral, Mendes, Campos. *MutDafny.* arXiv:2511.15403, 2025 (`mutation` ≈ a
  reimplementation of its idea).
- Endres et al. *Can LLMs Transform NL Intent into Formal Postconditions?* FSE 2024.
- *RL with Negative Tests as a Completeness Signal for Spec Synthesis.* arXiv:2604.05820.
- Aggarwal et al. *AlphaVerus.* arXiv:2412.06176, 2024. · Sun et al. *Clover.*
  arXiv:2310.17807, 2023. · Loughridge et al. *DafnyBench.* arXiv:2406.08467, 2024.
- DeMillo, Lipton, Sayward. *Hints on Test Data Selection.* 1978. · Beer et al.
  *Efficient Detection of Vacuity in ACTL Formulas.* CAV 1997.

## License

[ to be added ]
