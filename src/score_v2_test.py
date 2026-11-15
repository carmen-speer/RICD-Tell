"""
Phase 6 of "sampling protocol v2.md": scores the test institutions.

Every institution in the committed test draw is scored over the test
window (fiscal years 2009-2019) with the frozen pipeline and the frozen
classifier v2 (data/v2/classifier v2.json). For each institution the
result is one of:

  scored                      fitted at seeds 7, 101 and 202, each in its
                              own process with an empty compile cache; its
                              score and flag are those of seed 7, the flags
                              at all three seeds are recorded, and any
                              disagreement among them is recorded as an
                              attribute of the institution;
  structurally unscorable     the protocol's structural-reporting rule, the
                              same rule as in training applied to the test
                              window;
  unscorable                  it does not meet the protocol's minimum
                              record, with the pipeline's own reason.

The score is the frozen classifier's probability: the ten features are
standardized with the frozen scaler and combined with the frozen
coefficients and intercept; the flag is that probability at or above the
frozen threshold. The analysis-only variant without the missing-data
features is applied the same way and recorded beside it; it never decides
a flag.

Before every shard and every merge, the git blob hash of every pipeline
file is checked against the hashes frozen in data/v2/classifier v2.json,
and the run stops if any differs. It also stops if any test outcome has
been committed (data/v2/test outcomes.json), since every test score must
be committed before any test outcome is looked up.

A pipeline error or a failed NCES download at any seed says nothing about
the institution, so it is not recorded; the institution is tried again in
the next run.

Usage (GitHub Actions only, via score_v2_test.yml):
    cd src
    python score_v2_test.py prefetch --finance ../work/finance
    python score_v2_test.py shard --shard 0 --of 6 --minutes 290 \\
        --compact ../work/scorecard_compact.csv --finance ../work/finance --out ../work/evals
    python score_v2_test.py merge --evals ../work/evals
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import v2_common as v2
from score_v2_training import FORM_CODES, gap_features, pipeline_hashes

SCORES_DIR = v2.V2_DIR / "test scores"
CLASSIFIER_PATH = v2.V2_DIR / "classifier v2.json"
OUTCOMES_PATH = v2.V2_DIR / "test outcomes.json"
DRAW_PATH = v2.V2_DIR / "test draw.json"
WINDOW = "test"
VARIANT = "without the missing-data features (analysis only; never decides a flag)"


def frozen() -> dict:
    if not CLASSIFIER_PATH.exists():
        raise SystemExit("Classifier v2 is not frozen (data/v2/classifier v2.json); nothing is scored.")
    if OUTCOMES_PATH.exists():
        raise SystemExit("A test outcome file exists; no test institution may be scored after outcomes.")
    clf = json.loads(CLASSIFIER_PATH.read_text())
    now = pipeline_hashes()
    if now != clf["pipeline file hashes"]:
        diff = sorted(f for f in set(now) | set(clf["pipeline file hashes"])
                      if now.get(f) != clf["pipeline file hashes"].get(f))
        raise SystemExit("Pipeline files differ from those frozen with classifier v2: " + ", ".join(diff))
    return clf


def apply(model: dict, values: dict) -> dict:
    if any(values.get(k) is None or not math.isfinite(values[k]) for k in model["features"]):
        return {"probability": None, "flag": None, "note": "a feature has no finite value"}
    z = [(values[k] - m) / s for k, m, s in zip(model["features"], model["scaler"]["mean"], model["scaler"]["scale"])]
    logit = model["intercept"] + sum(model["coefficients"][k] * v for k, v in zip(model["features"], z))
    p = 1.0 / (1.0 + math.exp(-logit))
    return {"probability": p, "flag": p >= model["threshold"]}


def institutions() -> list[dict]:
    if not DRAW_PATH.exists():
        raise SystemExit("No test draw has been committed (data/v2/test draw.json).")
    return json.loads(DRAW_PATH.read_text())["institutions"]


def committed_batches() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(SCORES_DIR.glob("batch_*.json"))]


def done() -> set[str]:
    return {r["unitid"] for b in committed_batches() for r in b["results"]}


def structural(unitid: str, sector: str, finance: str) -> str | None:
    """The protocol's structural-reporting rule over the test window (the training rule, same logic)."""
    win = v2.WINDOWS[WINDOW]
    rows_any_form, rows_form, flagged = 0, 0, 0
    rev, exp_ = FORM_CODES[sector]
    for year in range(win["start_year"], win["end_year"]):
        found_any = False
        for s in v2.SECTORS:
            for f in (Path(finance) / s / str(year)).glob("*.csv"):
                with open(f, encoding="latin-1") as fh:
                    for row in csv.DictReader(fh):
                        if (row.get("UNITID") or "").strip() == unitid:
                            found_any = True
                            if s == sector:
                                rows_form += 1
                                if (row.get("X" + rev, "").strip().upper() == "A"
                                        or row.get("X" + exp_, "").strip().upper() == "A"):
                                    flagged += 1
                            break
        rows_any_form += found_any
    if rows_any_form == 0:
        return "no finance row of its own in any year of the window"
    if rows_form and flagged > rows_form / 2:
        return f"total revenue or total expenses flagged not applicable in {flagged} of {rows_form} years with a row"
    return None


