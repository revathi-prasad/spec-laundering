"""Dafny CLI wrapper for verification queries."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of `dafny verify` on a single source file.

    Attributes
    ----------
    success : bool
        True iff Dafny's summary line reports zero errors.
    error_count : int
        Number of errors parsed from the summary line; -1 if not parsed.
    raw_stdout : str
        Full stdout of the dafny invocation.
    raw_stderr : str
        Full stderr of the dafny invocation.
    returncode : int
        Exit code of the dafny process; -1 on timeout.
    """

    success: bool
    error_count: int
    raw_stdout: str
    raw_stderr: str
    returncode: int


def verify_file(path: Path, timeout_s: int = 60) -> VerifyResult:
    """Verify a Dafny source file.

    Parameters
    ----------
    path : Path
        Path to a .dfy file.
    timeout_s : int, default 60
        Maximum seconds to wait for the Dafny process.

    Returns
    -------
    VerifyResult

    Notes
    -----
    Invokes `dafny verify --allow-warnings <path>`. The warning allowance is
    required for files containing `assume {:axiom}`, which Dafny otherwise
    treats as a compilation-failing warning.
    """
    try:
        proc = subprocess.run(
            ["dafny", "verify", "--allow-warnings", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        return VerifyResult(
            success=False,
            error_count=-1,
            raw_stdout=e.stdout or "",
            raw_stderr=(e.stderr or "") + "\ndafny verify timed out",
            returncode=-1,
        )

    stdout = proc.stdout
    success = "0 errors" in stdout and "verified" in stdout
    error_count = -1
    for line in stdout.splitlines():
        if "verified" in line and "errors" in line:
            try:
                tail = line.split("verified,", 1)[1]
                error_count = int(tail.strip().split()[0])
            except (IndexError, ValueError):
                pass
    return VerifyResult(
        success=success,
        error_count=error_count,
        raw_stdout=stdout,
        raw_stderr=proc.stderr,
        returncode=proc.returncode,
    )


def verify_source(source: str, timeout_s: int = 60) -> VerifyResult:
    """Verify a Dafny source string via a temporary file.

    Parameters
    ----------
    source : str
        Dafny source code.
    timeout_s : int, default 60
        Maximum seconds to wait for the Dafny process.

    Returns
    -------
    VerifyResult
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".dfy", delete=False, encoding="utf-8"
    ) as f:
        f.write(source)
        tmp_path = Path(f.name)
    try:
        return verify_file(tmp_path, timeout_s=timeout_s)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
