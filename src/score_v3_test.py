"""
Phase 3 of "sampling protocol v3.md": scores the v3 test institutions.

Every institution in the committed v3 test list is scored over the test
window (fiscal years 2009-2019) with the v3 scoring pipeline
(v3_score_one.py: the v2 pipeline with the drift terms of RICD §10.3a
switched on), under the v2 test's structural-reporting rule and minimum
record, one fit per process with empty compile caches, once, at seed 7. For each institution the result is one of:

  scored                      fitted at seed 7; its nineteen classifier v3
                              features, its classifier v3 probability and
                              flag, its anchored probability and flag (the
                              anchor sensor, RICD §10.5b.13c), its
                              size-and-sector baseline probability and
                              flag (for the second verdict), the processor
                              it ran on, and (analysis only) the frozen
                              classifier v2 coefficients applied to its
                              v3-pipeline features;
  structurally unscorable     the protocol's structural-reporting rule;
  unscorable                  it does not meet the minimum record, with the
                              pipeline's own reason.

The three enrollment features are computed by v3_enrollment.py from the
compact College Scorecard file, for scoring year 2019, and the five drift
features by the v3 pipeline. The classifier v3 probability is the frozen
model's: the nineteen features standardized with the frozen scaler and
combined with the frozen coefficients and intercept. The flag is that probability at or above the
frozen for-profit cut for a for-profit institution, and at or above the
frozen nonprofit cut for any other. The size-and-sector baseline is
applied the same way with its own frozen model and cuts. The anchored
log-odds are classifier v3's log-odds minus the frozen anchor
coefficients times the institution's anchor inputs from
data/v3/anchors.json (scoring year 2019, f_approp and f_gift capped at 1,
0 where there is no record), and the anchored flag uses classifier v3's
cuts, so anchoring can only clear a flag.

Before every shard and every merge, the git blob hash of every pipeline
file is checked against the hashes frozen in data/v3/classifier v3.json,
and the run stops if any differs. It also stops if a v3 test outcome
file exists (data/v3/test outcomes.json).

A pipeline error or a failed NCES download says nothing about the
institution, so it is not recorded; the institution is tried again in
the next run.

Usage (GitHub Actions only, via score_v3_test.yml):
    cd src
    python score_v3_test.py prefetch --finance ../work/finance
    python score_v3_test.py shard --shard 0 --of 20 --minutes 290 \\
        --compact ../work/scorecard_compact.csv --finance ../work/finance --out ../work/evals
    python score_v3_test.py merge --evals ../work/evals
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import time
from pathlib import Path

import os
import subprocess
import sys
import tempfile

import v2_common as v2
import v3_common as v3c
import v3_enrollment as enr
import score_v2_test as t2
from score_v2_training import gap_features

V3_DIR = v2.ROOT / "data" / "v3"
SCORES_DIR = V3_DIR / "test scores"
CLASSIFIER_PATH = V3_DIR / "classifier v3.json"
OUTCOMES_PATH = V3_DIR / "test outcomes.json"
DRAW_PATH = V3_DIR / "test draw.json"
ANCHORS = V3_DIR / "anchors.json"
SEED = 7


def frozen() -> tuple[dict, dict]:
    if not CLASSIFIER_PATH.exists():
        raise SystemExit("Classifier v3 is not frozen (data/v3/classifier v3.json); nothing is scored.")
    if OUTCOMES_PATH.exists():
        raise SystemExit("A v3 test outcome file exists; no test institution may be scored after outcomes.")
    clf = json.loads(CLASSIFIER_PATH.read_text())
    now = v3c.pipeline_hashes()
    if now != clf["pipeline file hashes"]:
        diff = sorted(f for f in set(now) | set(clf["pipeline file hashes"])
                      if now.get(f) != clf["pipeline file hashes"].get(f))
        raise SystemExit("Pipeline files differ from those frozen with classifier v3: " + ", ".join(diff))
    clf2 = json.loads(t2.CLASSIFIER_PATH.read_text())["classifier v2"]
    return clf, clf2


def apply_v3(model: dict, values: dict, forprofit: bool) -> dict:
    if any(values.get(k) is None or not math.isfinite(values[k]) for k in model["features"]):
        return {"probability": None, "flag": None, "note": "a feature has no finite value"}
    z = [(values[k] - m) / s for k, m, s in zip(model["features"], model["scaler"]["mean"], model["scaler"]["scale"])]
    logit = model["intercept"] + sum(model["coefficients"][k] * v for k, v in zip(model["features"], z))
    p = 1.0 / (1.0 + math.exp(-logit))
    cut = model["threshold, for-profit"] if forprofit else model["threshold, public and private nonprofit"]
    return {"probability": p, "flag": p >= cut}


def apply_anchor(clf: dict, v3: dict, rec: dict | None, forprofit: bool) -> dict:
    b = clf["anchor sensor"]["coefficients (kappa_anch times theta_k; non-negative)"]
    if rec is None or rec.get("W") is None:
        inputs, has = {k: 0.0 for k in b}, False
    else:
        inputs = {"f_approp": min(rec["f_approp"] or 0.0, 1.0), "f_gift": min(rec["f_gift"] or 0.0, 1.0),
                  "S_par": float(rec["S_par"])}
        has = True
    out = {"anchor inputs": inputs, "anchor record": has, "anchor capacity (scale-free)":
           sum(b[k] * inputs[k] for k in b)}
    if v3["probability"] is None:
        return {**out, "anchored score": None, "anchored flag": None}
    p = min(max(v3["probability"], 1e-12), 1 - 1e-12)
    z = math.log(p / (1 - p)) - out["anchor capacity (scale-free)"]
    pa = 1.0 / (1.0 + math.exp(-z))
    m = clf["classifier v3"]
    cut = m["threshold, for-profit"] if forprofit else m["threshold, public and private nonprofit"]
    return {**out, "anchored score": pa, "anchored flag": pa >= cut}


def fit_one(inst: dict, sector: str, compact: str, finance: str) -> dict | None:
    u = inst["unitid"]
    cache = tempfile.mkdtemp(prefix=f"cache_{u}_")
    env = dict(os.environ)
    env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
    env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
    res = Path(cache) / "result.json"
    print(f"\n{'=' * 70}\n{inst['name']} ({u}), {sector}, seed {SEED}\n{'=' * 70}", flush=True)
    subprocess.run([sys.executable, "v3_score_one.py", "--unitid", u, "--name", inst["name"],
                    "--sector", sector, "--window", "test", "--seed", str(SEED),
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


def institutions() -> list[dict]:
    if not DRAW_PATH.exists():
        raise SystemExit("No v3 test list has been committed (data/v3/test draw.json).")
    return json.loads(DRAW_PATH.read_text())["institutions"]


def committed_batches() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(SCORES_DIR.glob("batch_*.json"))]


def done() -> set[str]:
    return {r["unitid"] for b in committed_batches() for r in b["results"]}


def cmd_shard(shard: int, of: int, minutes: float, compact: str, finance: str, out: str) -> None:
    clf, clf2 = frozen()
    model = clf["classifier v3"]
    hashes = clf["pipeline file hashes"]
    start = time.time()
    seen = done()
    todo = [i for k, i in enumerate(x for x in institutions() if x["unitid"] not in seen) if k % of == shard]
    results = []
    path = Path(out) / f"shard_{shard}_of_{of}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    win = v2.WINDOWS["test"]
    series = enr.load(compact, {i["unitid"] for i in todo})
    anchors = json.loads(ANCHORS.read_text())["cohorts"]["2019"]["records"]

    def save():
        path.write_text(json.dumps({"pipeline file hashes": hashes, "machine": v2.machine(),
                                    "results": results}, indent=2))

    for inst in todo:
        if (time.time() - start) / 60 > minutes:
            print(f"Time budget of {minutes} minutes reached; the rest waits for the next run.")
            break
        u = inst["unitid"]
        sector = v2.finance_sector(u, inst["sector"], finance, win["end_year"])
        rec = {"unitid": u, "name": inst["name"], "slot": inst["slot"], "sector": inst["sector"],
               "finance form sector": sector}
        why = t2.structural(u, sector, finance)
        if why:
            rec.update(status="structurally unscorable", reason=why)
        else:
            res = fit_one(inst, sector, compact, finance)
            if res is None:
                continue
            if res["status"] != "scored":
                rec.update(res)
            else:
                gaps = gap_features(res["availability"])
                fp = inst["sector"] == "forprofit"
                ef = enr.features(series.get(u), 2019)
                drift = res.get("drift") or {}
                vals = {**res["features"], "gap_trailing": gaps["gap_trailing"],
                        "gap_internal": gaps["gap_internal"], "forprofit": 1.0 if fp else 0.0, **ef,
                        **{k: drift.get(k) for k in v3c.DRIFT_FEATURES}}
                v3 = apply_v3(model, vals, fp)
                anc = apply_anchor(clf, v3, anchors.get(u), fp)
                bl = apply_v3(clf["size-and-sector baseline"], vals, fp)
                v2r = t2.apply(clf2, vals)
                rec.update({k: v for k, v in res.items() if k != "features"})
                rec.update(gaps)
                rec.update({"features (seed 7)": res["features"], "enrollment features": ef,
                            "drift features": {k: drift.get(k) for k in v3c.DRIFT_FEATURES},
                            "score": v3["probability"], "flag": v3["flag"], **anc,
                            "baseline score": bl["probability"], "baseline flag": bl["flag"],
                            "classifier v2 score on v3-pipeline features (analysis only)": v2r["probability"],
                            "classifier v2 flag on v3-pipeline features (analysis only)": v2r["flag"]})
        rec["processor"] = v2.machine()["cpu"]
        rec["scored at (UTC)"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        results.append(rec)
        save()
    save()
    print(f"Wrote {path} ({len(results)} results).")


def cmd_merge(evals: str) -> None:
    clf, _ = frozen()
    hashes = clf["pipeline file hashes"]
    shards = [json.loads(p.read_text()) for p in sorted(Path(evals).glob("shard_*.json"))]
    seen = done()
    new = []
    for s in shards:
        if s["pipeline file hashes"] != hashes:
            raise SystemExit("A shard ran with different pipeline files; nothing merged.")
        new += [r for r in s["results"] if r["unitid"] not in seen and not seen.add(r["unitid"])]
    if not new:
        print("No new results to merge.")
        return
    n = len(committed_batches()) + 1
    v2.write_json(SCORES_DIR / f"batch_{n:03d}.json", {
        "protocol": "sampling protocol v3.md, phase 3 (test scoring; committed before any test outcome)",
        "merged at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pipeline file hashes (checked against classifier v3.json)": hashes,
        "shards": [{"machine": s["machine"], "results": len(s["results"])} for s in shards],
        "results": new,
    })
    print(f"Merged batch {n:03d}: {len(new)} new results; {len(done())} of {len(institutions())} "
          "v3 test institutions now have one.")


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
        t2.cmd_prefetch(a.finance)
    elif a.cmd == "shard":
        cmd_shard(a.shard, a.of, a.minutes, a.compact, a.finance, a.out)
    else:
        cmd_merge(a.evals)


if __name__ == "__main__":
    main()
