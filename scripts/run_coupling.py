#!/usr/bin/env python3
"""Run coupling over benchmark.json. Full verdicts require the dafny CLI;
without it, emits the static portion (family + namespace guard) and marks
verdicts PENDING_DAFNY. Writes results/coupling_benchmark.json."""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detector import coupling as coup  # noqa: E402

FAMILY = {
    "drop_conjunct": "A_weakening",
    "weaken_comparator": "A_weakening",
    "narrow_quantifier": "A_weakening",
    "vacuous_disjunct": "A_weakening",
    "assumed_lemma": "B_proof",
    "extern_boundary_laundering": "C_incomplete",
}


def main() -> int:
    bench = json.loads((ROOT / "benchmark.json").read_text())
    have_dafny = shutil.which("dafny") is not None
    out = {"dafny_available": have_dafny, "entries": []}

    for e in bench["entries"]:
        dfy = ROOT / e["dafny_file"]
        rec = {"id": e["id"], "family": FAMILY.get(e["attack_type"], "?")}

        if have_dafny:
            r = coup.run_coupling(dfy, e["laundered_method"], e["original_ensures"])
            rec.update(
                verdict=r.verdict,
                dropped_D=r.dropped_D,
                V_proof=r.violated_V_proof,
                V_semantic=r.violated_V_semantic,
                surgical=r.surgical_score,
                foreign=r.foreign_identifiers,
            )
        else:
            src = dfy.read_text()
            inp, outp = coup.triv.extract_signature(src, e["laundered_method"])
            if inp is None:
                rec.update(verdict="error", foreign=["<signature parse failed>"])
            else:
                foreign = coup.foreign_identifiers(
                    e["original_ensures"],
                    [n for n, _ in inp],
                    [n for n, _ in outp],
                    src,
                )
                rec.update(
                    verdict="incomparable" if foreign else "PENDING_DAFNY",
                    foreign=foreign,
                )
        out["entries"].append(rec)

    res = ROOT / "results" / "coupling_benchmark.json"
    res.parent.mkdir(exist_ok=True)
    res.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
