"""
Rescores the development set for "sampling protocol v3.md" with the drift
terms switched on.

The development set is every institution scored in the v2 training set
(scoring year 2014, window FY2004-FY2014) and in the v2 test (scoring year
2019, window FY2009-FY2019). Each is refitted once, at seed 7, with the v3
scoring pipeline (v3_score_one.py: the v2 pipeline with RICD §10.3a's
drift-type and shock-type collapse terms), in its own process with empty
compile caches, on the finance form the v2 run used. No outcome is read
here; classifier v3 is fitted afterwards from these results and the
committed v2 outcomes.

It refuses to start unless the v3 reproducibility check has passed
(data/v3/reproducibility check.json) and the pipeline files are the ones
that check ran with, and it stops if classifier v3 has already been frozen.
A pipeline error or a failed download is not recorded; the institution is
tried again in the next run. An institution that was scored in v2 but
cannot be scored now is recorded with the pipeline's reason, which can
only happen if the drift terms themselves fail, and is reported.

Usage (GitHub Actions only, via score_v3_development.yml):
    cd src
    python score_v3_development.py prefetch --finance ../work/finance
    python score_v3_development.py shard --shard 0 --of 20 --minutes 290 \\
        --compact ../work/scorecard_compact.csv --finance ../work/finance --out ../work/evals
    python score_v3_development.py merge --evals ../work/evals
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import v2_common as v2
import v3_common as v3

SCORES_DIR = v3.V3_DIR / "development scores"
CHECK_PATH = v3.V3_DIR / "reproducibility check.json"
CLASSIFIER_PATH = v3.V3_DIR / "classifier v3.json"
SOURCES = (("training", v2.V2_DIR / "training scores", 2014),
           ("test", v2.V2_DIR / "test scores", 2019))
SEED = 7


def checked_hashes() -> dict:
    if not CHECK_PATH.exists():
        raise SystemExit("The v3 reproducibility check has not been run (data/v3/reproducibility check.json).")
    chk = json.loads(CHECK_PATH.read_text())
    if chk["verdict"] != "passed":
        raise SystemExit(f"The v3 reproducibility check has not passed (verdict: {chk['verdict']}).")
    if CLASSIFIER_PATH.exists():
        raise SystemExit("Classifier v3 is already frozen; the development set is not rescored after it.")
    now = v3.pipeline_hashes()
    if now != chk["pipeline file hashes"]:
        diff = sorted(f for f in set(now) | set(chk["pipeline file hashes"])
                      if now.get(f) != chk["pipeline file hashes"].get(f))
        raise SystemExit("Pipeline files differ from those the reproducibility check ran with: " + ", ".join(diff))
    return now


def development_list() -> list[dict]:
    out = []
    for window, d, year in SOURCES:
        for p in sorted(d.glob("batch_*.json")):
            for r in json.loads(p.read_text())["results"]:
                if r["status"] == "scored":
                    out.append({"unitid": r["unitid"], "name": r["name"], "sector": r["sector"],
                                "finance form sector": r["finance form sector"], "window": window,
                                "scoring year": year, "key": f"{year}:{r['unitid']}"})
    return out


def committed_batches() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(SCORES_DIR.glob("batch_*.json"))]


def done() -> set[str]:
    return {r["key"] for b in committed_batches() for r in b["results"]}


def fit_one(inst: dict, compact: str, finance: str) -> dict | None:
    cache = tempfile.mkdtemp(prefix=f"cache_{inst['unitid']}_")
    env = dict(os.environ)
    env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
    env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
    res = Path(cache) / "result.json"
    print(f"\n{'=' * 70}\n{inst['name']} ({inst['unitid']}), {inst['window']} window\n{'=' * 70}", flush=True)
    subprocess.run([sys.executable, "v3_score_one.py", "--unitid", inst["unitid"], "--name", inst["name"],
                    "--sector", inst["finance form sector"], "--window", inst["window"], "--seed", str(SEED),
                    "--compact", str(Path(compact).resolve()), "--finance", str(Path(finance).resolve()),
                    "--out", str(res)], cwd=Path(__file__).resolve().parent, env=env)
    if not res.exists():
        print("RETRY NEXT RUN: the fit process ended without a result.")
        return None
    r = json.loads(res.read_text())
    if r["status"] in ("error", "download failure"):
        print(f"RETRY NEXT RUN: {r['status']}: {r.get('error', '')}")
        return None
    return r


def cmd_prefetch(finance: str) -> None:
    start = min(w["start_year"] for w in v2.WINDOWS.values())
    end = max(w["end_year"] for w in v2.WINDOWS.values())
    manifest, _ = v2.prefetch_finance(finance, start, end, required=True)
    Path(finance, "manifest.json").write_text(json.dumps(manifest, indent=2))


def cmd_shard(shard: int, of: int, minutes: float, compact: str, finance: str, out: str) -> None:
    hashes = checked_hashes()
    start = time.time()
    seen = done()
    todo = [i for k, i in enumerate(x for x in development_list() if x["key"] not in seen) if k % of == shard]
    results = []
    path = Path(out) / f"shard_{shard}_of_{of}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    def save():
        path.write_text(json.dumps({"pipeline file hashes": hashes, "machine": v2.machine(), "results": results}, indent=2))

    for inst in todo:
        if (time.time() - start) / 60 > minutes:
            print(f"Time budget of {minutes} minutes reached; the rest waits for the next run.")
            break
        r = fit_one(inst, compact, finance)
        if r is None:
            continue
        results.append({**inst, **r, "scored at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        save()
    save()
    print(f"Wrote {path} ({len(results)} results).")


def cmd_merge(evals: str) -> None:
    hashes = checked_hashes()
    shards = [json.loads(p.read_text()) for p in sorted(Path(evals).glob("shard_*.json"))]
    seen = done()
    new = []
    for s in shards:
        if s["pipeline file hashes"] != hashes:
            raise SystemExit("A shard ran with different pipeline files; nothing merged.")
        new += [r for r in s["results"] if r["key"] not in seen and not seen.add(r["key"])]
    if not new:
        print("No new results to merge.")
        return
    n = len(committed_batches()) + 1
    v2.write_json(SCORES_DIR / f"batch_{n:03d}.json", {
        "protocol": "sampling protocol v3.md (development set rescored with the drift terms)",
        "merged at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pipeline file hashes": hashes,
        "shards": [{"machine": s["machine"], "results": len(s["results"])} for s in shards],
        "results": new,
    })
    print(f"Merged batch {n:03d}: {len(new)} new results; {len(done())} of {len(development_list())} "
          "development institutions now have one.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prefetch"); p.add_argument("--finance", required=True)
    p = sub.add_parser("shard")
    for a in ("--compact", "--finance", "--out"):
        p.add_argument(a, required=True)
    p.add_argument("--shard", type=int, required=True); p.add_argument("--of", type=int, required=True)
    p.add_argument("--minutes", type=float, required=True)
    p = sub.add_parser("merge"); p.add_argument("--evals", required=True)
    a = ap.parse_args()
    if a.cmd == "prefetch":
        cmd_prefetch(a.finance)
    elif a.cmd == "shard":
        cmd_shard(a.shard, a.of, a.minutes, a.compact, a.finance, a.out)
    else:
        cmd_merge(a.evals)


if __name__ == "__main__":
    main()
