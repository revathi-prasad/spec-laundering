#!/usr/bin/env python3
"""Demo the migration regression detector over the seed bank.

Each reference_impl is the trusted "old" total function. For every problem we
check: (a) old vs old -> equivalent (sanity); (b) old vs each type-trivial
"new" impl -> regression, with counterexamples. Writes results/migration_demo.json.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detector import migrate  # noqa: E402
from detector import trivial_gen as tg  # noqa: E402

_SIG = re.compile(r"method\s+(\w+)\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)")
TRIVIAL_CAP = 3


def _parse(s):
    return [tuple(x.strip() for x in p.split(":", 1)) for p in s.split(",") if ":" in p]


def main() -> int:
    bank = json.loads((ROOT / "data" / "problem_bank.json").read_text())["problems"]
    out = []
    n_reg = n_equiv = n_incon = 0
    for p in bank:
        sig, req = p["signature"], p.get("requires", [])
        m = _SIG.search(sig)
        ref = p["reference_impl"]

        sanity = migrate.check_migration(sig, req, ref, ref)
        out.append({"problem": p["problem_id"], "new": "reference",
                    "status": sanity.status, "counterexamples": sanity.counterexamples})

        trivials = tg.generate_trivials(_parse(m.group(2)), _parse(m.group(3)))[:TRIVIAL_CAP]
        for i, body in enumerate(trivials):
            rep = migrate.check_migration(sig, req, ref, body)
            n_reg += rep.status == "regression"
            n_equiv += rep.status == "equivalent"
            n_incon += rep.status == "inconclusive"
            out.append({"problem": p["problem_id"], "new": f"trivial{i}", "body": body,
                        "status": rep.status,
                        "counterexamples": rep.counterexamples[:3]})

    summary = {"regressions": n_reg, "equivalent": n_equiv, "inconclusive": n_incon}
    (ROOT / "results" / "migration_demo.json").write_text(
        json.dumps({"summary": summary, "records": out}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
