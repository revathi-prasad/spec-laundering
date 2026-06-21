#!/usr/bin/env python3
"""A-evade loop / labeled dataset over the problem bank.

For each (weak spec, candidate impl): verifies? behaviorally-wrong (difftest)?
coupling verdict? Labels via the 2x2 (independent of the detector). Flags
evasions = verified_but_wrong that coupling rates honest. Writes
results/dataset.json."""

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detector import coupling as coup  # noqa: E402
from detector import dafny  # noqa: E402
from detector import dataset as ds  # noqa: E402
from detector import difftest  # noqa: E402
from detector import mutation as mut  # noqa: E402
from detector import trivial_gen as tg  # noqa: E402
from detector import weakening_gen as wg  # noqa: E402

_SIG = re.compile(r"method\s+(\w+)\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)")
WEAK_CAP = 5
TRIVIAL_CAP = 4


def _parse(s):
    out = []
    for part in s.split(","):
        part = part.strip()
        if ":" in part:
            n, t = part.split(":", 1)
            out.append((n.strip(), t.strip()))
    return out


def _method_src(sig, requires, ensures, body):
    req = "".join("\n  requires " + r for r in requires)
    ens = "".join("\n  ensures " + e for e in ensures)
    return sig + req + ens + "\n{ " + body + " }\n"


def main() -> int:
    bank = json.loads((ROOT / "data" / "problem_bank.json").read_text())
    records, evasions = [], []

    for p in bank["problems"]:
        sig, req, strong, ref = p["signature"], p.get("requires", []), p["strong_spec"], p["reference_impl"]
        m = _SIG.search(sig)
        name, inputs, outputs = m.group(1), _parse(m.group(2)), _parse(m.group(3))
        cands = [("reference", ref)] + [
            (f"trivial{i}", b) for i, b in enumerate(tg.generate_trivials(inputs, outputs)[:TRIVIAL_CAP])
        ]
        specs = [strong] + wg.propose_weakenings(strong)[:WEAK_CAP]

        for ws in specs:
            for cname, body in cands:
                src = _method_src(sig, req, ws, body)
                if not dafny.verify_source(src).success:
                    continue  # not a valid (verifying) pair
                wrong = difftest.differential_test(sig, req, ref, body)
                correct = (not wrong) if wrong is not None else None
                with tempfile.NamedTemporaryFile("w", suffix=".dfy", delete=False) as f:
                    f.write(src)
                    tmp = Path(f.name)
                verdict = coup.run_coupling(tmp, name, strong).verdict
                mk = mut.run_mutation(tmp, name)
                kill = mk.kill_score if mk.mutants_tried else None
                tmp.unlink()
                label = ds.classify_label(True, correct) if correct is not None else "inconclusive"
                rec = {
                    "problem": p["problem_id"], "candidate": cname,
                    "weak_spec": ws, "verifies": True,
                    "behaviorally_correct": correct, "label": label,
                    "coupling": verdict, "mutation_kill": kill,
                }
                records.append(rec)
                if label == "verified_but_wrong" and verdict == "honest":
                    evasions.append(rec)

    by_label = {}
    for r in records:
        by_label[r["label"]] = by_label.get(r["label"], 0) + 1
    caught = sum(1 for r in records if r["label"] == "verified_but_wrong" and r["coupling"] != "honest")
    vbw = by_label.get("verified_but_wrong", 0)
    out = {
        "n_records": len(records), "by_label": by_label,
        "verified_but_wrong_caught_by_coupling": f"{caught}/{vbw}",
        "evasions": len(evasions), "records": records,
    }
    (ROOT / "results" / "dataset.json").write_text(json.dumps(out, indent=2) + "\n")
    print("records:", len(records), "| by_label:", by_label)
    print("verified_but_wrong caught by coupling:", f"{caught}/{vbw}", "| evasions:", len(evasions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
