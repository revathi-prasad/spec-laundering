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
        f"{'id':<40} {'attack':<22} {'check_c':<10} "
        f"{'d_raw':<13} {'d_filtered':<13} {'check_f':<8} verdict"
    )
    print(hdr)
    print("-" * len(hdr))

    for entry in entries:
        dfy = _resolve_dfy(repo_root, entry["dafny_file"])
        method = entry["laundered_method"]

        c_res = check_c.run_check_c(dfy, method)
        d_res = check_d.run_check_d(dfy, method)
        e_res = check_e.run_check_e(dfy, method, raw_result=d_res)
        f_res = check_f.scan_file(dfy)

        verdict_parts: list[str] = []
        if c_res.flagged:
            verdict_parts.append(
                f"noop({len(c_res.satisfying_impls)}/{c_res.trivial_impls_tried})"
            )
        if (
            e_res.filtered_tried > 0
            and e_res.filtered_kill_score < KILL_THRESHOLD
        ):
            verdict_parts.append(f"low_kill={e_res.filtered_kill_score:.2f}")
        if f_res.flagged:
            verdict_parts.append(f"assume({len(f_res.findings)})")
        verdict = "LAUNDERED" if verdict_parts else "clean"
        flags = ",".join(verdict_parts) if verdict_parts else "-"

        c_str = (
            f"{len(c_res.satisfying_impls)}/{c_res.trivial_impls_tried}"
            if c_res.trivial_impls_tried
            else "n/a"
        )
        d_raw_str = (
            f"{d_res.mutants_killed}/{d_res.mutants_tried}={d_res.kill_score:.2f}"
            if d_res.mutants_tried
            else "n/a"
        )
        d_filt_str = (
            f"{e_res.filtered_killed}/{e_res.filtered_tried}={e_res.filtered_kill_score:.2f}"
            if e_res.filtered_tried
            else "n/a"
        )
        print(
            f"{entry['id']:<40} {entry['attack_type']:<22} "
            f"{c_str:<10} {d_raw_str:<13} {d_filt_str:<13} "
            f"{'FLAG' if f_res.flagged else '-':<8} {verdict} ({flags})"
        )
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
