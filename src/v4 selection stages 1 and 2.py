"""
v4 channel selection, stages 1 and 2 ("channel selection protocol.md",
section 4 and Amendment 2), on the earlier scoring year (the 2014 frame).

Reads the committed gap values ("gap values at scoring years.csv") and
step 1's inputs (for size), then, and only then, the 2014 frame's closure
outcomes from the IPEDS header files HD2014 to HD2019 under the primary
coding of protocol v2 (src/v2_training_outcomes.py, code()). The 2019 frame's
outcomes are not read here; they belong to stage 3.

Stage 1, for each dimension alone, on the institutions with that dimension
available (matched coverage):
    baseline   logistic: log FTE + control
    with gap   logistic: log FTE + control + the dimension's features
               price: D_price; outcome (retention): D_over and D_under;
               four-year: D_4yr
    AUC of each, on out-of-fold predictions (stratified 10-fold, seed
    20261120); the gain and its paired bootstrap interval (2,000 resamples
    of institutions, seed 20261121, predictions held fixed)
Decision B: rank the dimensions by gain, carry the top three with a
positive gain (fewer if fewer are positive).
Stage 2, on the institutions with every carried dimension available:
    the carried gaps combined by the Spine's maximum (one feature, the
    largest of the carried direction-free gaps: D_price, D_outcome_ret,
    D_4yr), and as separate features (D_over and D_under for the outcome
    gap), each with the baseline, against the baseline.

Also reported: coverage, and how covered institutions differ from the rest
(control, size, closure rate); the outcome's components (closure date or
deletion, merger, disappearance); and, descriptively, which gap was largest
before each closure (by percentile within the frame, since the gaps are on
different scales).

Output: data/v4 channels/selection stages 1 and 2.json

Usage (GitHub Actions only, via v4_selection_stages_1_2.yml):
    cd src
    python "v4 selection stages 1 and 2.py"
"""

from __future__ import annotations

import csv
import datetime
import json
import math
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

import v2_training_outcomes as coding

