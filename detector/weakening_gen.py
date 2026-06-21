"""Generate strictly-weaker specs from a strong spec.

Produces candidate laundered specs algorithmically (drop a clause, weaken a
comparator, add a vacuous disjunct), i.e. the adversarial candidate space for
benchmark expansion. Pairing with implementations and the verify/violate/evade
filter are Dafny-gated and live elsewhere.
"""

from __future__ import annotations

import re

# strictly-weakening relational replacements (admit more values)
_WEAKEN = {"==": (">=", "<="), "<": ("<=",), ">": (">=",)}
_RELOP_RE = re.compile(r"(?<![<>=!])(==|<=|>=|<|>)(?![=>])")


def _weaken_comparators(clause: str) -> list[str]:
    out = []
    for m in _RELOP_RE.finditer(clause):
        for repl in _WEAKEN.get(m.group(1), ()):
            out.append(clause[: m.start(1)] + repl + clause[m.end(1) :])
    return out


def propose_weakenings(strong_ensures: list[str]) -> list[list[str]]:
    """Candidate weak specs, each strictly weaker than strong_ensures; deduped,
    excluding the original."""
    cands: list[list[str]] = []
    n = len(strong_ensures)
    for i in range(n):  # drop a clause
        cands.append(strong_ensures[:i] + strong_ensures[i + 1 :])
    for i, c in enumerate(strong_ensures):  # weaken a comparator
        for wc in _weaken_comparators(c):
            cands.append(strong_ensures[:i] + [wc] + strong_ensures[i + 1 :])
    for i, c in enumerate(strong_ensures):  # vacuous disjunct
        cands.append(strong_ensures[:i] + [f"({c}) || true"] + strong_ensures[i + 1 :])

    seen = set()
    out: list[list[str]] = []
    orig = tuple(strong_ensures)
    for c in cands:
        key = tuple(c)
        if key != orig and key not in seen:
            seen.add(key)
            out.append(c)
    return out
