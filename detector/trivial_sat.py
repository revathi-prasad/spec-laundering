"""Trivial-implementation satisfiability check for Dafny method specifications.

For a method with signature ``(inputs) -> (outputs)``, synthesize candidate
implementations from a type-driven catalog (constant return values, identity
projection, zero-filled sequences of varying lengths), substitute each into
the method body, and run Dafny verification. A satisfying trivial candidate
is evidence that the specification admits implementations unrelated to the
method's intent.

Catalog
-------
int return        : ``0``, ``1``, each int-typed input by name
bool return       : ``true``, ``false``
seq<T> return     : ``[]``, each seq-typed input by name, doubled and tripled
                    concatenations, ``seq(k, i => default(T))`` for
                    k in {0, 1, |input|, 2*|input|, 3*|input|}
other return types: not synthesized
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import dafny


@dataclass
class NoopResult:
    """Outcome of the trivial-impl satisfiability check on one method.

    Attributes
    ----------
    file_path : str
    method_name : str
    trivial_impls_tried : int
    satisfying_impls : list of str
        Candidate implementations whose substitution verified.
    error : str or None
        Error string if the signature could not be parsed.
    """

    file_path: str
    method_name: str
    trivial_impls_tried: int
    satisfying_impls: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def flagged(self) -> bool:
        return len(self.satisfying_impls) > 0


def _parse_param_list(s: str) -> list[tuple[str, str]]:
    """Parse a Dafny parameter list ``name1: T1, name2: T2``.

    Tracks angle-bracket depth so nested generics parse correctly.
    """
    out: list[tuple[str, str]] = []
    if not s.strip():
        return out
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in s:
        if ch == "<":
            depth += 1
            buf.append(ch)
        elif ch == ">":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    for part in parts:
        part = part.strip()
        if ":" not in part:
            continue
        name, ty = part.split(":", 1)
        out.append((name.strip(), ty.strip()))
    return out


def extract_signature(source: str, method_name: str):
    """Extract (inputs, outputs) for a named method.

    Parameters
    ----------
    source : str
    method_name : str

    Returns
    -------
    (list of (name, type), list of (name, type)) or (None, None)
    """
    pattern = rf"method\s+{re.escape(method_name)}\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)"
    m = re.search(pattern, source)
    if not m:
        return None, None
    return _parse_param_list(m.group(1)), _parse_param_list(m.group(2))


def _default_value_for_element(elt_type: str) -> str | None:
    elt_type = elt_type.strip()
    if elt_type == "int":
        return "0"
    if elt_type == "bool":
        return "false"
    if elt_type == "char":
        return "'a'"
    return None


def synthesize_trivials(
    inputs: list[tuple[str, str]], outputs: list[tuple[str, str]]
) -> list[str]:
    """Build candidate assignment statements for a single-output method.

    Returns an empty list for methods with zero or multiple outputs, or for
    output types outside the supported catalog (int, bool, seq<T>).
    """
    if not outputs or len(outputs) != 1:
        return []
    out_name, out_type = outputs[0]
    out_type = out_type.strip()
    impls: list[str] = []

    if out_type == "int":
        impls += [f"{out_name} := 0;", f"{out_name} := 1;"]
        for name, ty in inputs:
            if ty.strip() == "int":
                impls.append(f"{out_name} := {name};")
        return impls

    if out_type == "bool":
        return [f"{out_name} := true;", f"{out_name} := false;"]

    if out_type.startswith("seq<") and out_type.endswith(">"):
        impls.append(f"{out_name} := [];")
        elt = out_type[4:-1]
        default = _default_value_for_element(elt)
        seq_inputs = [n for n, t in inputs if t.strip().startswith("seq<")]
        for name in seq_inputs:
            impls.append(f"{out_name} := {name};")
            impls.append(f"{out_name} := {name} + {name};")
            impls.append(f"{out_name} := {name} + {name} + {name};")
            if default is not None:
                impls.append(f"{out_name} := seq(|{name}|, i => {default});")
                impls.append(f"{out_name} := seq(2 * |{name}|, i => {default});")
                impls.append(f"{out_name} := seq(3 * |{name}|, i => {default});")
        if default is not None and not seq_inputs:
            impls.append(f"{out_name} := seq(0, i => {default});")
            impls.append(f"{out_name} := seq(1, i => {default});")
        return impls

    # Result<T> wrapper: postconditions of the form `res.Success? ==> P` are
    # vacuously satisfied by `res := Failure`. Where T is a known type, also
    # synthesize Success(trivial) candidates. Assumes the datatype has the
    # constructors `Success(value: T)` and `Failure` (with no fields), the
    # convention used in this benchmark's scaffolding.
    if out_type.startswith("Result<") and out_type.endswith(">"):
        impls.append(f"{out_name} := Failure;")
        inner = out_type[len("Result<"):-1].strip()
        if inner.startswith("seq<") and inner.endswith(">"):
            elt = inner[4:-1]
            default = _default_value_for_element(elt)
            if default is not None:
                impls.append(f"{out_name} := Success([]);")
                seq_inputs = [n for n, t in inputs if t.strip().startswith("seq<")]
                for name in seq_inputs:
                    impls.append(
                        f"{out_name} := Success(seq(|{name}|, i => {default}));"
                    )
        elif inner == "int":
            impls.append(f"{out_name} := Success(0);")
        elif inner == "bool":
            impls.append(f"{out_name} := Success(false);")
        return impls

    return []


def _replace_method_body(
    source: str, method_name: str, new_body_stmt: str
) -> str | None:
    """Replace the named method's body block with a single statement.

    Returns the rewritten source, or None if the method cannot be located.
    """
    lines = source.splitlines(keepends=True)
    decl_re = re.compile(rf"^\s*method\s+{re.escape(method_name)}\b")
    method_start = None
    for i, line in enumerate(lines):
        if decl_re.search(line):
            method_start = i
            break
    if method_start is None:
        return None

    full = "".join(lines)
    offset = sum(len(lines[k]) for k in range(method_start))
    open_idx = full.find("{", offset)
    if open_idx == -1:
        return None
    depth = 0
    close_idx = None
    for j in range(open_idx, len(full)):
        c = full[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                close_idx = j
                break
    if close_idx is None:
        return None

    line_start = full.rfind("\n", 0, open_idx) + 1
    indent = re.match(r"^\s*", full[line_start:open_idx]).group(0) + "  "
    new_body = f"\n{indent}{new_body_stmt}\n{indent[:-2]}"
    return full[: open_idx + 1] + new_body + full[close_idx:]


def run_trivial_sat(file_path: Path | str, method_name: str) -> NoopResult:
    """Run the trivial-impl satisfiability check on one method.

    Parameters
    ----------
    file_path : Path or str
    method_name : str

    Returns
    -------
    NoopResult
    """
    file_path = Path(file_path)
    source = file_path.read_text(encoding="utf-8")
    inputs, outputs = extract_signature(source, method_name)
    if inputs is None or outputs is None:
        return NoopResult(
            file_path=str(file_path),
            method_name=method_name,
            trivial_impls_tried=0,
            error=f"could not parse signature of method {method_name}",
        )

    trivials = synthesize_trivials(inputs, outputs)
    satisfying: list[str] = []
    for impl in trivials:
        new_source = _replace_method_body(source, method_name, impl)
        if new_source is None:
            continue
        res = dafny.verify_source(new_source)
        if res.success:
            satisfying.append(impl)
    return NoopResult(
        file_path=str(file_path),
        method_name=method_name,
        trivial_impls_tried=len(trivials),
        satisfying_impls=satisfying,
    )
