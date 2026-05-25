"""Reproduction of IronSpec's input-dependency Automatic Sanity Check.

Reproduced from ``Source/Dafny/SpecInputOutputChecker.cs`` at commit
``28d01ef64a9eeadc28a32c0bc08d89436fe03e04`` of
``github.com/GLaDOS-Michigan/IronSpec``. The relevant code path is in
``ProcessProgram``, lines 627-660 of that file:

    foreach (var inputF in desiredMethod.Ins) {
        ...
        foreach (var nestedF in tfs.Values) {
            var sanCheck = simpleEnsSanityCheck(desiredMethod, nestedF, false);
            deepCheck &= sanCheck;
            noInputIsNeededInOutput |= sanCheck;
        }
    }
    if (!noInputIsNeededInOutput && desiredMethod.Ins.Count > 0) {
        Console.WriteLine("\n-- FLAG(HIGH) -- : NONE of Ensures depend on Any input parameters\n");
    }

The ``simpleEnsSanityCheck`` helper iterates ensures clauses and returns
true iff any formal on the clause matches ``inputF.Name``. The reproduction
treats the matching predicate as a word-boundary occurrence of the input
name inside any ensures clause text.

Scope of reproduction
---------------------
- Only the input-dependency HIGH flag is reproduced.
- The output-coverage flag (lines 661-697 of the same file), which uses
  Dafny's ``TraverseFormalSimplified`` to descend through datatype fields,
  is not reproduced; that path requires Dafny's resolved AST and cannot
  be approximated by a syntactic scan without sacrificing fidelity.
- IronSpec's deeper checks that handle nested formals (e.g. for record
  fields) are likewise out of scope.

Validation
----------
The module ships a small validation harness (``validate()``) that exercises
the reproduction on IronSpec's bundled test specs:

- ``IronSpec/specs/sort/sortMethod.dfy`` :: ``merge_sort`` — ASC documented
  to flag HIGH (the sortedness postcondition only mentions ``output``).
- The attack benchmark's ``MaxOriginal`` — every input is referenced in
  ``ensures``; ASC should NOT flag.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from . import check_a_noop_sat as ca
from . import check_b_mutation_kill as cb


@dataclass
class ASCResult:
    """Outcome of the reproduced input-dependency check.

    Attributes
    ----------
    file_path : str
    method_name : str
    has_inputs : bool
    referenced_inputs : list of str
        Input parameter names that appear in at least one ensures clause.
    unreferenced_inputs : list of str
        Input parameter names that appear in zero ensures clauses.
    high_flag : bool
        True iff the method has inputs and zero of them are referenced
        in any ensures clause.
    """

    file_path: str
    method_name: str
    has_inputs: bool
    referenced_inputs: list[str]
    unreferenced_inputs: list[str]
    high_flag: bool


def _name_appears_in_clauses(name: str, clauses: list[str]) -> bool:
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    return any(pattern.search(c) for c in clauses)


def run_asc(file_path: Path | str, method_name: str) -> ASCResult:
    """Run the reproduced ASC input-dependency check on one method.

    Parameters
    ----------
    file_path : Path or str
    method_name : str

    Returns
    -------
    ASCResult
    """
    file_path = Path(file_path)
    source = file_path.read_text(encoding="utf-8")

    inputs, _ = ca.extract_signature(source, method_name)
    _, ensures_clauses = cb.extract_ensures_for_method(source, method_name)

    if inputs is None or not inputs:
        return ASCResult(
            file_path=str(file_path),
            method_name=method_name,
            has_inputs=False,
            referenced_inputs=[],
            unreferenced_inputs=[],
            high_flag=False,
        )

    referenced: list[str] = []
    unreferenced: list[str] = []
    for name, _ty in inputs:
        if _name_appears_in_clauses(name, ensures_clauses):
            referenced.append(name)
        else:
            unreferenced.append(name)

    return ASCResult(
        file_path=str(file_path),
        method_name=method_name,
        has_inputs=True,
        referenced_inputs=referenced,
        unreferenced_inputs=unreferenced,
        high_flag=(len(referenced) == 0),
    )


def validate(
    ironspec_dir: Path | str, attacks_dir: Path | str
) -> int:
    """Run the reproduction against IronSpec's bundled test specs.

    Parameters
    ----------
    ironspec_dir : Path or str
        Path to a clone of github.com/GLaDOS-Michigan/IronSpec.
    attacks_dir : Path or str
        Path to the SpecLaunder ``attacks/`` directory; used as a positive
        control (ASC should NOT flag ``MaxOriginal``).

    Returns
    -------
    int
        0 if all validation cases match expectation, 1 otherwise.
    """
    ironspec_dir = Path(ironspec_dir)
    attacks_dir = Path(attacks_dir)

    cases = [
        # (file, method, expected_high_flag, expected_reason)
        (
            ironspec_dir / "specs/sort/sortMethod.dfy",
            "merge_sort",
            True,
            "sortedness postcondition references only output",
        ),
        (
            attacks_dir / "attack1_drop_conjunct.dfy",
            "MaxOriginal",
            False,
            "ensures r >= a, r >= b, ... references both inputs",
        ),
        (
            attacks_dir / "attack1_drop_conjunct.dfy",
            "MaxLaundered",
            False,
            "laundered version still references both inputs",
        ),
    ]

    print("# IronSpec ASC reproduction — validation")
    print()
    print(f"{'case':<60} {'method':<20} {'expected':<10} {'got':<10} match")
    print("-" * 110)

    failures = 0
    for path, method, expected, reason in cases:
        if not path.exists():
            print(f"{str(path)[:58]:<60} {method:<20} {'-':<10} {'NOT FOUND':<10} -")
            failures += 1
            continue
        res = run_asc(path, method)
        got = "HIGH" if res.high_flag else "no-flag"
        exp = "HIGH" if expected else "no-flag"
        ok = res.high_flag == expected
        marker = "ok" if ok else "FAIL"
        if not ok:
            failures += 1
        short = path.name
        print(f"{short[:58]:<60} {method:<20} {exp:<10} {got:<10} {marker}    # {reason}")
    return 1 if failures else 0


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    sys.exit(
        validate(
            ironspec_dir=repo_root / "IronSpec",
            attacks_dir=repo_root / "attacks",
        )
    )
