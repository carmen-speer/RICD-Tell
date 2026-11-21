"""
The live tracker, under "live tracker protocol.md": tracker v3, frozen,
applied to every four-year degree-granting college on the newest eleven
fiscal years (2014 to 2024).

Subcommands:
  frame     downloads the newest institutional header file NCES serves,
            builds the frame with the v2/v3 frame function (SECTOR 1, 2 or 3,
            DEGGRANT 1), and writes data/live/frame.json with its SHA-256
  anchors   computes the anchor sensor's inputs (f_approp, f_gift, S_par)
            for the 2024 cohort (fiscal 2022 to 2024) with v3_anchors.py's
            own cohort function, unchanged; writes data/live/anchors 2024.json
            (the frozen data/v3/anchors.json is not touched)
  prefetch  downloads the finance files for the live window
  shard     scores one shard of the colleges not yet scored, within a time
            budget, one fit per process with empty compile caches, seed 7
  merge     merges the shards into the next batch in data/live/scores/ and
            writes docs/data/live v3 scores.json for the dashboard

Every shard and merge first checks the git blob hash of every pipeline file
against data/v3/classifier v3.json and stops if any differs. A pipeline
error or a failed NCES download says nothing about a college, so it is not
recorded; the college is tried again in the next run.

Usage (GitHub Actions only, via score_live.yml):
    cd src
    python score_live.py frame
    python score_live.py anchors
    python score_live.py prefetch --finance ../work/finance
    python score_live.py shard --shard 0 --of 20 --minutes 290 \\
        --compact ../work/scorecard_compact.csv --finance ../work/finance --out ../work/evals
    python score_live.py merge --evals ../work/evals
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import v3_score_live_one as live          # adds the live window to v2.WINDOWS
import v2_common as v2
import v3_common as v3c
import v3_enrollment as enr
import v3_anchors as anc
import score_v2_test as t2
from score_v2_training import gap_features

WINDOW = "live"
SCORING_YEAR = 2024
t2.WINDOW = WINDOW                       # the structural rule and prefetch read the live window
enr.LAST_LABEL[SCORING_YEAR] = SCORING_YEAR - 1   # the compact file's 2023 label is fiscal 2024
ANCHOR_YEARS = (2022, 2023, 2024)
SEED = 7

ROOT = v2.ROOT
LIVE = ROOT / "data" / "live"
FRAME = LIVE / "frame.json"
ANCHORS = LIVE / "anchors 2024.json"
SCORES = LIVE / "scores"
CLASSIFIER = ROOT / "data" / "v3" / "classifier v3.json"
DASHBOARD = ROOT / "docs" / "data" / "live v3 scores.json"
HD_FIRST_TRY = 2025

_d = importlib.util.spec_from_file_location("v2draw", Path(__file__).resolve().parent / "draw v2 sample.py")
v2draw = importlib.util.module_from_spec(_d)
_d.loader.exec_module(v2draw)


# ------------------------------------------------------------------ frozen model
def frozen() -> dict:
    if not CLASSIFIER.exists():
        raise SystemExit("Classifier v3 is not frozen (data/v3/classifier v3.json); nothing is scored.")
    clf = json.loads(CLASSIFIER.read_text())
    now = v3c.pipeline_hashes()
    if now != clf["pipeline file hashes"]:
        diff = sorted(f for f in set(now) | set(clf["pipeline file hashes"])
                      if now.get(f) != clf["pipeline file hashes"].get(f))
        raise SystemExit("Pipeline files differ from those frozen with classifier v3: " + ", ".join(diff))
    return clf


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
    out = {"anchor inputs": inputs, "anchor record": has,
           "anchor capacity (scale-free)": sum(b[k] * inputs[k] for k in b)}
    if v3["probability"] is None:
        return {**out, "anchored score": None, "anchored flag": None}
    p = min(max(v3["probability"], 1e-12), 1 - 1e-12)
    z = math.log(p / (1 - p)) - out["anchor capacity (scale-free)"]
    pa = 1.0 / (1.0 + math.exp(-z))
    m = clf["classifier v3"]
    cut = m["threshold, for-profit"] if forprofit else m["threshold, public and private nonprofit"]
    return {**out, "anchored score": pa, "anchored flag": pa >= cut}


# ------------------------------------------------------------------ inputs
def cmd_frame() -> None:
    last_err = None
    for year in range(HD_FIRST_TRY, HD_FIRST_TRY - 3, -1):
        try:
            csv_bytes, url = v2draw.download_hd(year)
        except SystemExit as e:
            last_err = e
            continue
        frame = v2draw.build_frame(csv_bytes)
        v2.write_json(FRAME, {
            "protocol": "live tracker protocol.md, section 1",
            "created (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "source file": f"HD{year}", "source url": url, "source sha256": hashlib.sha256(csv_bytes).hexdigest(),
            "colleges": len(frame), "institutions": frame})
        print(f"Frame from HD{year}: {len(frame)} colleges.")
        return
    raise SystemExit(f"No recent header file was served ({last_err}). Nothing recorded.")


def cmd_anchors() -> None:
    log: dict = {}
    recs = anc.cohort(str(SCORING_YEAR), ANCHOR_YEARS, log)
    v2.write_json(ANCHORS, {
        "protocol": "live tracker protocol.md, section 2 (v3_anchors.py's cohort function, unchanged)",
        "created (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "codes": anc.CODES, "fiscal years": list(ANCHOR_YEARS), "institutions": len(recs),
        "records": recs, "files read": log})
    print(f"Anchor inputs for {len(recs)} institutions, fiscal {ANCHOR_YEARS[0]}-{ANCHOR_YEARS[-1]}.")


def cmd_prefetch(finance: str) -> None:
    win = v2.WINDOWS[WINDOW]
    manifest, _ = v2.prefetch_finance(finance, win["start_year"], win["end_year"], required=True)
    Path(finance, "manifest.json").write_text(json.dumps(manifest, indent=2))


# ------------------------------------------------------------------ scoring
def batches() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(SCORES.glob("batch_*.json"))]


def done() -> set[str]:
    return {r["unitid"] for b in batches() for r in b["results"]}


def fit_one(inst: dict, sector: str, compact: str, finance: str) -> dict | None:
    u = inst["unitid"]
    cache = tempfile.mkdtemp(prefix=f"cache_{u}_")
    env = dict(os.environ)
    env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
    env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
    res = Path(cache) / "result.json"
    print(f"\n{'=' * 70}\n{inst['name']} ({u}), {sector}, seed {SEED}\n{'=' * 70}", flush=True)
    subprocess.run([sys.executable, "v3_score_live_one.py", "--unitid", u, "--name", inst["name"],
                    "--sector", sector, "--window", WINDOW, "--seed", str(SEED),
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


def cmd_shard(shard: int, of: int, minutes: float, compact: str, finance: str, out: str) -> None:
    clf = frozen()
    model = clf["classifier v3"]
    hashes = clf["pipeline file hashes"]
    if not FRAME.exists() or not ANCHORS.exists():
        raise SystemExit("The frame or the 2024 anchor inputs are missing (data/live/). Nothing scored.")
    with open(compact, newline="") as f:
        if not any((row.get("YEAR") or "").strip() == str(SCORING_YEAR - 1) for row in csv.DictReader(f)):
            raise SystemExit(f"The compact College Scorecard file has no {SCORING_YEAR - 1} rows (fiscal "
                             f"{SCORING_YEAR}); the live window cannot be read. Nothing scored.")
    start = time.time()
    seen = done()
    insts = json.loads(FRAME.read_text())["institutions"]
    todo = [i for k, i in enumerate(x for x in insts if x["unitid"] not in seen) if k % of == shard]
    results = []
    path = Path(out) / f"shard_{shard}_of_{of}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    win = v2.WINDOWS[WINDOW]
    series = enr.load(compact, {i["unitid"] for i in todo})
    anchors = json.loads(ANCHORS.read_text())["records"]

    def save():
        path.write_text(json.dumps({"pipeline file hashes": hashes, "machine": v2.machine(),
                                    "results": results}, indent=2))

    for inst in todo:
        if (time.time() - start) / 60 > minutes:
            print(f"Time budget of {minutes} minutes reached; the rest waits for the next run.")
            break
        u = inst["unitid"]
        sector = v2.finance_sector(u, inst["sector"], finance, win["end_year"])
        rec = {"unitid": u, "name": inst["name"], "state": inst.get("state", ""), "sector": inst["sector"],
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
                ef = enr.features(series.get(u), SCORING_YEAR)
                drift = res.get("drift") or {}
                vals = {**res["features"], "gap_trailing": gaps["gap_trailing"],
                        "gap_internal": gaps["gap_internal"], "forprofit": 1.0 if fp else 0.0, **ef,
                        **{k: drift.get(k) for k in v3c.DRIFT_FEATURES}}
                v3 = apply_v3(model, vals, fp)
                a = apply_anchor(clf, v3, anchors.get(u), fp)
                rec.update({k: v for k, v in res.items() if k != "features"})
                rec.update(gaps)
                rec.update({"features (seed 7)": res["features"], "enrollment features": ef,
                            "drift features": {k: drift.get(k) for k in v3c.DRIFT_FEATURES},
                            "score": v3["probability"], "flag": v3["flag"], **a})
        rec["processor"] = v2.machine()["cpu"]
        rec["scored at (UTC)"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        results.append(rec)
        save()
    save()
    print(f"Wrote {path} ({len(results)} results).")


def dashboard_rows() -> list[dict]:
    rows = []
    for b in batches():
        for r in b["results"]:
            rows.append({k: r.get(k) for k in ("unitid", "name", "state", "sector", "status", "reason", "score",
                                                "flag", "anchored score", "anchored flag", "anchor inputs",
                                                "scored at (UTC)")})
    rows.sort(key=lambda r: (r["name"] or "").lower())
    return rows


def cmd_merge(evals: str) -> None:
    clf = frozen()
    hashes = clf["pipeline file hashes"]
    shards = [json.loads(p.read_text()) for p in sorted(Path(evals).glob("shard_*.json"))]
    seen = done()
    new = []
    for s in shards:
        if s["pipeline file hashes"] != hashes:
            raise SystemExit("A shard ran with different pipeline files; nothing merged.")
        new += [r for r in s["results"] if r["unitid"] not in seen and not seen.add(r["unitid"])]
    if new:
        n = len(batches()) + 1
        v2.write_json(SCORES / f"batch_{n:03d}.json", {
            "protocol": "live tracker protocol.md (tracker v3, frozen; fiscal 2014-2024)",
            "merged at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "pipeline file hashes (checked against classifier v3.json)": hashes,
            "shards": [{"machine": s["machine"], "results": len(s["results"])} for s in shards],
            "results": new,
        })
    total = len(json.loads(FRAME.read_text())["institutions"]) if FRAME.exists() else None
    rows = dashboard_rows()
    v2.write_json(DASHBOARD, {"protocol": "live tracker protocol.md", "window": "fiscal years 2014-2024",
                              "colleges in the frame": total, "colleges with a result": len(rows),
                              "updated (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                              "colleges": rows})
    print(f"{len(new)} new results; {len(rows)} of {total} colleges in the frame now have one.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("frame")
    sub.add_parser("anchors")
    p = sub.add_parser("prefetch"); p.add_argument("--finance", required=True)
    p = sub.add_parser("shard")
    for x in ("--compact", "--finance", "--out"):
        p.add_argument(x, required=True)
    p.add_argument("--shard", type=int, required=True); p.add_argument("--of", type=int, required=True)
    p.add_argument("--minutes", type=float, required=True)
    p = sub.add_parser("merge"); p.add_argument("--evals", required=True)
    a = ap.parse_args()
    if a.cmd == "frame":
        cmd_frame()
    elif a.cmd == "anchors":
        cmd_anchors()
    elif a.cmd == "prefetch":
        cmd_prefetch(a.finance)
    elif a.cmd == "shard":
        cmd_shard(a.shard, a.of, a.minutes, a.compact, a.finance, a.out)
    else:
        cmd_merge(a.evals)


if __name__ == "__main__":
    main()
