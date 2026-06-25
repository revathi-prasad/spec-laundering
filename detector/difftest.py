"""Differential testing: is a candidate impl behaviorally wrong vs a reference?

Runs both on generated inputs via `dafny run --target:py` and compares outputs.
Independent of the detector (the ground-truth label for the dataset).
"""

from __future__ import annotations

import itertools
import re
import subprocess
import tempfile
from pathlib import Path

_SIG = re.compile(r"method\s+(\w+)\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)")
_POOL = {
    "int": ["0", "1", "-1", "5", "2", "10", "-7"],
    "nat": ["0", "1", "2", "5", "10"],
    "bool": ["true", "false"],
}
# all seqs non-empty so a `requires |s| > 0` precondition never blocks the run
_SEQ_POOL = ["[1]", "[1, 2, 3]", "[3, 1, 2]", "[5, 4, 3, 2, 1]", "[2, 2]"]


def _params(s: str) -> list[tuple[str, str]]:
    out = []
    for part in s.split(","):
        part = part.strip()
        if ":" in part:
            n, t = part.split(":", 1)
            out.append((n.strip(), t.strip()))
    return out


def _pool(ty: str) -> list[str] | None:
    ty = ty.strip()
    if ty in _POOL:
        return _POOL[ty]
    if ty.startswith("seq<"):
        return _SEQ_POOL
    return None


def gen_inputs(params: list[tuple[str, str]], cap: int = 25) -> list[str]:
    pools = [_pool(t) for _, t in params]
    if not pools or any(p is None for p in pools):
        return []
    return [", ".join(t) for t in list(itertools.product(*pools))[:cap]]


def build_harness(signature, requires, ref_impl, cand_impl, inputs) -> str:
    m = _SIG.search(signature)
    params_s, out_s = m.group(2), m.group(3)
    req = "".join("\n  requires " + r for r in (requires or []))
    blocks = []
    for args in inputs:
        blocks.append(
            "  { var r := Ref(" + args + "); var c := Cand(" + args + ");"
            ' if r != c { print "MISMATCH in=(' + args + ') ref=", r, " cand=", c, "\\n"; } }'
        )
    body = "\n".join(blocks)
    return (
        "method Ref(" + params_s + ") returns (" + out_s + ")" + req + "\n{ " + ref_impl + " }\n\n"
        "method Cand(" + params_s + ") returns (" + out_s + ")" + req + "\n{ " + cand_impl + " }\n\n"
        "method Main() {\n" + body + "\n}\n"
    )


def _dafny_run(src: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "prog.dfy"
        p.write_text(src)
        try:
            proc = subprocess.run(
                ["dafny", "run", "--target:py", str(p)],
                capture_output=True, text=True, timeout=180, cwd=d,
            )
        except subprocess.TimeoutExpired:
            return -1, ""
        return proc.returncode, proc.stdout


def find_counterexamples(signature, requires, ref_impl, cand_impl, _run=None):
    """Compare cand_impl against ref_impl on generated inputs.

    Returns (status, examples):
      status   'regression' | 'equivalent' | 'inconclusive'
      examples list of mismatch lines (input + both outputs).
    """
    params = _params(_SIG.search(signature).group(2))
    inputs = gen_inputs(params)
    if not inputs:
        return "inconclusive", []
    src = build_harness(signature, requires, ref_impl, cand_impl, inputs)
    rc, out = (_run or _dafny_run)(src)
    if rc != 0:
        return "inconclusive", []
    examples = [ln for ln in out.splitlines() if ln.startswith("MISMATCH")]
    return ("regression" if examples else "equivalent"), examples


def differential_test(signature, requires, ref_impl, cand_impl, _run=None) -> bool | None:
    """True = behaviorally wrong, False = matches reference, None = inconclusive
    (unsupported types or did not run)."""
    status, _ = find_counterexamples(signature, requires, ref_impl, cand_impl, _run)
    return {"regression": True, "equivalent": False, "inconclusive": None}[status]
