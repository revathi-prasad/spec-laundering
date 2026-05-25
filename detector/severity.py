"""Cheating-severity score for a (specification, implementation) pair.

Aggregates the orthogonal signals produced by checks (c), (d/e), and (f)
into a single numeric severity score in [0, 1]. Higher = more evidence of
specification looseness or axiom-based proof bypass.

Aggregation
-----------
severity = max over the implemented checks of each check's normalized
signal. The max() aggregation is deliberate: per-check signals target
disjoint cheating dimensions, so a single high signal is sufficient to
warrant flagging; averaging would let one dimension hide another.

Components
----------
component_c : float in [0, 1] or None
    Fraction of trivial implementations from the type-driven catalog that
    satisfy the specification. None if no trivials applicable to the
    method signature (e.g., unsupported return type).

component_d : float in [0, 1] or None
    1 - filtered_kill_score. Filtered kill score is the mutation kill
    score after equivalent-mutant filtering (check (e)). None if no
    mutants applicable (e.g., extractor failed).

component_f : float in {0.0, 1.0}
    1.0 if any of assume / {:axiom} / lemma {:axiom} / {:verify false}
    patterns is present in the source; 0.0 otherwise. The check is
    syntactic and binary by construction.

Relation to prior work
----------------------
Twin-metric "correctness + completeness" approaches (CLEVER benchmark
arXiv:2505.13938; nl2postcond Endres et al. FSE 2024) measure
specification quality on the cooperative-developer threat model. The
score implemented here measures cheating severity on the adversarial
spec-author threat model, where the question is whether a (spec, impl)
pair shows signs of bypass rather than how well a spec discriminates
buggy implementations.

Bidirectional-equivalence scoring (VeriEquivBench arXiv:2510.06296) uses
the Dafny verifier to check implication between generated code and
specification. The severity score here uses the same verifier as the
underlying judge but aggregates over multiple cheating-dimension checks
rather than a single equivalence relation.

Calibration
-----------
The aggregation is uncalibrated: the max function assumes the three
signal channels are commensurable in [0, 1]. Per-channel weights based on
empirical per-check reliability on a labeled corpus would refine the
score; no such labeled corpus exists for Dafny specifications, so the
implementation reports the unweighted max and the per-channel
contributions separately for downstream calibration.

Limitations
-----------
- The score is bounded above by the coverage of the implemented checks.
  Cheating dimensions outside the catalog (e.g., aggressive automation
  via :fuel overrides or :opaque reveals) contribute 0 regardless of
  severity in those dimensions.
- The score is normalized but not probabilistic; it does not express
  "probability of cheating" and should not be interpreted as such.
- Single-clause equality specs produce a check (d) component near
  1 - 1/N where N is the number of mutation operators, irrespective of
  spec quality. The triage in results_triage.md documents this
  structural failure mode of mutation kill score on single-clause specs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import check_c_noop_sat as cc
from . import check_d_mutation_kill as cd
from . import check_e_equiv_filter as ce
from . import check_f_assume as cf


@dataclass
class SeverityResult:
    """Aggregated cheating-severity score and per-check components.

    Attributes
    ----------
    file_path : str
    method_name : str
    component_c : float or None
        Normalized check (c) signal.
    component_d : float or None
        Normalized check (d/e) signal.
    component_f : float
        Binary check (f) signal in {0.0, 1.0}.
    severity : float or None
        max over non-None components; None if all components are None.
    consensus : int
        Number of components above threshold 0.5. Reported separately as
        a transparency indicator; not used in the score itself.
    """

    file_path: str
    method_name: str
    component_c: float | None
    component_d: float | None
    component_f: float
    severity: float | None = field(init=False)
    consensus: int = field(init=False)

    def __post_init__(self) -> None:
        signals = [s for s in (self.component_c, self.component_d, self.component_f) if s is not None]
        self.severity = max(signals) if signals else None
        self.consensus = sum(1 for s in signals if s >= 0.5)


def _component_c(c_res: cc.NoopResult) -> float | None:
    if c_res.trivial_impls_tried == 0:
        return None
    return len(c_res.satisfying_impls) / c_res.trivial_impls_tried


def _component_d(e_res: ce.FilteredKillResult) -> float | None:
    if e_res.filtered_tried == 0:
        return None
    return 1.0 - e_res.filtered_kill_score


def _component_f(f_res: cf.CheckFResult) -> float:
    return 1.0 if f_res.flagged else 0.0


def compute_severity(file_path: Path | str, method_name: str) -> SeverityResult:
    """Compute the cheating-severity score for one (spec, impl) pair.

    Parameters
    ----------
    file_path : Path or str
        Path to the .dfy file containing the method.
    method_name : str
        Name of the method to evaluate.

    Returns
    -------
    SeverityResult
    """
    file_path = Path(file_path)
    c_res = cc.run_check_c(file_path, method_name)
    d_res = cd.run_check_d(file_path, method_name)
    e_res = ce.run_check_e(file_path, method_name, raw_result=d_res)
    f_res = cf.scan_file(file_path)
    return SeverityResult(
        file_path=str(file_path),
        method_name=method_name,
        component_c=_component_c(c_res),
        component_d=_component_d(e_res),
        component_f=_component_f(f_res),
    )
