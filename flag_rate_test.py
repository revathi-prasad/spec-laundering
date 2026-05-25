"""Flag-rate measurement on non-adversarial DafnyBench programs.

DafnyBench (Loughridge et al., arXiv:2406.08467) ships verified Dafny
programs intended for evaluating LLM hint-completion. The dataset is not
labeled by specification quality; the ``ground_truth`` directory guarantees
only that each (spec, impl) pair verifies. The flag rate reported here
therefore combines:

  (i)  detector false positives on tight honest specs, and
  (ii) detector true positives on honest but loose specs analogous to those
       IronSpec (Goldweber et al., OSDI 2024) reports for real-world Dafny.

Manual triage is required to separate (i) and (ii); this script does not
attempt it.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from detector import check_a_noop_sat as ca
from detector import check_b_mutation_kill as cb
from detector import check_d_assume as cd
from detector import dafny as df

BENCH_DIR = Path("DafnyBench/DafnyBench/dataset/ground_truth")
MAX_FILE_BYTES = 3000
SAMPLE_SIZE = 60
KILL_THRESHOLD = 0.3


_METHOD_RE = re.compile(r"method\s+(\w+)\s*\([^)]*\)\s*returns\s*\(")


def _pick_files() -> list[Path]:
    files = [
        f for f in BENCH_DIR.glob("*.dfy") if 200 < f.stat().st_size < MAX_FILE_BYTES
    ]
    files.sort()
    return files[:SAMPLE_SIZE]


def _first_method_with_returns(source: str) -> str | None:
    m = _METHOD_RE.search(source)
    return m.group(1) if m else None


def _baseline_verifies(path: Path) -> bool:
    return df.verify_file(path, timeout_s=20).success


def main() -> int:
    if not BENCH_DIR.exists():
        print(f"DafnyBench not found at {BENCH_DIR}", file=sys.stderr)
        return 2

    files = _pick_files()
    print(f"# flag-rate test on {len(files)} DafnyBench programs (non-adversarial)")
    print()
    hdr = (
        f"{'file':<58} {'method':<22} {'baseline':<10} "
        f"{'a flag':<8} {'b kill':<10} {'d flag':<8} verdict"
    )
    print(hdr)
    print("-" * len(hdr))

    counts = {"checked": 0, "a": 0, "b": 0, "d": 0, "any": 0, "skipped": 0}
    t0 = time.time()
    for f in files:
        src = f.read_text(encoding="utf-8")
        method = _first_method_with_returns(src)
        if method is None:
            print(f"{f.name[:56]:<58} {'-':<22} {'no-method':<10}")
            counts["skipped"] += 1
            continue
        if not _baseline_verifies(f):
            print(f"{f.name[:56]:<58} {method[:20]:<22} {'no-verify':<10}")
            counts["skipped"] += 1
            continue

        counts["checked"] += 1
        a_res = ca.run_check_a(f, method)
        b_res = cb.run_check_b(f, method)
        d_res = cd.scan_file(f)

        a_flag = a_res.flagged
        b_flag = b_res.mutants_tried > 0 and b_res.kill_score < KILL_THRESHOLD
        d_flag = d_res.flagged
        any_flag = a_flag or b_flag or d_flag

        if a_flag:
            counts["a"] += 1
        if b_flag:
            counts["b"] += 1
        if d_flag:
            counts["d"] += 1
        if any_flag:
            counts["any"] += 1

        verdict = "flagged" if any_flag else "clean"
        print(
            f"{f.name[:56]:<58} {method[:20]:<22} {'ok':<10} "
            f"{('1' if a_flag else '0'):<8} "
            f"{(f'{b_res.kill_score:.2f}' if b_res.mutants_tried else 'n/a'):<10} "
            f"{('1' if d_flag else '0'):<8} {verdict}"
        )

    print()
    print(f"elapsed: {time.time() - t0:.1f}s")
    print()
    print("summary:")
    print(f"  files attempted    : {len(files)}")
    print(f"  files skipped      : {counts['skipped']}")
    print(f"  files checked      : {counts['checked']}")
    if counts["checked"]:
        n = counts["checked"]
        print(f"  check (a) flag rate: {counts['a']}/{n} = {counts['a']/n:.2%}")
        print(f"  check (b) flag rate: {counts['b']}/{n} = {counts['b']/n:.2%}")
        print(f"  check (d) flag rate: {counts['d']}/{n} = {counts['d']/n:.2%}")
        print(f"  combined flag rate : {counts['any']}/{n} = {counts['any']/n:.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
