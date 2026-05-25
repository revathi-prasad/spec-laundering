"""Command-line driver: run the implemented checks across a benchmark file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import check_c_noop_sat as check_c
from . import check_d_mutation_kill as check_d
from . import check_e_equiv_filter as check_e
from . import check_f_assume as check_f
from . import severity as sev


KILL_THRESHOLD = 0.3


def _load_benchmark(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_dfy(repo_root: Path, rel: str) -> Path:
    return (repo_root / rel).resolve()


def run(benchmark_path: Path, repo_root: Path) -> int:
    bench = _load_benchmark(benchmark_path)
    entries = bench["entries"]
    print(f"# detector run on {len(entries)} benchmark entries")
    print()
    hdr = (
        f"{'id':<40} {'attack':<22} "
        f"{'c':<6} {'d':<6} {'f':<4} {'severity':<10} {'consensus':<10}"
    )
    print(hdr)
    print("-" * len(hdr))

    for entry in entries:
        dfy = _resolve_dfy(repo_root, entry["dafny_file"])
        method = entry["laundered_method"]
        sev_res = sev.compute_severity(dfy, method)

        def _fmt(x: float | None) -> str:
            return f"{x:.2f}" if x is not None else "n/a"

        print(
            f"{entry['id']:<40} {entry['attack_type']:<22} "
            f"{_fmt(sev_res.component_c):<6} "
            f"{_fmt(sev_res.component_d):<6} "
            f"{_fmt(sev_res.component_f):<4} "
            f"{_fmt(sev_res.severity):<10} "
            f"{sev_res.consensus:<10}"
        )
    print()
    print("note: severity is a measure in [0,1], not a binary verdict.")
    print("      threshold selection requires labeled calibration data not available here.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run the detector across a benchmark file."
    )
    ap.add_argument(
        "--benchmark", default="benchmark.json", help="Path to benchmark.json"
    )
    ap.add_argument(
        "--repo-root", default=".", help="Repository root for resolving dafny_file paths"
    )
    args = ap.parse_args(argv)
    return run(Path(args.benchmark), Path(args.repo_root))


if __name__ == "__main__":
    sys.exit(main())
