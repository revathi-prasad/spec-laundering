"""Migration regression detector: flag a new impl that diverges from a trusted
old impl. The reference is a total function (the old code), so no spec is needed
-- the deployable, reference-free counterpart to coupling.

Reuses the differential-testing engine; reports counterexamples.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import difftest

_SIG = re.compile(r"method\s+(\w+)\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)")


@dataclass
class MigrationReport:
    method: str
    status: str  # 'regression' | 'equivalent' | 'inconclusive'
    counterexamples: list[str] = field(default_factory=list)

    @property
    def regressed(self) -> bool:
        return self.status == "regression"


def extract_method_body(source: str, method_name: str) -> str | None:
    """Brace-matched body of a named method (statements between the braces)."""
    m = re.search(rf"method\s+{re.escape(method_name)}\b", source)
    if not m:
        return None
    start = source.find("{", m.end())
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:i].strip()
    return None


def check_migration(signature, requires, old_impl, new_impl, _run=None) -> MigrationReport:
    method = _SIG.search(signature).group(1)
    status, examples = difftest.find_counterexamples(
        signature, requires, old_impl, new_impl, _run=_run
    )
    return MigrationReport(method=method, status=status, counterexamples=examples)


def check_migration_files(old_source, new_source, signature, requires, method_name,
                          _run=None) -> MigrationReport:
    """Same, taking two full Dafny sources and pulling the method body from each."""
    old = extract_method_body(old_source, method_name)
    new = extract_method_body(new_source, method_name)
    if old is None or new is None:
        return MigrationReport(method=method_name, status="inconclusive")
    return check_migration(signature, requires, old, new, _run=_run)
