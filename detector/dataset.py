"""Dataset records and labeling for the matched generation / harvest set.

label axis (impl behavior) is set from differential testing; spec_quality axis
(tight/loose/ambiguous) is set separately. Verification and differential testing
are Dafny-gated and live in the runner.
"""

from __future__ import annotations

from dataclasses import dataclass

_CONDITIONS = ("H", "L", "A", "A-evade", "harvested")
_SPEC_QUALITY = ("tight", "loose", "ambiguous")
_REQUIRED = (
    "problem_id",
    "condition",
    "source",
    "strong_spec",
    "generated_spec",
    "generated_impl",
)


def classify_label(verifies: bool, behaviorally_correct: bool) -> str:
    if not verifies:
        return "invalid"
    return "honest_correct" if behaviorally_correct else "verified_but_wrong"


@dataclass
class Record:
    problem_id: str
    condition: str
    source: str  # generated | harvested
    strong_spec: list
    generated_spec: list
    generated_impl: str
    verifies: bool | None = None
    behaviorally_correct: bool | None = None
    spec_quality: str | None = None
    label: str | None = None

    def finalize(self) -> "Record":
        if self.verifies is not None and self.behaviorally_correct is not None:
            self.label = classify_label(self.verifies, self.behaviorally_correct)
        return self


def validate_record(d: dict) -> list[str]:
    errs = [f"missing:{k}" for k in _REQUIRED if not d.get(k)]
    if d.get("condition") not in _CONDITIONS:
        errs.append("bad:condition")
    if d.get("spec_quality") is not None and d["spec_quality"] not in _SPEC_QUALITY:
        errs.append("bad:spec_quality")
    return errs
