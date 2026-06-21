#!/usr/bin/env python3
"""Enumerate the algorithmic weakening-candidate space over the problem bank.
Writes results/candidate_space.json. Pairing each candidate weak spec with a
backdoor impl and the verify/violate/evade filter are Dafny-gated."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detector import weakening_gen as wg  # noqa: E402


def main() -> int:
    bank = json.loads((ROOT / "data" / "problem_bank.json").read_text())
    out = {"problems": [], "total_candidates": 0}
    for p in bank["problems"]:
        cands = wg.propose_weakenings(p["strong_spec"])
        out["problems"].append(
            {
                "problem_id": p["problem_id"],
                "strong_spec": p["strong_spec"],
                "num_candidates": len(cands),
                "candidate_weak_specs": cands,
            }
        )
        out["total_candidates"] += len(cands)

    (ROOT / "results" / "candidate_space.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    print(
        f"problems: {len(out['problems'])}  "
        f"total weakening candidates: {out['total_candidates']}"
    )
    for pr in out["problems"]:
        print(f"  {pr['problem_id']}: {pr['num_candidates']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
