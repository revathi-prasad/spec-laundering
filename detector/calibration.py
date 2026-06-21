"""Threshold calibration for a severity score over labeled (score, label) data.

Replaces the uncalibrated reported score: given labeled examples, pick an
operating threshold and report TPR/FPR/precision and an ROC curve.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThresholdEval:
    threshold: float
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def tpr(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def fpr(self) -> float:
        d = self.fp + self.tn
        return self.fp / d if d else 0.0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def youden_j(self) -> float:
        return self.tpr - self.fpr


def evaluate_threshold(scored: list[tuple[float, bool]], threshold: float) -> ThresholdEval:
    # predict positive iff score >= threshold
    tp = fp = tn = fn = 0
    for s, pos in scored:
        pred = s >= threshold
        if pred and pos:
            tp += 1
        elif pred and not pos:
            fp += 1
        elif not pred and pos:
            fn += 1
        else:
            tn += 1
    return ThresholdEval(threshold, tp, fp, tn, fn)


def candidate_thresholds(scored: list[tuple[float, bool]]) -> list[float]:
    scores = sorted({s for s, _ in scored})
    if not scores:
        return []
    cands = [scores[0] - 1e-9]
    cands += [(a + b) / 2 for a, b in zip(scores, scores[1:])]
    cands.append(scores[-1] + 1e-9)
    return cands


def best_threshold(scored: list[tuple[float, bool]]) -> ThresholdEval | None:
    """Threshold maximizing Youden's J (TPR - FPR)."""
    best = None
    for t in candidate_thresholds(scored):
        e = evaluate_threshold(scored, t)
        if best is None or e.youden_j > best.youden_j:
            best = e
    return best


def roc_curve(scored: list[tuple[float, bool]]) -> list[tuple[float, float]]:
    """(FPR, TPR) points across candidate thresholds, ascending FPR."""
    pts = {(round(e.fpr, 6), round(e.tpr, 6)) for e in (evaluate_threshold(scored, t) for t in candidate_thresholds(scored))}
    return sorted(pts)
