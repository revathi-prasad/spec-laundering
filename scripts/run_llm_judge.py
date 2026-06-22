#!/usr/bin/env python3
"""Run the LLM-judge baseline over the labeled dataset and score it against the
behavioral labels. Writes results/llm_judge.json."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detector import llm_judge  # noqa: E402
from detector import trivial_gen as tg  # noqa: E402

_SIG = re.compile(r"method\s+(\w+)\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)")
TRIVIAL_CAP = 4
POS = "verified_but_wrong"


def _parse(s):
    return [tuple(x.strip() for x in p.split(":", 1)) for p in s.split(",") if ":" in p]


def main() -> int:
    bank = {p["problem_id"]: p for p in
            json.loads((ROOT / "data" / "problem_bank.json").read_text())["problems"]}
    bodies = {}
    for pid, p in bank.items():
        m = _SIG.search(p["signature"])
        cands = {"reference": p["reference_impl"]}
        for i, b in enumerate(tg.generate_trivials(_parse(m.group(2)), _parse(m.group(3)))[:TRIVIAL_CAP]):
            cands[f"trivial{i}"] = b
        bodies[pid] = cands

    recs = [r for r in json.loads((ROOT / "results" / "dataset.json").read_text())["records"]
            if r["label"] in (POS, "honest_correct")]
    tp = fp = tn = fn = skipped = 0
    out = []
    for r in recs:
        p = bank[r["problem"]]
        body = bodies[r["problem"]].get(r["candidate"])
        verdict = llm_judge.judge(p["problem_nl"], r["weak_spec"], body) if body else None
        pos = r["label"] == POS
        if verdict is None:
            skipped += 1
        else:
            pred = verdict == "wrong"
            tp += pred and pos
            fp += pred and not pos
            fn += (not pred) and pos
            tn += (not pred) and not pos
        out.append({"problem": r["problem"], "candidate": r["candidate"],
                    "label": r["label"], "llm_judge": verdict})

    n = tp + fp + tn + fn
    summary = {
        "n_scored": n, "skipped": skipped,
        "accuracy": round((tp + tn) / n, 3) if n else 0,
        "tpr": round(tp / (tp + fn), 3) if tp + fn else 0,
        "fpr": round(fp / (fp + tn), 3) if fp + tn else 0,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }
    (ROOT / "results" / "llm_judge.json").write_text(
        json.dumps({"summary": summary, "records": out}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
