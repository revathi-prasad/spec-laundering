"""Cross-tool evaluation: SpecLaunder detector vs reproduced IronSpec ASC.

Runs both detectors over:

1. The 5-entry SpecLaunder benchmark of laundered (spec, impl) pairs.
2. A sample of non-adversarial DafnyBench programs.

Reports per-attack outcomes and aggregate flag rates so the two tools can be
compared on the same inputs.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from detector import check_c_noop_sat as cc
from detector import check_d_mutation_kill as cd
from detector import check_e_equiv_filter as ce
from detector import check_f_assume as cf
from detector import dafny as df
from detector import ironspec_asc_repro as asc

KILL_THRESHOLD = 0.3
BENCHMARK = Path("benchmark.json")
DAFNYBENCH_DIR = Path("DafnyBench/DafnyBench/dataset/ground_truth")
DAFNYBENCH_SAMPLE_SIZE = 60
DAFNYBENCH_MAX_BYTES = 3000

_METHOD_RE = re.compile(r"method\s+(\w+)\s*\([^)]*\)\s*returns\s*\(")


def _our_flag(dfy: Path, method: str) -> tuple[bool, list[str]]:
    """Run the SpecLaunder detector on one method. Returns (flagged, reasons)."""
    reasons: list[str] = []
    c_res = cc.run_check_c(dfy, method)
    d_res = cd.run_check_d(dfy, method)
    e_res = ce.run_check_e(dfy, method, raw_result=d_res)
    f_res = cf.scan_file(dfy)
    if c_res.flagged:
        reasons.append(f"noop({len(c_res.satisfying_impls)}/{c_res.trivial_impls_tried})")
    if e_res.filtered_tried and e_res.filtered_kill_score < KILL_THRESHOLD:
        reasons.append(f"low_kill={e_res.filtered_kill_score:.2f}")
    if f_res.flagged:
        reasons.append(f"assume({len(f_res.findings)})")
    return (bool(reasons), reasons)


def _asc_flag(dfy: Path, method: str) -> tuple[bool, str]:
    res = asc.run_asc(dfy, method)
    if not res.has_inputs:
        return (False, "no-inputs")
    if res.high_flag:
        return (True, f"unreferenced_inputs={res.unreferenced_inputs}")
    return (False, f"referenced={res.referenced_inputs}")


def _benchmark_table() -> dict[str, dict[str, bool]]:
    bench = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    entries = bench["entries"]
    print("# Cross-tool comparison: benchmark (laundered specs)")
    print()
    hdr = f"{'id':<40} {'attack':<22} {'our_detector':<15} {'ironspec_asc':<15} caught_by"
    print(hdr)
    print("-" * len(hdr))

    summary: dict[str, dict[str, bool]] = {}
    for entry in entries:
        dfy = Path(entry["dafny_file"])
        method = entry["laundered_method"]
        ours, our_reasons = _our_flag(dfy, method)
        ascf, asc_reason = _asc_flag(dfy, method)
        caught = []
        if ours:
            caught.append("ours")
        if ascf:
            caught.append("asc")
        if not caught:
            caught = ["none"]
        print(
            f"{entry['id']:<40} {entry['attack_type']:<22} "
            f"{('LAUNDERED' if ours else 'clean'):<15} "
            f"{('HIGH' if ascf else 'clean'):<15} {','.join(caught)}"
        )
        summary[entry["id"]] = {"ours": ours, "asc": ascf}
    return summary


def _dafnybench_sample() -> list[Path]:
    files = [
        f
        for f in DAFNYBENCH_DIR.glob("*.dfy")
        if 200 < f.stat().st_size < DAFNYBENCH_MAX_BYTES
    ]
    files.sort()
    return files[:DAFNYBENCH_SAMPLE_SIZE]


def _dafnybench_table() -> dict[str, int]:
    files = _dafnybench_sample()
    print(f"# Cross-tool flag rates on {len(files)} non-adversarial DafnyBench programs")
    print()
    hdr = f"{'file':<58} {'method':<22} {'our_detector':<15} {'ironspec_asc':<15}"
    print(hdr)
    print("-" * len(hdr))

    counts = {"checked": 0, "ours": 0, "asc": 0, "either": 0, "both": 0}
    for f in files:
        src = f.read_text(encoding="utf-8")
        m = _METHOD_RE.search(src)
        if not m:
            continue
        method = m.group(1)
        if not df.verify_file(f, timeout_s=20).success:
            continue
        counts["checked"] += 1
        ours, _ = _our_flag(f, method)
        ascf, _ = _asc_flag(f, method)
        if ours:
            counts["ours"] += 1
        if ascf:
            counts["asc"] += 1
        if ours or ascf:
            counts["either"] += 1
        if ours and ascf:
            counts["both"] += 1
        print(
            f"{f.name[:56]:<58} {method[:20]:<22} "
            f"{('flag' if ours else 'clean'):<15} "
            f"{('flag' if ascf else 'clean'):<15}"
        )

    print()
    n = counts["checked"]
    print(f"summary on {n} programs:")
    if n:
        print(f"  our detector flag rate : {counts['ours']}/{n} = {counts['ours']/n:.2%}")
        print(f"  ironspec asc flag rate : {counts['asc']}/{n} = {counts['asc']/n:.2%}")
        print(f"  either flagged         : {counts['either']}/{n} = {counts['either']/n:.2%}")
        print(f"  both flagged           : {counts['both']}/{n} = {counts['both']/n:.2%}")
    return counts


def main() -> int:
    t0 = time.time()
    _benchmark_table()
    print()
    _dafnybench_table()
    print(f"\nelapsed: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