HERE = Path(__file__).resolve().parent
DIR = HERE.parent / "data" / "v4 channels"
OUT = DIR / "selection stages 1 and 2.json"
FRAME = 2014
HD_FILES = list(range(2014, 2020))
CV_SEED, BOOT_SEED, BOOT_N, FOLDS = 20261120, 20261121, 2000, 10
MIN_HD_ROWS = 3000
DIMENSIONS = {"price": ["D_price"], "outcome (retention)": ["D_over", "D_under"], "four-year": ["D_4yr"]}
IOTA = {"price": "iota_price", "outcome (retention)": "iota_outcome_ret", "four-year": "iota_4yr"}
DIRECTION_FREE = {"price": "D_price", "outcome (retention)": "D_outcome_ret", "four-year": "D_4yr"}


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load() -> list[dict]:
    fte = {}
    with open(DIR / "inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["fiscal year"]) == FRAME and f(r["FTE"]):
                fte[r["unitid"]] = f(r["FTE"])
    rows = []
    with open(DIR / "gap values at scoring years.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["frame"]) != FRAME:
                continue
            rec = {"unitid": r["unitid"], "name": r["name"], "control": r["control"],
                   "log FTE": math.log(fte[r["unitid"]]) if fte.get(r["unitid"], 0) > 0 else None,
                   "price flag": r.get("price flag", ""), "outcome source": r.get("outcome source", ""),
                   "tau_out reported": r.get("tau_out reported", "")}
            for k in ("D_price", "D_over", "D_under", "D_outcome_ret", "D_4yr"):
                rec[k] = f(r.get(k))
            for k in IOTA.values():
                rec[k] = r.get(k) in ("1", "1.0")
            rows.append(rec)
    return rows


def outcomes(ids: list[str]) -> tuple[dict, list]:
    coding.SCORING_YEAR, coding.FILES = FRAME, HD_FILES
    files, tables = [], {}
    for y in HD_FILES:
        hd = coding.download_hd(y)
        t = coding.rows_by_id(hd["csv"])
        if len(t) < MIN_HD_ROWS:
            raise SystemExit(f"HD{y} yielded {len(t)} institutions; misread. Nothing recorded.")
        tables[y] = t
        files.append({k: v for k, v in hd.items() if k != "csv"} | {"institutions read": len(t)})
    return {u: coding.code(u, {y: tables[y].get(u) for y in HD_FILES}) for u in ids}, files


def design(rows, feats):
    X = [[r["log FTE"], 1.0 if r["control"] == "private nonprofit" else 0.0,
          1.0 if r["control"] == "for-profit" else 0.0] + [r[k] for k in feats] for r in rows]
    return np.array(X, float)


def oof(X, y) -> np.ndarray:
    p = np.zeros(len(y))
    for tr, te in StratifiedKFold(FOLDS, shuffle=True, random_state=CV_SEED).split(X, y):
        mu, sd = X[tr].mean(0), X[tr].std(0)
        sd[sd == 0] = 1
        m = LogisticRegression(C=1e6, max_iter=5000).fit((X[tr] - mu) / sd, y[tr])
        p[te] = m.predict_proba((X[te] - mu) / sd)[:, 1]
    return p


def compare(rows, feats_a, feats_b, label_a, label_b) -> dict:
    y = np.array([r["closed"] for r in rows], int)
    if y.sum() < FOLDS or (len(y) - y.sum()) < FOLDS:
        return {"N": len(y), "closures": int(y.sum()), "verdict": "too few closures for 10-fold cross-validation"}
    pa, pb = oof(design(rows, feats_a), y), oof(design(rows, feats_b), y)
    aa, ab = roc_auc_score(y, pa), roc_auc_score(y, pb)
    rng = np.random.default_rng(BOOT_SEED)
    diffs, n = [], len(y)
    for _ in range(BOOT_N):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            diffs.append(roc_auc_score(y[i], pb[i]) - roc_auc_score(y[i], pa[i]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"N": n, "closures": int(y.sum()), f"AUC, {label_a}": float(aa), f"AUC, {label_b}": float(ab),
            "gain": float(ab - aa), "gain 95% bootstrap": [float(lo), float(hi)],
            "bootstrap resamples used": len(diffs),
            "verdict": ("gain, interval above 0" if lo > 0 else "positive, interval includes 0" if ab > aa
                        else "no gain")}


def describe(group, rest) -> dict:
    def d(g):
        n = len(g)
        return {"N": n, "closure rate": (sum(r["closed"] for r in g) / n) if n else None,
                "median log FTE": float(np.median([r["log FTE"] for r in g])) if n else None,
                "control": {c: sum(r["control"] == c for r in g) for c in ("public", "private nonprofit", "for-profit")}}
    return {"covered": d(group), "not covered": d(rest),
            "wealth": "no wealth measure is in the committed inputs; not compared here"}


def main() -> None:
    rows = load()
    out, files = outcomes([r["unitid"] for r in rows])
    for r in rows:
        c = out[r["unitid"]]
        r["closed"] = bool(c["closed or failed (primary)"])
        r["grounds"] = c["standing grounds"]
    base = [r for r in rows if r["log FTE"] is not None]
    components = {"closed or failed (primary)": sum(r["closed"] for r in base),
                  "closure date or deletion (a or b)": sum(r["closed"] and bool({"a", "b"} & set(r["grounds"])) for r in base),
                  "merger (successor institution, c)": sum(r["closed"] and "c" in r["grounds"] for r in base),
                  "disappearance only (d)": sum(r["closed"] and r["grounds"] == ["d"] for r in base)}

    stage1 = {}
    for dim, feats in DIMENSIONS.items():
        cov = [r for r in base if r[IOTA[dim]]]
        res = compare(cov, [], feats, "size and sector", f"size, sector and {dim}")
        res["coverage"] = describe(cov, [r for r in base if not r[IOTA[dim]]])
        if dim == "outcome (retention)":
            res["direction-free outcome gap, for information"] = compare(
                cov, [], ["D_outcome_ret"], "size and sector", "size, sector and the direction-free outcome gap")
            res["by tau_out availability"] = {
                k: compare([r for r in cov if (r["tau_out reported"] == "True") == v], [], feats,
                           "size and sector", f"size, sector and {dim}") for k, v in (("reported", True), ("unreported", False))}
        stage1[dim] = res

    ranked = sorted((d for d in stage1 if "gain" in stage1[d]), key=lambda d: -stage1[d]["gain"])
    carried = [d for d in ranked if stage1[d]["gain"] > 0][:3]

    stage2 = {"carried (Decision B)": carried}
    if carried:
        cov = [r for r in base if all(r[IOTA[d]] for d in carried)]
        for r in cov:
            r["D_max"] = max(r[DIRECTION_FREE[d]] for d in carried)
        sep = [k for d in carried for k in DIMENSIONS[d]]
        stage2["combined by the maximum"] = compare(cov, [], ["D_max"], "size and sector", "size, sector and the maximum")
        stage2["separate features"] = compare(cov, [], sep, "size and sector", "size, sector and the carried gaps")
        stage2["coverage"] = describe(cov, [r for r in base if r not in cov])

    largest = {"price": 0, "outcome (retention)": 0, "four-year": 0, "none available": 0}
    pct = {}
    for dim in DIMENSIONS:
        vals = np.array([r[DIRECTION_FREE[dim]] for r in base if r[IOTA[dim]]])
        pct[dim] = vals
    for r in base:
        if not r["closed"]:
            continue
        ranks = {d: float((pct[d] <= r[DIRECTION_FREE[d]]).mean()) for d in DIMENSIONS if r[IOTA[d]] and len(pct[d])}
        largest[max(ranks, key=ranks.get) if ranks else "none available"] += 1

    DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "protocol": "channel selection protocol.md, section 4 and Amendment 2: stages 1 and 2 (2014 frame)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "frame": FRAME, "header files": files,
        "institutions in frame": len(rows), "with size": len(base), "outcome components": components,
        "settings": {"folds": FOLDS, "cross-validation seed": CV_SEED, "bootstrap resamples": BOOT_N,
                     "bootstrap seed": BOOT_SEED, "size": "log 12-month FTE, fiscal 2014", "sector": "control"},
        "stage 1": stage1, "ranking by gain": ranked, "stage 2": stage2,
        "largest gap before each closure (by percentile within the frame; descriptive)": largest,
        "program-length check (Amendment 3)": "not made: every four-year-gap result is reported without the check of "
                                              "Definition 15.2.13; the error can only weaken the gap's association with closure",
        "largest four-year gaps, for the catalog look-up (Amendment 3; names and gaps only)": (
            [{"unitid": r["unitid"], "name": r["name"], "control": r["control"], "D_4yr": r["D_4yr"]}
             for r in sorted((r for r in base if r["iota_4yr"]), key=lambda r: -r["D_4yr"])[:30]]
            if "four-year" in carried else "not needed: the four-year gap was not carried"),
        "note": "Selection-stage performance, used only to choose dimensions; never an estimate of v4's accuracy.",
    }, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"components": components, "stage 1": {d: {k: v for k, v in s.items() if k in ("N", "closures", "gain", "gain 95% bootstrap", "verdict")} for d, s in stage1.items()},
                      "carried": carried}, indent=1))


if __name__ == "__main__":
    main()
