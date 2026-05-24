"""SMT-based equivalent-mutant filter for postcondition mutation testing.

Removes mutants whose mutated postcondition is logically equivalent to the
original, addressing one source of inflation in the raw kill score.

For an original postcondition ``Q`` and a mutant ``Q'``, the mutants are
equivalent iff ``Q <==> Q'`` is valid. The check is delegated to Dafny by
constructing a synthetic lemma over the free variables of the postconditions
and verifying it::

    lemma EquivProbe(<vars>) ensures Q <==> Q';

If Dafny verifies the lemma, the mutant is equivalent and excluded from
both numerator and denominator of the filtered kill score. If Dafny
rejects, the mutant is genuinely distinct and contributes to the score
as before. If Dafny times out or returns unknown, the mutant is conservatively
retained (counted toward the denominator only if the original kill check
classifies it).

MutDafny (Amaral, Mendes, Campos, arXiv:2511.15403) names equivalent-mutant
detection as the first item in its open problems. This module is one
construction; faithfulness to Dafny's decision procedure (Z3 4.8.5) is
inherited, including its limits on nonlinear arithmetic and quantifier
alternation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import dafny
from .check_d_mutation_kill import (
    CheckDResult,
    Mutant,
    all_mutants,
    extract_ensures_for_method,
)


@dataclass
class EquivResult:
    """Per-mutant equivalence-test outcome.

    Attributes
    ----------
    mutant : Mutant
    equivalent : bool
        True iff Dafny verified ``Q <==> Q'``.
    indeterminate : bool
        True iff Dafny returned without a clear verdict (timeout, parse error).
    """

    mutant: Mutant
    equivalent: bool
    indeterminate: bool = False


@dataclass
class FilteredKillResult:
    """Kill-score after equivalent-mutant filtering.

    Attributes
    ----------
    raw : CheckDResult
        Unfiltered check (d) result for reference.
    equivalences : list of EquivResult
        One per mutant tested for equivalence.
    equivalent_count : int
        Number of mutants Dafny classified as equivalent to the original.
    indeterminate_count : int
        Number of mutants Dafny could not classify.
    filtered_tried : int
        Mutants remaining after dropping equivalents.
    filtered_killed : int
        Killed mutants among the non-equivalent.
    filtered_kill_score : float
    """

    raw: CheckDResult
    equivalences: list[EquivResult] = field(default_factory=list)
    equivalent_count: int = 0
    indeterminate_count: int = 0
    filtered_tried: int = 0
    filtered_killed: int = 0
    filtered_kill_score: float = 0.0


def _collect_variables(source: str, method_name: str) -> list[tuple[str, str]]:
    """Collect (name, type) pairs for a method's inputs and named outputs."""
    sig_re = re.compile(
        rf"method\s+{re.escape(method_name)}\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)"
    )
    m = sig_re.search(source)
    if not m:
        return []
    out: list[tuple[str, str]] = []
    for chunk in (m.group(1), m.group(2)):
        depth = 0
        buf: list[str] = []
        items: list[str] = []
        for ch in chunk:
            if ch == "<":
                depth += 1
                buf.append(ch)
            elif ch == ">":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 0:
                items.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        if buf:
            items.append("".join(buf))
        for item in items:
            item = item.strip()
            if ":" not in item:
                continue
            name, ty = item.split(":", 1)
            out.append((name.strip(), ty.strip()))
    return out


def _conj(clauses: list[str]) -> str:
    """Join clauses with `&&`, parenthesizing each. Empty list -> ``true``."""
    if not clauses:
        return "true"
    return " && ".join(f"({c})" for c in clauses)


def _equiv_probe(
    extras: str,
    vars_decl: str,
    original: list[str],
    mutated: list[str],
) -> str:
    """Build a self-contained Dafny program asserting Q <==> Q'.

    ``extras`` is prepended verbatim and carries any function/predicate
    declarations referenced by the postconditions.
    """
    q = _conj(original)
    q_prime = _conj(mutated)
    return (
        extras
        + "\n\n"
        + f"lemma EquivProbe({vars_decl})\n"
        + f"  ensures ({q}) <==> ({q_prime})\n"
        + "{ }\n"
    )


