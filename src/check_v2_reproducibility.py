"""
Cross-machine reproducibility check for "sampling protocol v2.md" (third
amendment).

Training and test scoring run in several jobs at once, and GitHub assigns
each job its own machine. The phase 0 checks showed that the same code,
seed and data can give slightly different sampled features on different
machines, and on one machine depending on whether the compiled model was
fresh or cached. The third amendment therefore runs every v2 fit with a
fixed software environment (requirements v2 lock.txt, Python 3.11.18), an
empty compile cache, single-threaded numerical libraries, and code
compiled for a generic processor rather than for whichever processor the
machine happens to have. This check tests whether those settings make a
score independent of the machine.

The workflow runs this script twice, as two separate jobs on two separate
machines ("replica" a and b). Each replica fits the same 10 institutions
(the first 10 the first confirmatory test scored, over its window,
FY2009-FY2019, at seed 7) under the amendment's settings and saves the
features. The compare step then checks that the two replicas agree exactly
on every feature of every institution.

Passing: the two replicas ran on processors of different models and agree
exactly (floating-point slack of 1e-9 only). If both replicas happened to
run on the same processor model, the result is recorded as inconclusive
and the workflow is run again, up to three times in all.

Nothing here looks up any outcome. The result is written to
data/v2/reproducibility check.json.

Usage (GitHub Actions only, via check_v2_reproducibility.yml):
    cd src
    python check_v2_reproducibility.py replica --name a --compact C --finance F --out DIR
    python check_v2_reproducibility.py compare --dir DIR
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import v2_common as v2

OUT_PATH = v2.V2_DIR / "reproducibility check.json"
OUTCOMES = v2.ROOT / "data" / "confirmatory" / "outcomes.csv"
N = 10
TOL = 1e-9


def first_scored() -> list[dict]:
    with open(OUTCOMES, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["group"] == "scored"]
    rows.sort(key=lambda r: int(r["slot"]))
    return rows[:N]


def cmd_replica(name: str, compact: str, finance: str, out: str) -> None:
    win = v2.WINDOWS["test"]
    v2.prefetch_finance(finance, win["start_year"], win["end_year"], required=True)
    results = []
    for row in first_scored():
        sector = v2.finance_sector(row["unitid"], row["sector"], finance, win["end_year"])
        cache = tempfile.mkdtemp(prefix=f"cache_{row['unitid']}_")
        env = dict(os.environ)
        env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
        env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
        res = Path(cache) / "result.json"
        subprocess.run([sys.executable, "v2_score_one.py", "--unitid", row["unitid"], "--name", row["name"],
                        "--sector", sector, "--window", "test", "--seed", "7",
                        "--compact", str(Path(compact).resolve()), "--finance", str(Path(finance).resolve()),
                        "--out", str(res)], cwd=Path(__file__).resolve().parent, env=env, check=True)
        results.append({"unitid": row["unitid"], "name": row["name"], **json.loads(res.read_text())})
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, f"replica_{name}.json").write_text(json.dumps({"machine": v2.machine(), "results": results}, indent=2))


def cmd_compare(directory: str) -> None:
    a = json.loads(Path(directory, "replica_a.json").read_text())
    b = json.loads(Path(directory, "replica_b.json").read_text())
    different_cpus = a["machine"]["cpu"] != b["machine"]["cpu"]
    rows, all_equal = [], True
    for ra, rb in zip(a["results"], b["results"]):
        fa, fb = ra.get("features"), rb.get("features")
        if fa is None or fb is None:
            diffs = None
            equal = False
        else:
            diffs = {k: abs(fa[k] - fb[k]) for k in fa}
            equal = all(d <= TOL for d in diffs.values())
        all_equal &= equal
        rows.append({"unitid": ra["unitid"], "name": ra["name"], "replica a": fa, "replica b": fb,
                     "differences": diffs, "equal": equal})
    verdict = ("passed" if all_equal and different_cpus else
               "failed" if not all_equal else
               "inconclusive: both replicas ran on the same processor model")
    history = []
    if OUT_PATH.exists():
        prev = json.loads(OUT_PATH.read_text())
        history = prev.get("earlier runs", []) + [{k: prev[k] for k in ("written at (UTC)", "verdict", "processors")}]
    v2.write_json(OUT_PATH, {
        "protocol": "sampling protocol v2.md, third amendment (cross-machine reproducibility)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "processors": [a["machine"]["cpu"], b["machine"]["cpu"]],
        "settings": a["machine"]["environment variables"],
        "institutions": rows,
        "machines": {"a": a["machine"], "b": b["machine"]},
        "earlier runs": history,
    })
    print(f"Verdict: {verdict}. Processors: {a['machine']['cpu']} / {b['machine']['cpu']}.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("replica")
    for x in ("--name", "--compact", "--finance", "--out"):
        p.add_argument(x, required=True)
    p = sub.add_parser("compare")
    p.add_argument("--dir", required=True)
    a = ap.parse_args()
    if a.cmd == "replica":
        cmd_replica(a.name, a.compact, a.finance, a.out)
    else:
        cmd_compare(a.dir)


if __name__ == "__main__":
    main()
