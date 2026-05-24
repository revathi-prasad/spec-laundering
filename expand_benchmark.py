"""Programmatic generation of laundered (spec, impl) pairs from DafnyBench.

For each candidate DafnyBench program with an extractable single-method
signature and ensures clauses, apply a panel of attack mutators to the
postcondition. For each mutated postcondition, try each candidate trivial
implementation from check (c)'s catalog as the backdoor. Accept the
generated entry iff:

  1. Dafny verifies the (laundered_spec, backdoor_impl) pair (the laundering
     must produce a verifying program; otherwise nothing is laundered).
  2. The backdoor does NOT satisfy the original spec (otherwise the
     "laundering" is vacuous — any implementation satisfying the original
     spec also satisfies a weaker spec).

Accepted entries are written to ``generated_attacks/`` and indexed in
``benchmark_expanded.json``.

Mutators implemented:
  - vacuous_disjunct  : append ``|| true`` to the first ensures clause
  - drop_conjunct     : drop the last clause (requires >= 2 clauses)
  - weaken_comparator : replace the first ``==`` in any clause with ``>=``
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from detector import check_c_noop_sat as cc
from detector import check_d_mutation_kill as cd
from detector import dafny


OUTPUT_DIR = Path("generated_attacks")
OUTPUT_JSON = Path("benchmark_expanded.json")
DAFNYBENCH_DIR = Path("DafnyBench/DafnyBench/dataset/ground_truth")
MAX_FILES = 80
MAX_ENTRIES = 60
BASELINE_TIMEOUT_S = 20
VERIFY_TIMEOUT_S = 30


def att_vacuous_disjunct(ensures: list[str]) -> list[str] | None:
    if not ensures:
        return None
    return [f"({ensures[0]}) || true"] + ensures[1:]


def att_drop_conjunct(ensures: list[str]) -> list[str] | None:
    if len(ensures) < 2:
        return None
    return ensures[:-1]


def att_weaken_comparator(ensures: list[str]) -> list[str] | None:
    eq_re = re.compile(r"(?<![<>=!])==(?!=)")
    for i, clause in enumerate(ensures):
        if eq_re.search(clause):
            new = eq_re.sub(">=", clause, count=1)
            if new != clause:
                return ensures[:i] + [new] + ensures[i + 1 :]
    return None


ATTACK_FNS = {
    "vacuous_disjunct": att_vacuous_disjunct,
    "drop_conjunct": att_drop_conjunct,
    "weaken_comparator": att_weaken_comparator,
}


_METHOD_RE = re.compile(r"method\s+(\w+)\s*\([^)]*\)\s*returns\s*\(")


def try_generate_entry(
    source_file: Path,
    method: str,
    attack_name: str,
    attack_fn,
    output_path: Path,
) -> dict | None:
    source = source_file.read_text(encoding="utf-8")
    inputs, outputs = cc.extract_signature(source, method)
    ensures_lines, ensures = cd.extract_ensures_for_method(source, method)

    if not inputs or not outputs or not ensures:
        return None

    laundered_ensures = attack_fn(ensures)
    if laundered_ensures is None or laundered_ensures == ensures:
        return None

    spliced = cd._splice_ensures(source, ensures_lines, laundered_ensures)

    for trivial in cc.synthesize_trivials(inputs, outputs):
        new_source = cc._replace_method_body(spliced, method, trivial)
        if new_source is None:
            continue

        res = dafny.verify_source(new_source, timeout_s=VERIFY_TIMEOUT_S)
        if not res.success:
            continue

        # Backdoor must NOT satisfy the original (unmodified) spec.
        check_source = cc._replace_method_body(source, method, trivial)
        if check_source is None:
            continue
        check_res = dafny.verify_source(check_source, timeout_s=VERIFY_TIMEOUT_S)
        if check_res.success:
            continue

        output_path.write_text(new_source, encoding="utf-8")
        return {
            "attack_type": attack_name,
            "base_problem": method,
            "source_file": source_file.name,
            "original_ensures": ensures,
            "laundered_ensures": laundered_ensures,
            "backdoor_impl": trivial,
        }
    return None


def main() -> int:
    if not DAFNYBENCH_DIR.exists():
        print(f"DafnyBench not found at {DAFNYBENCH_DIR}", file=sys.stderr)
        return 2
    OUTPUT_DIR.mkdir(exist_ok=True)

    files = [
        f
        for f in DAFNYBENCH_DIR.glob("*.dfy")
        if 200 < f.stat().st_size < 2500
    ]
    files.sort()
    files = files[:MAX_FILES]

    print(f"# scanning {len(files)} DafnyBench programs")
    entries: list[dict] = []
    t0 = time.time()
    for f in files:
        src = f.read_text(encoding="utf-8")
        m = _METHOD_RE.search(src)
        if not m:
            continue
        method = m.group(1)
        if not dafny.verify_file(f, timeout_s=BASELINE_TIMEOUT_S).success:
            continue

        for attack_name, attack_fn in ATTACK_FNS.items():
            out_filename = f"{f.stem[:60]}_{attack_name}.dfy"
            out_path = OUTPUT_DIR / out_filename
            entry = try_generate_entry(f, method, attack_name, attack_fn, out_path)
            if entry is not None:
                entry["id"] = f"{f.stem[:50]}_{attack_name}"
                entry["dafny_file"] = f"generated_attacks/{out_filename}"
                entry["laundered_method"] = method
                entries.append(entry)
                print(f"  + {entry['id']}  ({len(entries)}/{MAX_ENTRIES})")
                if len(entries) >= MAX_ENTRIES:
                    break
        if len(entries) >= MAX_ENTRIES:
            break

    OUTPUT_JSON.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "description": (
                    "Programmatically-generated benchmark entries derived from DafnyBench."
                    " Each entry is a (laundered_spec, backdoor_impl) pair where the laundered"
                    " spec verifies and the backdoor implementation does not satisfy the"
                    " original spec."
                ),
                "entries": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(f"generated {len(entries)} entries in {time.time() - t0:.1f}s")
    print(f"written to {OUTPUT_JSON} and {OUTPUT_DIR}/")
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["attack_type"]] = counts.get(e["attack_type"], 0) + 1
    for at, n in sorted(counts.items()):
        print(f"  {at:<20} : {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
