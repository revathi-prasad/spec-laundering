#!/usr/bin/env python3
"""Internal ablation on the labeled dataset: coupling vs the mutation check.
Reads results/dataset.json, writes results/ablation.json."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detector import calibration as cal  # noqa: E402

POS = "verified_but_wrong"


def confusion(records, predict):
    tp = fp = tn = fn = 0
    for r in records:
        pos = r["label"] == POS
        pred = predict(r)
        tp += pred and pos
        fp += pred and not pos
        fn += (not pred) and pos
        tn += (not pred) and not pos
    n = tp + fp + tn + fn
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": round((tp + tn) / n, 3) if n else 0,
        "tpr": round(tp / (tp + fn), 3) if tp + fn else 0,
        "fpr": round(fp / (fp + tn), 3) if fp + tn else 0,
    }


def main() -> int:
    d = json.loads((ROOT / "results" / "dataset.json").read_text())
    recs = [r for r in d["records"] if r["label"] in (POS, "honest_correct")]

    coupling = confusion(recs, lambda r: r["coupling"] != "honest")

    # mutation: low kill = suspicious; score = 1 - kill (None kill -> 0, no signal)
    scored = [(1 - (r["mutation_kill"] if r["mutation_kill"] is not None else 1.0),
               r["label"] == POS) for r in recs]
    b = cal.best_threshold(scored)
    n = b.tp + b.fp + b.tn + b.fn
    mutation_best = {
        "threshold_on_(1-kill)": round(b.threshold, 3),
        "accuracy": round((b.tp + b.tn) / n, 3),
        "tpr": round(b.tpr, 3), "fpr": round(b.fpr, 3),
    }
    mutation_fixed = confusion(
        recs, lambda r: r["mutation_kill"] is not None and r["mutation_kill"] < 0.3
    )

    out = {
        "n": len(recs),
        "coupling": coupling,
        "mutation_best_threshold": mutation_best,
        "mutation_fixed_kill_lt_0.3": mutation_fixed,
    }
    (ROOT / "results" / "ablation.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
