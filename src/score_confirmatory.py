"""
Scores the 300-institution confirmatory sample, exactly as specified in
"sampling protocol.md" at the root of this repository. Read that file
first -- this script implements it and does not change any of its
rules.

HOW THE WORK IS SPLIT. A model fit depends only on the institution, not
on which slot it is being tried for, so the work is done in two
separate kinds of step:

1. Evaluate candidates (in parallel, across many GitHub Actions jobs).
   Each candidate institution gets the protocol's two checks, in
   order: the data check and the stability check (seeds 7, 101 and 202
   must all give the same flag). A candidate that fails a check is not
   fitted further. Every evaluation, pass or fail, is kept, because
   skipped institutions' later outcomes are part of the analysis
   ("institutional broken window").

2. Assign candidates to slots (in one job, in slot order). Each slot
   walks its own ordered list -- its selected institution, then its 25
   backups from "draw slots.json" -- and takes the first candidate that
   passed both checks and is not a duplicate. A candidate counts
   as a duplicate if it is any slot's selected institution (each
   selected institution belongs to its own slot) or if a lower-numbered
   slot has already taken it, so overlapping backup lists always
   resolve the same way: the lower-numbered slot wins. Slots are
   finalized strictly in order; a slot waiting on an unevaluated
   candidate holds up the finalizing of every slot after it (their
   candidates are still evaluated meanwhile), so a finalized slot can
   never be changed by a later run. A slot whose 25 backups are all
   used up without a pass is finalized as unfilled.

Each workflow run is one batch: it evaluates as many pending candidates
as fit in its time budget, finalizes what it can, and commits the batch
to data/confirmatory/scores/ along with the updated draw log and the
README progress line. Running it again resumes where the last run left
off. Nothing in this script looks up any institution's outcome.

FROZEN CONFIGURATION. Before doing anything, the script checks the git
blob hash of every frozen file listed in the protocol and stops if any
differs. Every fit uses the protocol's FY2019 window (start_year 2008,
end_year 2019: pipeline years 2008-2018, FY2009-FY2019, so the last
finance file is F1819), 300 draws, 300 tuning steps, 2 chains,
target_accept 0.9, cores 1, the Numba backend. Enrollment, completion,
tuition and admission rate come from the bulk College Scorecard file
(the release asset named in the protocol, checked by its SHA-256 in
build_scorecard_compact.py), never from the Scorecard API, which has no
record for institutions that have since closed. The governance override
is not applied. The flag is the frozen classifier's prediction at its
0.5 probability cut; the reported score and flag are those from seed 7.

DATA CHECK. Five consecutive fiscal years of complete finance data
ending in FY2019 means the four finance values the model reads
(revenue, institutional support, instruction, total expenses) parse for
each of FY2015-FY2019, read from the same downloaded files the fit
used. A candidate whose pipeline itself returns no features (an
incomplete Scorecard series anywhere in the window, missing finance or
debt years) also fails the data check, with the pipeline's own reason
recorded as the type of data gap.

STABILITY CHECK. Fits with seeds 7, 101 and 202 must all give the same
flag. This is the only check on the fit itself: under the protocol's
amendment of 2026-11-12, divergent transitions and R-hat are recorded
for every fit but do not cause a skip (see the protocol for why).

Usage (GitHub Actions only, via score_confirmatory.yml):
    cd src
    python score_confirmatory.py plan --out ../work/plan.json
    python build_scorecard_compact.py --out ../work/scorecard_compact.csv
    python score_confirmatory.py evaluate --plan ../work/plan.json --shard 0 --of 20 --minutes 300 --out ../work/eval --compact ../work/scorecard_compact.csv
    python score_confirmatory.py merge --evals ../work/evals --compact ../work/scorecard_compact.csv
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLOTS_PATH = ROOT / "data" / "confirmatory" / "draw slots.json"
DRAW_LOG_PATH = ROOT / "data" / "confirmatory" / "draw log.csv"
SCORES_DIR = ROOT / "data" / "confirmatory" / "scores"
README_PATH = ROOT / "README.md"
PANEL_PATH = ROOT / "data" / "panel" / "panel.json"


FROZEN_BLOBS = {
    "src/classifier.py": "13c946532f651501e3e99f8574a9ccdea8f4ae8d",
    "data/panel/panel.json": "8d1f5e4135ee278f80c4af937611ab68ff4b3f78",
    "src/model.py": "ec8aac432fd772def527ca8d7db4dfa4c2e1aaf5",
    "src/dynamics.py": "0fb853c22972a9ccdfd2a44de82fcbf7513c81f8",
    "src/real_adapter.py": "7bcd88039d990d131e0ef0ac31b16531fd9defc8",
    "src/score_institution.py": "30d65337f8e45cc88e84a48a99250a2943e0a765",
    "src/fetch_live_data.py": "d56d8231e6dd82bcd10a061f676ea40bd5e1ba76",
    "src/build_scorecard_compact.py": "ce3683908488ecd8f590a9a4021df255a3416352",
}

START_YEAR = 2008
END_YEAR = 2019
SAMPLER = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9,
               cores=1, compile_mode="NUMBA")
SEEDS = (7, 101, 202)
# Beyond the one candidate a waiting slot needs next, also queue its
# following LOOKAHEAD candidates, after every needed one, so a batch with
# spare time does not end early. Those extra evaluations are kept but
# only count if the slot actually reaches them.
LOOKAHEAD = 2
TARGET = 300
PROGRESS_PREFIX = "**Confirmatory test:**"
SCORECARD_NOTE: str | None = None  # set from --compact in merge, for the batch record

CONV_RE = re.compile(r"CONVERGENCE: (\d+) divergences, max rhat=([0-9.]+|nan|inf)")
PARAM_RE = re.compile(r"^  ([* ]) (\S+)\s+max_rhat=([0-9.]+|nan|inf)", re.M)
INSUFF_RE = re.compile(r"^(INSUFFICIENT [A-Z ]+?):", re.M)


# ---------------------------------------------------------------- checks

def blob_hash(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def verify_frozen() -> dict:
    bad = {}
    for rel, expected in FROZEN_BLOBS.items():
        got = blob_hash(ROOT / rel)
        if got != expected:
            bad[rel] = got
    if bad:
        for rel, got in bad.items():
            print(f"FROZEN FILE CHANGED: {rel} is {got}, protocol says {FROZEN_BLOBS[rel]}")
        raise SystemExit("A frozen file differs from the protocol. Not scoring.")
    print("Frozen files verified against the protocol's hashes.")
    return dict(FROZEN_BLOBS)


def load_slots() -> list[dict]:
    return json.loads(SLOTS_PATH.read_text())["slot list"]


def candidates_for(slot: dict) -> list[dict]:
    return [slot["selected"]] + list(slot["backups in order"])


def load_evaluations() -> dict[str, dict]:
    evals = {}
    for p in sorted(SCORES_DIR.glob("batch_*.json")):
        for e in json.loads(p.read_text()).get("evaluations", []):
            evals.setdefault(e["unitid"], e)
    return evals


def load_finalized() -> dict[int, dict]:
    done = {}
    for p in sorted(SCORES_DIR.glob("batch_*.json")):
        for f in json.loads(p.read_text()).get("finalized slots", []):
            done[f["slot"]] = f
    return done


# ------------------------------------------------------------- assignment

def walk(slots, evals, finalized):
    """Walks every slot in order. Returns (newly_finalized, frontier).
    frontier: unitids that need evaluating next, in slot order."""
    primaries = {s["selected"]["unitid"]: s["slot"] for s in slots}
    claimed = {f["unitid"] for f in finalized.values() if f.get("unitid")}
    newly, frontier, extra = [], [], []
    seen_req, seen_extra = set(), set()
    prefix_open = True
    tentative = set()

    for s in slots:
        n = s["slot"]
        if n in finalized:
            continue
        trail, chosen, pending = [], None, None
        cands = candidates_for(s)
        for idx, c in enumerate(cands):
            u = c["unitid"]
            if u in primaries and primaries[u] != n:
                trail.append((c, "skipped", "duplicate (another slot's selected institution)"))
                continue
            if u in claimed or u in tentative:
                trail.append((c, "skipped", "duplicate (taken by a lower-numbered slot)"))
                continue
            e = evals.get(u)
            if e is None:
                pending = c
                break
            if e["result"] == "pass":
                chosen = (c, e)
                break
            trail.append((c, "skipped", f"insufficient data: {e['failed check']} check ({e['gap']})"))

        if pending is not None:
            if pending["unitid"] not in seen_req:
                seen_req.add(pending["unitid"])
                frontier.append({"unitid": pending["unitid"], "name": pending["name"],
                                 "sector": pending["sector"], "for slot": n})
            ahead = 0
            for c in cands[idx + 1:]:
                u = c["unitid"]
                if ahead >= LOOKAHEAD:
                    break
                if (u in primaries and primaries[u] != n) or u in claimed or u in evals:
                    continue
                ahead += 1
                if u not in seen_extra:
                    seen_extra.add(u)
                    extra.append({"unitid": u, "name": c["name"], "sector": c["sector"],
                                  "for slot": n, "lookahead": True})
            prefix_open = False
            continue
        if chosen is not None:
            tentative.add(chosen[0]["unitid"])
        if prefix_open:
            rec = {"slot": n, "trail": [{"unitid": c["unitid"], "name": c["name"],
                                         "frame position": c["frame position"], "sector": c["sector"],
                                         "state": c["state"], "status": st, "reason": why}
                                        for c, st, why in trail]}
            if chosen is not None:
                c, e = chosen
                claimed.add(c["unitid"])
                rec.update({"unitid": c["unitid"], "name": c["name"], "frame position": c["frame position"],
                            "sector": c["sector"], "state": c["state"],
                            "probability": e["probability"], "flag": e["flag"]})
            else:
                rec.update({"unitid": None, "status": "unfilled (all 25 backups used)"})
            newly.append(rec)
    return newly, frontier + [e for e in extra if e["unitid"] not in seen_req]


# ------------------------------------------------------------- evaluation

def parse_fit_log(text: str) -> dict:
    out = {"divergences": None, "rhat_max_all": None, "rhat_max_free": None}
    m = CONV_RE.search(text)
    if m:
        out["divergences"] = int(m.group(1))
        out["rhat_max_all"] = float(m.group(2))
    free = [float(v) for mark, _, v in PARAM_RE.findall(text) if mark == "*"]
    if free:
        out["rhat_max_free"] = max(free)
    return out


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def finance_years_complete(unitid: str, sector: str) -> list[bool]:
    import fetch_live_data as fld
    window = [f"{y}-{str(y + 1)[2:]}" for y in range(START_YEAR, END_YEAR)]
    E, M, Wi, Wt, mask, _ = fld.parse_live_finance(unitid, window, f"/tmp/ipeds_live/{unitid}", sector=sector)
    import numpy as np
    ok = mask & ~np.isnan(E) & ~np.isnan(M) & ~np.isnan(Wi) & ~np.isnan(Wt)
    return [bool(x) for x in ok]


def evaluate_one(cand: dict, clf) -> dict:
    from score_institution import compute_features_for_institution
    u, name, sector = cand["unitid"], cand["name"], cand["sector"]
    rec = {"unitid": u, "name": name, "sector": sector, "fits": []}

    for seed in SEEDS:
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(Tee(sys.stdout, buf)):
                feats = compute_features_for_institution(
                    u, name, sector=sector, start_year=START_YEAR, end_year=END_YEAR,
                    random_seed=seed, debug_param_rhat=True, **SAMPLER)
        except Exception as e:
            # A crash (most often a network error reaching NCES or the
            # College Scorecard) says nothing about the institution, so it
            # is not recorded as a skip; the candidate is tried again in
            # the next batch.
            print(f"RETRY NEXT BATCH: pipeline error at seed {seed}: {type(e).__name__}: {e}")
            return None
        log = buf.getvalue()
        diag = parse_fit_log(log)
        if feats is None and "INSUFFICIENT FINANCE DATA: only" in log:
            # The download stage fetches whole-sector bulk files from NCES;
            # failing there is a download problem, not this institution's
            # data, so it is retried rather than recorded as a skip.
            print("RETRY NEXT BATCH: NCES bulk finance download failed.")
            return None

        if seed == 7:
            if feats is None:
                reasons = INSUFF_RE.findall(log)
                rec.update(result="fail", **{"failed check": "data"},
                           gap=(reasons[0].lower() if reasons else "pipeline returned no features"),
                           **diag)
                return rec
            years = finance_years_complete(u, sector)
            rec[f"finance years complete FY{START_YEAR + 1}-FY{END_YEAR}"] = years
            if not all(years[-5:]):
                missing = [f"FY{START_YEAR + 1 + i}" for i, ok in enumerate(years) if not ok and i >= len(years) - 5]
                rec.update(result="fail", **{"failed check": "data"},
                           gap="finance data incomplete in " + ", ".join(missing), **diag)
                return rec
        if feats is None:
            rec.update(result="fail", **{"failed check": "stability"},
                       gap=f"seed {seed} fit returned no features")
            return rec

        feats.governance_flag = False  # override not applied in the confirmatory run
        X = clf.scaler.transform(feats.to_vector().reshape(1, -1))
        prob = float(clf.model.predict_proba(X)[0, 1])
        pred = int(clf.model.predict(X)[0])
        rec["fits"].append({"seed": seed, "probability": prob,
                            "flag": "high_risk" if pred == 1 else "stable",
                            "features": {k: getattr(feats, k) for k in (
                                "d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy",
                                "debt_spike", "delta_R_trend", "reserve_adequacy", "research_ratio")},
                            **diag})

    flags = {f["flag"] for f in rec["fits"]}
    if len(flags) != 1:
        rec.update(result="fail", **{"failed check": "stability"},
                   gap="seeds disagree: " + ", ".join(f"{f['seed']}={f['flag']}" for f in rec["fits"]))
        return rec
    seed7 = rec["fits"][0]
    rec.update(result="pass", probability=seed7["probability"], flag=seed7["flag"])
    return rec


# --------------------------------------------------------------- commands

def cmd_plan(out: str) -> None:
    verify_frozen()
    slots = load_slots()
    _, frontier = walk(slots, load_evaluations(), load_finalized())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(frontier, indent=2))
    print(f"Plan: {len(frontier)} candidates to evaluate this batch.")


def cmd_evaluate(plan: str, shard: int, of: int, minutes: float, out: str, compact: str) -> None:
    verify_frozen()
    import fetch_live_data as fld
    fld.use_bulk_scorecard(compact)
    from classifier import RICDClassifier, load_panel
    clf = RICDClassifier()
    clf.fit(load_panel(PANEL_PATH))

    start = time.time()
    todo = [c for i, c in enumerate(json.loads(Path(plan).read_text())) if i % of == shard]
    results = []
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"eval_{shard}_of_{of}.json"
    env = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout.split()

    for c in todo:
        if (time.time() - start) / 60 > minutes:
            print(f"Time budget of {minutes} minutes reached; the rest waits for the next batch.")
            break
        print(f"\n{'=' * 70}\nCandidate {c['name']} ({c['unitid']}, {c['sector']}), slot {c['for slot']}\n{'=' * 70}", flush=True)
        rec = evaluate_one(c, clf)
        if rec is None:
            continue
        rec["evaluated at (UTC)"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        results.append(rec)
        path.write_text(json.dumps({"environment": env, "evaluations": results}, indent=2))
    path.write_text(json.dumps({"environment": env, "evaluations": results}, indent=2))
    print(f"Wrote {path} ({len(results)} evaluations)")


def update_readme(n_scored: int, n_unfilled: int) -> None:
    line = f"{PROGRESS_PREFIX} {n_scored} / {TARGET} scored, outcomes not yet checked."
    if n_unfilled:
        line = line[:-1] + f"; {n_unfilled} slots unfilled after all backups."
    lines = README_PATH.read_text().split("\n")
    for i, l in enumerate(lines):
        if l.startswith(PROGRESS_PREFIX):
            lines[i] = line
            break
    else:
        lines[1:1] = ["", line]
    README_PATH.write_text("\n".join(lines))


def cmd_merge(evals_dir: str, compact: str | None) -> None:
    global SCORECARD_NOTE
    SCORECARD_NOTE = str(Path(compact).with_suffix(".json")) if compact else None
    frozen = verify_frozen()
    existing = load_evaluations()
    new_evals, envs = [], []
    for p in sorted(Path(evals_dir).rglob("eval_*.json")):
        d = json.loads(p.read_text())
        envs.append(d.get("environment", []))
        for e in d.get("evaluations", []):
            if e["unitid"] not in existing:
                existing[e["unitid"]] = e
                new_evals.append(e)

    slots = load_slots()
    finalized = load_finalized()
    newly, frontier = walk(slots, existing, finalized)
    if not new_evals and not newly:
        print("Nothing new this batch.")
        return

    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    n = len(list(SCORES_DIR.glob("batch_*.json"))) + 1
    batch = {
        "protocol": "sampling protocol.md",
        "batch": n,
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "frozen file hashes": frozen,
        "scorecard file": json.loads(Path(SCORECARD_NOTE).read_text()) if SCORECARD_NOTE else None,
        "environment": sorted({pkg for env in envs for pkg in env}),
        "evaluations": new_evals,
        "finalized slots": newly,
    }
    (SCORES_DIR / f"batch_{n:03d}.json").write_text(json.dumps(batch, indent=2))

    with open(DRAW_LOG_PATH, "a", newline="") as f:
        w = csv.writer(f)
        for rec in newly:
            for t in rec["trail"]:
                w.writerow([rec["slot"], t["frame position"], t["unitid"], t["name"], t["sector"],
                            t["state"], "skipped at scoring", f"{t['reason']}; batch {n}"])
            if rec.get("unitid"):
                w.writerow([rec["slot"], rec["frame position"], rec["unitid"], rec["name"], rec["sector"],
                            rec["state"], "scored",
                            f"probability {rec['probability']:.4f}, flag {rec['flag']}; batch {n}"])
            else:
                w.writerow([rec["slot"], "", "", "", "", "", "unfilled", f"all 25 backups used; batch {n}"])

    all_final = {**finalized, **{r["slot"]: r for r in newly}}
    n_scored = sum(1 for r in all_final.values() if r.get("unitid"))
    n_unfilled = sum(1 for r in all_final.values() if not r.get("unitid"))
    update_readme(n_scored, n_unfilled)
    print(f"Batch {n}: {len(new_evals)} candidates evaluated, {len(newly)} slots finalized; "
          f"{n_scored} / {TARGET} scored so far, {len(frontier)} candidates queued for the next batch.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--out", required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("--plan", required=True); e.add_argument("--shard", type=int, required=True)
    e.add_argument("--of", type=int, required=True); e.add_argument("--minutes", type=float, default=300)
    e.add_argument("--out", required=True); e.add_argument("--compact", required=True)
    m = sub.add_parser("merge"); m.add_argument("--evals", required=True); m.add_argument("--compact")
    a = ap.parse_args()
    if a.cmd == "plan":
        cmd_plan(a.out)
    elif a.cmd == "evaluate":
        cmd_evaluate(a.plan, a.shard, a.of, a.minutes, a.out, a.compact)
    else:
        cmd_merge(a.evals, a.compact)


if __name__ == "__main__":
    main()
