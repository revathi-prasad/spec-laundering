"""Syntactic scan for assume-based proof bypass patterns in Dafny source.

Dafny statements and attributes that admit a verification obligation without
proof:

- `assume <expr>;`              advisory warning under Dafny 4 default settings
- `assume {:axiom} <expr>;`     warning suppressed by annotation
- `lemma {:axiom} L(...) ...`   lemma declared as axiom; body not required
- `{:verify false}` attribute   on method or lemma; verification disabled

The patterns are not detectable by spec mutation testing because the
weakening lives outside the `ensures` block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AssumeFinding:
    """One occurrence of a flagged pattern."""

    pattern: str
    line_no: int
    line_text: str


@dataclass
class CheckFResult:
    """Aggregated findings for one file."""

    file_path: str
    findings: list[AssumeFinding] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return len(self.findings) > 0


_BARE_ASSUME = re.compile(r"\bassume\s+(?!\{:axiom\})")
_AXIOM_ASSUME = re.compile(r"\bassume\s+\{:axiom\}")
_AXIOM_LEMMA = re.compile(r"\blemma\s+\{:axiom\}")
_VERIFY_FALSE = re.compile(r"\{:verify\s+false\}")


def _strip_comments(source: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", no_block)


def scan_source(source: str, file_path: str = "<string>") -> CheckFResult:
    """Scan a Dafny source string.

    Parameters
    ----------
    source : str
        Dafny source code.
    file_path : str
        Label used in the result for traceability.

    Returns
    -------
    CheckFResult
    """
    cleaned = _strip_comments(source)
    result = CheckFResult(file_path=file_path)
    for line_no, line in enumerate(cleaned.splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        if _AXIOM_ASSUME.search(line):
            result.findings.append(AssumeFinding("axiom_assume", line_no, text))
            continue
        if _BARE_ASSUME.search(line):
            result.findings.append(AssumeFinding("bare_assume", line_no, text))
        if _AXIOM_LEMMA.search(line):
            result.findings.append(AssumeFinding("axiom_lemma", line_no, text))
        if _VERIFY_FALSE.search(line):
            result.findings.append(AssumeFinding("verify_false", line_no, text))
    return result


def scan_file(path: Path | str) -> CheckFResult:
    """Scan a Dafny file.

    Parameters
    ----------
    path : Path or str
        Path to a .dfy file.

    Returns
    -------
    CheckFResult
    """
    path = Path(path)
    return scan_source(path.read_text(encoding="utf-8"), file_path=str(path))