def fit_one(inst: dict, sector: str, seed: int, compact: str, finance: str) -> dict | None:
    u = inst["unitid"]
    cache = tempfile.mkdtemp(prefix=f"cache_{u}_{seed}_")
    env = dict(os.environ)
    env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
    env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
    res_path = Path(tempfile.mkdtemp()) / "result.json"
    print(f"\n{'=' * 70}\n{inst['name']} ({u}), {sector}, seed {seed}\n{'=' * 70}", flush=True)
    subprocess.run([sys.executable, "v2_score_one.py", "--unitid", u, "--name", inst["name"],
                    "--sector", sector, "--window", WINDOW, "--seed", str(seed),
                    "--compact", str(Path(compact).resolve()), "--finance", str(Path(finance).resolve()),
                    "--out", str(res_path)], cwd=Path(__file__).resolve().parent, env=env)
    if not res_path.exists():
        print("RETRY NEXT RUN: the fit process ended without a result.")
        return None
    res = json.loads(res_path.read_text())
    if res["status"] in ("error", "download failure"):
        print(f"RETRY NEXT RUN: {res['status']}: {res.get('error', '')}")
        return None
    return res


def cmd_prefetch(finance: str) -> None:
    win = v2.WINDOWS[WINDOW]
    manifest, _ = v2.prefetch_finance(finance, win["start_year"], win["end_year"], required=True)
    Path(finance, "manifest.json").write_text(json.dumps(manifest, indent=2))


def cmd_shard(shard: int, of: int, minutes: float, compact: str, finance: str, out: str) -> None:
    clf = frozen()
    hashes = clf["pipeline file hashes"]
    start = time.time()
    seen = done()
    todo = [i for k, i in enumerate(x for x in institutions() if x["unitid"] not in seen) if k % of == shard]
    results = []
    path = Path(out) / f"shard_{shard}_of_{of}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    win = v2.WINDOWS[WINDOW]

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
        why = structural(u, sector, finance)
        if why:
            rec.update(status="structurally unscorable", reason=why)
        else:
            first = fit_one(inst, sector, v2.TEST_SEEDS[0], compact, finance)
            if first is None:
                continue
            if first["status"] != "scored":
                rec.update(first)
            else:
                fits = {v2.TEST_SEEDS[0]: first}
                for seed in v2.TEST_SEEDS[1:]:
                    r = fit_one(inst, sector, seed, compact, finance)
                    if r is None or r["status"] != "scored":
                        fits = None
                        print("RETRY NEXT RUN: a later seed did not return a score.")
                        break
                    fits[seed] = r
                if fits is None:
                    continue
                gaps = gap_features(first["availability"])
                seeds = {}
                for seed, r in fits.items():
                    vals = {**r["features"], "gap_trailing": gaps["gap_trailing"], "gap_internal": gaps["gap_internal"]}
                    seeds[str(seed)] = {"features": r["features"],
                                        "classifier v2": apply(clf["classifier v2"], vals),
                                        "variant without the missing-data features": apply(clf[VARIANT], vals)}
                flags = [s["classifier v2"]["flag"] for s in seeds.values()]
                rec.update({k: v for k, v in first.items() if k not in ("features",)})
                rec.update(gaps)
                rec.update({
                    "features (seed 7)": first["features"],
                    "score (seed 7)": seeds[str(v2.TEST_SEEDS[0])]["classifier v2"]["probability"],
                    "flag (seed 7)": seeds[str(v2.TEST_SEEDS[0])]["classifier v2"]["flag"],
                    "variant flag (seed 7, analysis only)":
                        seeds[str(v2.TEST_SEEDS[0])]["variant without the missing-data features"]["flag"],
                    "flags at seeds 7, 101, 202": flags,
                    "seeds disagree": len(set(flags)) > 1,
                    "by seed": seeds,
                })
        rec["scored at (UTC)"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        results.append(rec)
        save()
    save()
    print(f"Wrote {path} ({len(results)} results).")


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
    if not new:
        print("No new results to merge.")
        return
    n = len(committed_batches()) + 1
    v2.write_json(SCORES_DIR / f"batch_{n:03d}.json", {
        "protocol": "sampling protocol v2.md, phase 6 (test scoring; committed before any test outcome)",
        "merged at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pipeline file hashes (checked against classifier v2.json)": hashes,
        "shards": [{"machine": s["machine"], "results": len(s["results"])} for s in shards],
        "results": new,
    })
    print(f"Merged batch {n:03d}: {len(new)} new results; {len(done())} of {len(institutions())} "
          "test institutions now have one.")


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
