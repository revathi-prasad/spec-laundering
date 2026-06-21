"""Type-driven trivial-implementation generator.

Candidates derived from the method signature only (no benchmark-specific
lengths/values, unlike trivial_sat's hand catalog). Single-output methods only.
"""

from __future__ import annotations

_ELT_DEFAULT = {"int": "0", "nat": "0", "bool": "false", "char": "'a'"}


def _trivial_values(ty: str, inputs: list[tuple[str, str]]) -> list[str]:
    ty = ty.strip()
    if ty in ("int", "nat"):
        vals = ["0", "1"] + (["-1"] if ty == "int" else [])
        vals += [n for n, t in inputs if t.strip() in ("int", "nat")]
        return vals
    if ty == "bool":
        return ["true", "false"]
    if ty == "char":
        return ["'a'"]
    if ty.startswith("seq<") and ty.endswith(">"):
        elt = ty[4:-1].strip()
        d = _ELT_DEFAULT.get(elt)
        seq_inputs = [n for n, t in inputs if t.strip().startswith("seq<")]
        vals = ["[]"] + seq_inputs
        if d is not None:
            vals += [f"seq(0, i => {d})", f"seq(1, i => {d})"]
            vals += [f"seq(|{n}|, i => {d})" for n in seq_inputs]
        return vals
    if ty.startswith("Result<") and ty.endswith(">"):
        inner = ty[len("Result<") : -1].strip()
        return ["Failure"] + [f"Success({v})" for v in _trivial_values(inner, inputs)]
    return []


def generate_trivials(
    inputs: list[tuple[str, str]], outputs: list[tuple[str, str]]
) -> list[str]:
    """Assignment statements for a single-output method; [] otherwise."""
    if not outputs or len(outputs) != 1:
        return []
    name, ty = outputs[0]
    return [f"{name} := {v};" for v in _trivial_values(ty.strip(), inputs)]
