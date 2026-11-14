"""
Phase 2 of "sampling protocol v2.md": scores the training institutions.

Every institution in the committed training draw (and in the second pass,
if the protocol's event floor required one) is scored once, at seed 7,
over the training window (fiscal years 2004-2014), with the gap-tolerant
pipeline. For each institution the result is one of:

  scored                      its eight features, the years of data that
                              were present, and the two missing-data
                              features computed from them;
  structurally unscorable     it has no finance row of its own in any year
                              of the window, or IPEDS flags its total
                              revenue or total expenses "not applicable"
                              in most years in which it has a row;
  unscorable                  it does not meet the protocol's minimum
                              record, with the pipeline's own reason.

A pipeline error or a failed NCES download says nothing about the
institution, so it is not recorded; the institution is tried again in the
next run. Nothing here looks up any outcome.

The work is split into shards that run in parallel; each shard writes its
results to a file, and the merge step adds them to the committed record as
the next numbered batch in data/v2/training scores/. A run picks up only
institutions not already in a committed batch, so the workflow is simply
run again until every institution has a result. Every batch records the
git blob hash of each pipeline file, and a run refuses to start if any of
them differs from the hashes in the first committed batch, so every
training institution is scored by the same code.

Usage (GitHub Actions only, via score_v2_training.yml):
    cd src
    python score_v2_training.py prefetch --finance ../work/finance
    python score_v2_training.py shard --shard 0 --of 4 --minutes 300 \\
        --compact ../work/scorecard_compact.csv --finance ../work/finance --out ../work/evals [--cold]
    python score_v2_training.py merge --evals ../work/evals
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
import time
from pathlib import Path

import v2_common as v2

SCORES_DIR = v2.V2_DIR / "training scores"
DRAWS = ("training", "training-second")
PIPELINE_FILES = ("score_institution.py", "model.py", "fetch_live_data.py", "real_adapter.py",
                  "dynamics.py", "jump_diffusion.py", "v2_common.py", "v2_score_one.py",
                  "score_v2_training.py")
FORM_CODES = {"private": ("F2B01", "F2B02"), "public": ("F1D01", "F1D02"), "forprofit": ("F3D09", "F3B02")}


def pipeline_hashes() -> dict:
    src = Path(__file__).resolve().parent
    out = {f: subprocess.run(["git", "hash-object", str(src / f)], capture_output=True, text=True,
                             check=True).stdout.strip() for f in PIPELINE_FILES}
    lock = v2.ROOT / "requirements v2 lock.txt"
    if lock.exists():
        out["requirements v2 lock.txt"] = subprocess.run(["git", "hash-object", str(lock)], capture_output=True,
                                                         text=True, check=True).stdout.strip()
    return out


def committed_batches() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(SCORES_DIR.glob("batch_*.json"))]


def check_hashes() -> dict:
    now = pipeline_hashes()
    batches = committed_batches()
    if batches and batches[0]["pipeline file hashes"] != now:
        diff = [f for f in now if batches[0]["pipeline file hashes"].get(f) != now[f]]
        raise SystemExit("Pipeline files differ from those the first training batch was scored with: "
                         + ", ".join(diff) + ". Every training institution must be scored by the same code.")
    return now


def institutions() -> list[dict]:
    out = []
    for name in DRAWS:
        p = v2.V2_DIR / f"{name} draw.json"
        if p.exists():
            out += [{**i, "draw": name} for i in json.loads(p.read_text())["institutions"]]
    if not out:
        raise SystemExit("No training draw has been committed (data/v2/training draw.json).")
    return out


def done() -> set[str]:
    return {r["unitid"] for b in committed_batches() for r in b["results"]}


def structural(unitid: str, sector: str, finance: str) -> str | None:
    """The protocol's structural-reporting rule, read from the prefetched finance files."""
    win = v2.WINDOWS["training"]
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


def gap_features(av: dict) -> dict:
    """gap_trailing and gap_internal, as the protocol defines them."""
    reported = [e and f for e, f in zip(av["enrollment"], av["finance"])]
    anything = [e or f for e, f in zip(av["enrollment"], av["finance"])]
    if not any(anything):
        return {"gap_trailing": None, "gap_internal": None, "first reporting year": None}
    first = anything.index(True)
    n = len(reported) - first
    tail = 0
    for r in reversed(reported[first:]):
        if r:
            break
        tail += 1
    last_reported = max((i for i, r in enumerate(reported) if r), default=None)
    internal = 0 if last_reported is None else sum(1 for i in range(first, last_reported + 1) if not reported[i])
    return {"gap_trailing": tail / n, "gap_internal": internal / n,
            "first reporting year": av["years"][first]}


