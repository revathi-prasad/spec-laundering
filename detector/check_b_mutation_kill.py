"""Mutation kill score for Dafny method postconditions.

For a method with implementation B and postcondition ``Q = Q_1 ∧ ... ∧ Q_n``,
generate mutants ``Q'`` of ``Q`` under a fixed operator catalog. For each
mutant, ask Dafny whether B verifies against ``ensures Q'``. The kill score
is the fraction of mutants Dafny rejects::

    kill_score = | { Q' : Dafny rejects (B, Q') } | / | { Q' } |

Operators
---------
drop_conjunct  : remove one top-level ``ensures`` clause
ror_eq_to_ge   : ``==``  ->  ``>=``
ror_eq_to_le   : ``==``  ->  ``<=``
ror_ge_to_gt   : ``>=``  ->  ``>``
ror_le_to_lt   : ``<=``  ->  ``<``
negate         : ``Q_i`` ->  ``!(Q_i)``

The drop-conjunct and ROR operators produce strictly weaker mutants; an
honest implementation generally satisfies them. The negate operator produces
a non-weakening mutant; an honest implementation generally violates it.

Equivalent-mutant filtering (check (c)) is not applied at this layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import dafny


@dataclass
class Mutant:
    """One mutant of a method's postcondition.

    Attributes
    ----------
    operator : str
        Name of the mutation operator applied.
    original_clause : str
    mutated_clause : str or None
        None for drop_conjunct.
    mutated_ensures : list of str
        Full ensures list after mutation.
    """

    operator: str
    original_clause: str
    mutated_clause: str | None
    mutated_ensures: list[str]


@dataclass
class MutationResult:
    """Per-mutant verification outcome.

    Attributes
    ----------
    mutant : Mutant
    verifies : bool
        True iff Dafny accepted (B, mutated_ensures); the mutant survived.
    """

    mutant: Mutant
    verifies: bool


@dataclass
class CheckBResult:
    """Aggregated kill-score result for one method.

    Attributes
    ----------
    file_path : str
    method_name : str
    original_ensures : list of str
    mutants_tried : int
    mutants_killed : int
    survivors : list of MutationResult
    kill_score : float
    """

    file_path: str
    method_name: str
    original_ensures: list[str]
    mutants_tried: int
    mutants_killed: int
    survivors: list[MutationResult] = field(default_factory=list)
    kill_score: float = 0.0


_ENSURES_RE = re.compile(r"^\s*ensures\s+(.+?)\s*$")


def extract_ensures_for_method(
    source: str, method_name: str
) -> tuple[list[int], list[str]]:
    """Locate single-line ``ensures`` clauses attached to a named declaration.

    Walks forward from the declaration line, accepting contiguous
    ``ensures`` / ``requires`` / ``decreases`` / ``modifies`` / ``reads``
    lines until the first ``{``.

    Returns
    -------
    (line_numbers, expression_strings)
    """
    lines = source.splitlines()
    method_start = None
    decl_re = re.compile(
        rf"^\s*(method|function|predicate|lemma)\s+{re.escape(method_name)}\b"
    )
    for i, line in enumerate(lines):
        if decl_re.search(line):
            method_start = i
            break
    if method_start is None:
        return [], []

    ensures_lines: list[int] = []
    ensures_exprs: list[str] = []
    # `returns` is included to skip the case where a method signature spans
    # multiple lines, with `returns (...)` on its own line after the parameter
    # list. This is common in AWS-style Dafny formatting.
    contract_intro = re.compile(
        r"^\s*(ensures|requires|decreases|modifies|reads|returns)\b"
    )
    for j in range(method_start + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped.startswith("{"):
            break
        m = _ENSURES_RE.match(lines[j])
        if m:
            ensures_lines.append(j)
            ensures_exprs.append(m.group(1))
            continue
        if contract_intro.search(lines[j]):
            continue
        if stripped and not stripped.startswith("//"):
            break
    return ensures_lines, ensures_exprs


def _drop_conjunct(ensures: list[str]) -> list[Mutant]:
    out = []
    for i, clause in enumerate(ensures):
        mutated = ensures[:i] + ensures[i + 1 :]
        out.append(Mutant("drop_conjunct", clause, None, mutated))
    return out


_ROR_REPLACEMENTS = [
    ("ror_eq_to_ge", r"==", ">="),
    ("ror_eq_to_le", r"==", "<="),
    ("ror_ge_to_gt", r">=", ">"),
    ("ror_le_to_lt", r"<=", "<"),
]


def _ror(ensures: list[str]) -> list[Mutant]:
    out = []
    for i, clause in enumerate(ensures):
        for op_name, pat, repl in _ROR_REPLACEMENTS:
            if re.search(rf"(?<![<>=!]){pat}(?!=)", clause):
                mutated_clause = re.sub(
                    rf"(?<![<>=!]){pat}(?!=)", repl, clause, count=1
                )
                if mutated_clause != clause:
                    out.append(
                        Mutant(
                            op_name,
                            clause,
                            mutated_clause,
                            ensures[:i] + [mutated_clause] + ensures[i + 1 :],
                        )
                    )
    return out


def _negate(ensures: list[str]) -> list[Mutant]:
    out = []
    for i, clause in enumerate(ensures):
        mutated = f"!({clause})"
        out.append(
            Mutant(
                "negate",
                clause,
                mutated,
                ensures[:i] + [mutated] + ensures[i + 1 :],
            )
        )
    return out


def all_mutants(ensures: list[str]) -> list[Mutant]:
    """Return all mutants produced by the implemented operators."""
    return _drop_conjunct(ensures) + _ror(ensures) + _negate(ensures)


def _splice_ensures(
    source: str, ensures_lines: list[int], new_ensures: list[str]
) -> str:
    lines = source.splitlines()
    if not ensures_lines:
        return source
    first = ensures_lines[0]
    indent = re.match(r"^\s*", lines[first]).group(0)
    new_block = [f"{indent}ensures {e}" for e in new_ensures]
    out = (
        lines[:first]
        + new_block
        + [lines[k] for k in range(first + 1, len(lines)) if k not in ensures_lines]
    )
    return "\n".join(out) + ("\n" if source.endswith("\n") else "")


def run_check_b(file_path: Path | str, method_name: str) -> CheckBResult:
    """Run the mutation kill score check on one method.

    Parameters
    ----------
    file_path : Path or str
    method_name : str

    Returns
    -------
    CheckBResult
    """
    file_path = Path(file_path)
    source = file_path.read_text(encoding="utf-8")
    ensures_lines, ensures_exprs = extract_ensures_for_method(source, method_name)
    if not ensures_exprs:
        return CheckBResult(
            file_path=str(file_path),
            method_name=method_name,
            original_ensures=[],
            mutants_tried=0,
            mutants_killed=0,
            kill_score=0.0,
        )

    mutants = all_mutants(ensures_exprs)
    killed = 0
    survivors: list[MutationResult] = []
    for m in mutants:
        mutated_source = _splice_ensures(source, ensures_lines, m.mutated_ensures)
        res = dafny.verify_source(mutated_source)
        if not res.success:
            killed += 1
        else:
            survivors.append(MutationResult(m, verifies=True))

    total = len(mutants)
    return CheckBResult(
        file_path=str(file_path),
        method_name=method_name,
        original_ensures=ensures_exprs,
        mutants_tried=total,
        mutants_killed=killed,
        survivors=survivors,
        kill_score=(killed / total) if total else 0.0,
    )
