#!/usr/bin/env python3
"""Uncoupled control (GetFirst): hold the spec, vary the impl. mutation reacts to
spec shape; coupling reacts to the impl. Writes results/control_getfirst.json."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detector import mutation as mut  # noqa: E402
from detector import coupling as coup  # noqa: E402

STRONG = ["r == s[0]"]
KILL_THRESHOLD = 0.3
VARIANTS = [
    ("honest_strong", "r == s[0]", "r := s[0];"),
    ("loose_honest", "r == s[0] || true", "r := s[0];"),
    ("laundered", "r == s[0] || true", "r := 0;"),
]


def _src(ensures: str, body: str) -> str:
    return (
        "method GetFirst(s: seq<int>) returns (r: int)\n"
        "  requires |s| > 0\n"
        f"  ensures {ensures}\n"
        f"{{ {body} }}\n"
    )


def main() -> int:
    rows = []
    for name, ensures, body in VARIANTS:
        f = tempfile.NamedTemporaryFile("w", suffix=".dfy", delete=False)
        f.write(_src(ensures, body))
        f.close()
        p = Path(f.name)
        b = mut.run_mutation(p, "GetFirst")
        kill = b.kill_score if b.mutants_tried else None
        b_flag = kill is not None and kill < KILL_THRESHOLD
        e = coup.run_coupling(p, "GetFirst", STRONG)
        p.unlink()
        rows.append(
            {
                "variant": name,
                "ensures": ensures,
                "body": body,
                "mutation_kill": kill,
                "mutation_flag": b_flag,
                "coupling_verdict": e.verdict,
            }
        )

    (ROOT / "results" / "control_getfirst.json").write_text(
        json.dumps(rows, indent=2) + "\n"
    )
    print(f"{'variant':<15}{'mutation':<22}{'coupling':<16}")
    print("-" * 53)
    for r in rows:
        k = r["mutation_kill"]
        cbs = (f"FLAG kill={k:.2f}" if r["mutation_flag"] else f"clean kill={k:.2f}") if k is not None else "n/a"
        print(f"{r['variant']:<15}{cbs:<22}{r['coupling_verdict']:<16}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