def _extract_supporting_decls(source: str, method_name: str) -> str:
    """Extract function / predicate declarations referenced by the spec.

    A minimal implementation: capture every top-level ``function`` and
    ``predicate`` declaration in the source. The equivalence probe then has
    the same name resolution environment as the original method.
    """
    out: list[str] = []
    decl_re = re.compile(
        r"^(\s*)(function|predicate|datatype|type)\s",
        re.MULTILINE,
    )
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        if decl_re.match(lines[i]):
            start = i
            # Capture until matching closing brace at column 0 or end-of-block.
            depth = 0
            seen_open = False
            j = i
            while j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                if "{" in lines[j]:
                    seen_open = True
                if seen_open and depth == 0:
                    break
                j += 1
            out.append("\n".join(lines[start : j + 1]))
            i = j + 1
        else:
            i += 1
    return "\n\n".join(out)


def _equivalent_under_dafny(
    extras: str,
    vars_decl: str,
    original: list[str],
    mutated: list[str],
    timeout_s: int = 30,
) -> tuple[bool, bool]:
    """Return (equivalent, indeterminate)."""
    src = _equiv_probe(extras, vars_decl, original, mutated)
    res = dafny.verify_source(src, timeout_s=timeout_s)
    if res.success:
        return True, False
    if res.returncode == -1:
        return False, True
    return False, False


def run_check_e(
    file_path: Path | str, method_name: str, raw_result: CheckDResult | None = None
) -> FilteredKillResult:
    """Filter equivalent mutants from a kill-score computation.

    Parameters
    ----------
    file_path : Path or str
    method_name : str
    raw_result : CheckDResult, optional
        Pre-computed check (d) result for the same method. If omitted, the
        function reproduces the mutant set and verification map.

    Returns
    -------
    FilteredKillResult
    """
    file_path = Path(file_path)
    source = file_path.read_text(encoding="utf-8")
    ensures_lines, ensures_exprs = extract_ensures_for_method(source, method_name)
    if not ensures_exprs:
        return FilteredKillResult(
            raw=raw_result
            or CheckDResult(
                file_path=str(file_path),
                method_name=method_name,
                original_ensures=[],
                mutants_tried=0,
                mutants_killed=0,
            )
        )

    if raw_result is None:
        # Avoid a circular import; reach into check_d directly.
        from . import check_d_mutation_kill as cd

        raw_result = cd.run_check_d(file_path, method_name)

    extras = _extract_supporting_decls(source, method_name)
    sig_vars = _collect_variables(source, method_name)
    vars_decl = ", ".join(f"{n}: {t}" for n, t in sig_vars)

    equivalences: list[EquivResult] = []
    equivalent_count = 0
    indeterminate_count = 0
    for m in all_mutants(ensures_exprs):
        equiv, indet = _equivalent_under_dafny(
            extras, vars_decl, ensures_exprs, m.mutated_ensures
        )
        equivalences.append(EquivResult(m, equivalent=equiv, indeterminate=indet))
        if equiv:
            equivalent_count += 1
        elif indet:
            indeterminate_count += 1

    survivor_keys = {(s.mutant.operator, s.mutant.original_clause): True for s in raw_result.survivors}
    filtered_tried = 0
    filtered_killed = 0
    for e in equivalences:
        if e.equivalent:
            continue
        filtered_tried += 1
        key = (e.mutant.operator, e.mutant.original_clause)
        if key not in survivor_keys:
            filtered_killed += 1

    filtered_kill_score = (
        filtered_killed / filtered_tried if filtered_tried else 0.0
    )

    return FilteredKillResult(
        raw=raw_result,
        equivalences=equivalences,
        equivalent_count=equivalent_count,
        indeterminate_count=indeterminate_count,
        filtered_tried=filtered_tried,
        filtered_killed=filtered_killed,
        filtered_kill_score=filtered_kill_score,
    )
