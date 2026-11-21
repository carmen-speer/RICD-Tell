"""
Exploratory (chosen after the v3 results were known; not pre-registered):
does tracker v3's flag beat the frozen size-and-sector model's flag at
their committed cut points?

Reads only committed files, downloads nothing:
  data/v3/test scores/batch_001.json   each institution's "flag" (v3) and
                                       "baseline flag" (size and sector)
  data/v3/test outcomes.json           "closed or failed (primary)"

For all scored institutions and for public and private nonprofit
institutions alone, computes Youden's J for each flag and a paired
bootstrap of the difference (10,000 resamples of institutions, seed
20261121, the same resampling the pre-registered tests used).

Output: data/v3 exploratory/cut-point comparison.json

Usage:
    cd src
    python "v3 cut-point comparison.py"
"""

import datetime
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORES = ROOT / "data" / "v3" / "test scores" / "batch_001.json"
OUTCOMES = ROOT / "data" / "v3" / "test outcomes.json"
OUT = ROOT / "data" / "v3 exploratory" / "cut-point comparison.json"
RESAMPLES, SEED = 10000, 20261121


def youden(rows, k):
    closed = [r for r in rows if r[0]]
    survived = [r for r in rows if not r[0]]
    return sum(r[k] for r in closed) / len(closed) - sum(r[k] for r in survived) / len(survived)


def compare(rows):
    j_v3, j_ss = youden(rows, 1), youden(rows, 2)
    rng, diffs = random.Random(SEED), []
    for _ in range(RESAMPLES):
        b = [rows[rng.randrange(len(rows))] for _ in rows]
        if any(r[0] for r in b) and not all(r[0] for r in b):
            diffs.append(youden(b, 1) - youden(b, 2))
    diffs.sort()
    return {"institutions": len(rows), "closed or failed": sum(r[0] for r in rows),
            "J, tracker v3": j_v3, "J, size-and-sector model": j_ss, "difference": j_v3 - j_ss,
            "difference, paired 95% bootstrap": [diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]],
            "share of resamples with difference at or below zero": sum(x <= 0 for x in diffs) / len(diffs),
            "closures caught by v3 and missed by size and sector": sum(r[0] and r[1] and not r[2] for r in rows),
            "closures caught by size and sector and missed by v3": sum(r[0] and r[2] and not r[1] for r in rows)}


def main():
    scored = [x for x in json.loads(SCORES.read_text())["results"] if x["status"] == "scored"]
    outcome = {x["unitid"]: x["closed or failed (primary)"] for x in json.loads(OUTCOMES.read_text())["institutions"]}
    rows = lambda sel: [(outcome[x["unitid"]], bool(x["flag"]), bool(x["baseline flag"])) for x in sel]
    result = {
        "note": "Exploratory: chosen after the v3 results were known, so not pre-registered. Flags and outcomes "
                "are the committed v3 test files, unchanged.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "resamples": RESAMPLES, "seed": SEED,
        "all scored institutions": compare(rows(scored)),
        "public and private nonprofit": compare(rows([x for x in scored if x["sector"] in ("public", "private")])),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