def cmd_prefetch(finance: str) -> None:
    win = v2.WINDOWS["training"]
    manifest, _ = v2.prefetch_finance(finance, win["start_year"], win["end_year"], required=True)
    Path(finance, "manifest.json").write_text(json.dumps(manifest, indent=2))


def cmd_shard(shard: int, of: int, minutes: float, compact: str, finance: str, out: str, cold: bool) -> None:
    hashes = check_hashes()
    start = time.time()
    seen = done()
    todo = [i for k, i in enumerate(x for x in institutions() if x["unitid"] not in seen) if k % of == shard]
    results = []
    path = Path(out) / f"shard_{shard}_of_{of}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    win = v2.WINDOWS["training"]
    for inst in todo:
        if (time.time() - start) / 60 > minutes:
            print(f"Time budget of {minutes} minutes reached; the rest waits for the next run.")
            break
        u = inst["unitid"]
        sector = v2.finance_sector(u, inst["sector"], finance, win["end_year"])
        rec = {"unitid": u, "name": inst["name"], "draw": inst["draw"], "slot": inst["slot"],
               "sector": inst["sector"], "finance form sector": sector}
        why = structural(u, sector, finance)
        if why:
            rec.update(status="structurally unscorable", reason=why)
        else:
            env = dict(os.environ)
            if cold:
                cache = tempfile.mkdtemp(prefix=f"cache_{u}_")
                env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
                env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
            res_path = Path(tempfile.mkdtemp()) / "result.json"
            print(f"\n{'=' * 70}\n{inst['name']} ({u}), {sector}\n{'=' * 70}", flush=True)
            subprocess.run([sys.executable, "v2_score_one.py", "--unitid", u, "--name", inst["name"],
                            "--sector", sector, "--window", "training", "--seed", str(v2.TRAINING_SEED),
                            "--compact", str(Path(compact).resolve()), "--finance", str(Path(finance).resolve()),
                            "--out", str(res_path)], cwd=Path(__file__).resolve().parent, env=env)
            if not res_path.exists():
                print("RETRY NEXT RUN: the fit process ended without a result.")
                continue
            res = json.loads(res_path.read_text())
            if res["status"] in ("error", "download failure"):
                print(f"RETRY NEXT RUN: {res['status']}: {res.get('error', '')}")
                continue
            rec.update(res)
            if res["status"] == "scored":
                rec.update(gap_features(res["availability"]))
        rec["scored at (UTC)"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        results.append(rec)
        path.write_text(json.dumps({"pipeline file hashes": hashes, "machine": v2.machine(),
                                    "cold compile cache per institution": cold, "results": results}, indent=2))
    path.write_text(json.dumps({"pipeline file hashes": hashes, "machine": v2.machine(),
                                "cold compile cache per institution": cold, "results": results}, indent=2))
    print(f"Wrote {path} ({len(results)} results).")


def cmd_merge(evals: str) -> None:
    hashes = check_hashes()
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
        "protocol": "sampling protocol v2.md, phase 2 (training scoring; no outcome looked up)",
        "merged at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pipeline file hashes": hashes,
        "shards": [{"machine": s["machine"], "cold compile cache per institution": s["cold compile cache per institution"],
                    "results": len(s["results"])} for s in shards],
        "results": new,
    })
    total = len(institutions())
    have = len(done())
    print(f"Merged batch {n:03d}: {len(new)} new results; {have} of {total} training institutions now have one.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prefetch"); p.add_argument("--finance", required=True)
    p = sub.add_parser("shard")
    for a in ("--compact", "--finance", "--out"):
        p.add_argument(a, required=True)
    p.add_argument("--shard", type=int, required=True)
    p.add_argument("--of", type=int, required=True)
    p.add_argument("--minutes", type=float, default=300)
    p.add_argument("--cold", action="store_true")
    p = sub.add_parser("merge"); p.add_argument("--evals", required=True)
    a = ap.parse_args()
    if a.cmd == "prefetch":
        cmd_prefetch(a.finance)
    elif a.cmd == "shard":
        cmd_shard(a.shard, a.of, a.minutes, a.compact, a.finance, a.out, a.cold)
    else:
        cmd_merge(a.evals)


if __name__ == "__main__":
    main()
