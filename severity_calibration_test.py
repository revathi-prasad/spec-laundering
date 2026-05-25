"""Severity score calibration: compare attack-benchmark and DafnyBench distributions.

Computes the severity score for every entry in the adversarial benchmark and
for a sample of non-adversarial DafnyBench programs. Reports per-entry
severity components and summary distributions so the score's discriminative
behavior can be inspected without committing to a threshold.

The script is intentionally non-prescriptive about threshold selection:
threshold calibration requires labeled data (tight-vs-loose specifications)
that does not exist for Dafny. The distributions are reported for inspection.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from detector import dafny as df
from detector import severity as sev


BENCHMARK = Path("benchmark.json")
DAFNYBENCH_DIR = Path("DafnyBench/DafnyBench/dataset/ground_truth")
SAMPLE_SIZE = 60
MAX_BYTES = 3000

_METHOD_RE = re.compile(r"method\s+(\w+)\s*\([^)]*\)\s*returns\s*\(")


def _adversarial_run() -> list[float]:
    bench = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    entries = bench["entries"]
    print(f"# adversarial benchmark (N={len(entries)})")
    print()
    print(f"{'id':<42} {'a':<6} {'b':<6} {'d':<4} {'severity':<10} consensus")
    print("-" * 80)
    scores: list[float] = []
    for entry in entries:
        sev_res = sev.compute_severity(Path(entry["dafny_file"]), entry["laundered_method"])

        def _fmt(x: float | None) -> str:
            return f"{x:.2f}" if x is not None else "n/a"

        print(
            f"{entry['id']:<42} "
            f"{_fmt(sev_res.component_a):<6} "
            f"{_fmt(sev_res.component_b):<6} "
            f"{_fmt(sev_res.component_d):<4} "
            f"{_fmt(sev_res.severity):<10} "
            f"{sev_res.consensus}"
        )
        if sev_res.severity is not None:
            scores.append(sev_res.severity)
    return scores


def _dafnybench_run() -> list[float]:
    files = sorted(f for f in DAFNYBENCH_DIR.glob("*.dfy") if 200 < f.stat().st_size < MAX_BYTES)
    files = files[:SAMPLE_SIZE]
    print()
    print(f"# non-adversarial DafnyBench sample (N up to {len(files)})")
    print()
    print(f"{'file':<58} {'method':<22} {'a':<6} {'b':<6} {'d':<4} {'severity':<10} consensus")
    print("-" * 120)
    scores: list[float] = []
    for f in files:
        src = f.read_text(encoding="utf-8")
        m = _METHOD_RE.search(src)
        if not m:
            continue
        method = m.group(1)
        if not df.verify_file(f, timeout_s=20).success:
            continue
        sev_res = sev.compute_severity(f, method)

        def _fmt(x: float | None) -> str:
            return f"{x:.2f}" if x is not None else "n/a"

        print(
            f"{f.name[:56]:<58} {method[:20]:<22} "
            f"{_fmt(sev_res.component_a):<6} "
            f"{_fmt(sev_res.component_b):<6} "
            f"{_fmt(sev_res.component_d):<4} "
            f"{_fmt(sev_res.severity):<10} "
            f"{sev_res.consensus}"
        )
        if sev_res.severity is not None:
            scores.append(sev_res.severity)
    return scores


def _summary_stats(label: str, scores: list[float]) -> None:
    if not scores:
        print(f"  {label}: no scored entries")
        return
    s = sorted(scores)
    n = len(s)
    mean = sum(s) / n
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    p25 = s[n // 4]
    p75 = s[(3 * n) // 4]
    above_05 = sum(1 for x in s if x >= 0.5)
    above_07 = sum(1 for x in s if x >= 0.7)
    above_09 = sum(1 for x in s if x >= 0.9)
    print(f"  {label} (N={n}):")
    print(f"    min={s[0]:.2f} p25={p25:.2f} median={median:.2f} mean={mean:.2f} p75={p75:.2f} max={s[-1]:.2f}")
    print(f"    fraction >= 0.5: {above_05}/{n} = {above_05/n:.2%}")
    print(f"    fraction >= 0.7: {above_07}/{n} = {above_07/n:.2%}")
    print(f"    fraction >= 0.9: {above_09}/{n} = {above_09/n:.2%}")


def main() -> int:
    t0 = time.time()
    adv_scores = _adversarial_run()
    dbench_scores = _dafnybench_run()
    print()
    print("# severity-score distributions")
    print()
    _summary_stats("adversarial benchmark", adv_scores)
    _summary_stats("non-adversarial DafnyBench", dbench_scores)
    print()
    print(f"elapsed: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
