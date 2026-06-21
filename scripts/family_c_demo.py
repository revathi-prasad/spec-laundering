#!/usr/bin/env python3
"""Family-C boundary: coupling is only as sound as the reference spec. A
length-only spec admits a right-length/wrong-content impl that coupling rates
honest yet differential testing proves wrong. Writes results/family_c_demo.json."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detector import coupling as coup  # noqa: E402
from detector import difftest  # noqa: E402

SIG = "method DoubleLength(s: seq<int>) returns (r: seq<int>)"
INCOMPLETE = ["|r| == 2 * |s|"]          # length only
REF = "r := s + s;"
CAND = "r := seq(2 * |s|, i => 0);"      # right length, wrong content


def main() -> int:
    src = f"{SIG}\n  ensures {INCOMPLETE[0]}\n{{ {CAND} }}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".dfy", delete=False) as f:
        f.write(src)
        tmp = Path(f.name)
    verdict = coup.run_coupling(tmp, "DoubleLength", INCOMPLETE).verdict
    tmp.unlink()
    wrong = difftest.differential_test(SIG, [], REF, CAND)

    out = {
        "reference_spec": INCOMPLETE,
        "candidate": CAND,
        "behaviorally_wrong": wrong,
        "coupling": verdict,
        "note": "incomplete reference spec -> coupling misses a verified-but-wrong impl (Family C)",
    }
    (ROOT / "results" / "family_c_demo.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
