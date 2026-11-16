"""
Phase 1 of "sampling protocol v3.md": classifier v3, the size-and-sector
baseline and the anchor sensor, fit and freeze.

Fits all three on the development set, exactly as the protocol fixes them,
before the v3 test institutions are listed:

  development set  every scored institution of the v2 training set (scoring
                   year 2014) and of the v2 test (scoring year 2019), as
                   rescored with the v3 pipeline (the drift terms of RICD
                   §10.3a switched on) in data/v3/development scores/, with
                   its primary-coding outcome from the committed v2 outcome
                   files (for the v2 test, the corrected phase 8 run);
  features         the eight model features at seed 7, gap_trailing and
                   gap_internal; forprofit, which is 1 for an institution in
                   the for-profit sector of its draw and 0 otherwise; the
                   three enrollment features of v3_enrollment.py; and the
                   five drift features of v3_common.DRIFT_FEATURES;
  model            the features standardized, then logistic regression with
                   scikit-learn's default L2 penalty (C = 1);
  thresholds       two: one for for-profit institutions and one for public
                   and private nonprofit institutions. Both are fixed
                   together by 10-fold stratified cross-validation on the
                   development set (random seed 20261114, folds stratified
                   on outcome and sector together): the pair of cuts that
                   maximizes the mean J across folds, with the nonprofit
                   cut on a grid of 0.01 to 0.99 and the for-profit cut on
                   a grid of 0.00 to 0.99, in 0.01 steps (a cut of 0.00
                   flags every for-profit institution). On ties the lowest
                   nonprofit cut is taken, then the lowest for-profit cut.

The size-and-sector baseline, which decides the protocol's second verdict
(whether the tracker's own features add anything), is fitted and frozen
beside it by exactly the same procedure, with only forprofit and the
three enrollment features.

The anchor sensor (RICD §10.5b.13c) is fitted on the same institutions:
the primary outcome is regressed, by logistic regression without an
intercept, with non-negative coefficients and the same L2 penalty as the
classifier (C = 1), on the anchor inputs
f_approp, f_gift (each capped at 1) and S_par from data/v3/anchors.json,
with classifier v3's out-of-fold log-odds as an offset, so that only the
anchor terms are estimated. Its anchored flag uses classifier v3's own
frozen cuts, so that anchoring can only clear a flag (Proposition
10.5b.13c.1). An institution with no anchor record, or no total expenses,
is given anchor inputs of 0 and counted.

Freeze: the scalers, coefficients, intercepts and cuts of both models, the
anchor coefficients, the git blob hash of every file of the v3 scoring
pipeline, and the processor of every development result are written to
data/v3/classifier v3.json, which is committed before the test frame is
listed. The fit refuses to run unless every development institution has a
v3 result and every development batch ran with the current pipeline files.

The cross-validated estimates are reported as in-sample estimates only.
The solver is given up to 10,000 iterations so that the fit converges;
this changes no setting of the model itself.

Usage (GitHub Actions only, via fit_classifier_v3.yml):
    cd src
    python fit_classifier_v3.py --compact ../work/scorecard_compact.csv
"""


from __future__ import annotations

import argparse
import datetime
import json
import math

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

import v2_common as v2
import v3_enrollment as enr
import v3_common as v3c
from scipy.optimize import minimize
from scipy.special import expit
from v2_training_outcomes import committed
from score_v2_training import gap_features

V3_DIR = v2.ROOT / "data" / "v3"
OUT_PATH = V3_DIR / "classifier v3.json"
DEV_SCORES = V3_DIR / "development scores"
ANCHORS = V3_DIR / "anchors.json"
TRAIN_OUTCOMES = v2.V2_DIR / "training outcomes.json"
TEST_OUTCOMES = v2.V2_DIR / "test outcomes.json"
CLASSIFIER_V2 = v2.V2_DIR / "classifier v2.json"
ANCHOR_INPUTS = ["f_approp", "f_gift", "S_par"]

BASE_FEATURES = ["d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy", "debt_spike",
                 "delta_R_trend", "reserve_adequacy", "research_ratio"]
FEATURES = BASE_FEATURES + ["gap_trailing", "gap_internal", "forprofit"] + enr.FEATURES + list(v3c.DRIFT_FEATURES)
BASELINE_FEATURES = ["forprofit"] + enr.FEATURES
CV_SEED = 20261114
GRID_NP = [round(0.01 * k, 2) for k in range(1, 100)]
GRID_FP = [round(0.01 * k, 2) for k in range(0, 100)]
MAX_ITER = 10_000


def dev_batches() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(DEV_SCORES.glob("batch_*.json"))]


def anchor_inputs(anchors: dict, era: int, unitid: str) -> tuple[dict, bool]:
    rec = anchors["cohorts"][str(era)]["records"].get(unitid)
    if rec is None or rec.get("W") is None:
        return {k: 0.0 for k in ANCHOR_INPUTS}, False
    return {"f_approp": min(rec["f_approp"] or 0.0, 1.0), "f_gift": min(rec["f_gift"] or 0.0, 1.0),
            "S_par": float(rec["S_par"])}, True


def development_set(compact: str, hashes: dict) -> tuple[list[dict], dict]:
    provenance = {"development scores (commit, time)": committed(DEV_SCORES),
                  "anchors (commit, time)": committed(ANCHORS)}
    batches = dev_batches()
    if not batches:
        raise SystemExit("No development scores are committed (data/v3/development scores/).")
    stale = [i + 1 for i, b in enumerate(batches) if b["pipeline file hashes"] != hashes]
    if stale:
        raise SystemExit(f"Development batches {stale} ran with pipeline files other than the current ones.")
    res = {r["key"]: r for b in batches for r in b["results"]}
    anchors = json.loads(ANCHORS.read_text())
    series = enr.load(compact)
    rows, missing, processors = [], [], {}
    for era, outcomes_path in ((2014, TRAIN_OUTCOMES), (2019, TEST_OUTCOMES)):
        provenance[f"outcomes, scoring year {era} (commit, time)"] = committed(outcomes_path)
        for inst in json.loads(outcomes_path.read_text())["institutions"]:
            if inst["status"] != "scored":
                continue
            r = res.get(f"{era}:{inst['unitid']}")
            if r is None:
                missing.append(f"{era}:{inst['unitid']}")
                continue
            processors[r["processor"]] = processors.get(r["processor"], 0) + 1
            if r["status"] != "scored":
                rows.append({"unitid": inst["unitid"], "name": inst["name"], "scoring year": era,
                             "sector": inst["sector"], "closed": int(inst["closed or failed (primary)"]),
                             "unscorable with the drift terms": r.get("reason", r["status"])})
                continue
            gaps = gap_features(r["availability"])
            drift = r.get("drift") or {}
            anc, has = anchor_inputs(anchors, era, inst["unitid"])
            vals = {**{k: r["features"].get(k) for k in BASE_FEATURES},
                    "gap_trailing": gaps["gap_trailing"], "gap_internal": gaps["gap_internal"],
                    "forprofit": 1.0 if inst["sector"] == "forprofit" else 0.0,
                    **enr.features(series.get(inst["unitid"]), era),
                    **{k: drift.get(k) for k in v3c.DRIFT_FEATURES}}
            rows.append({"unitid": inst["unitid"], "name": inst["name"], "scoring year": era,
                         "sector": inst["sector"], "closed": int(inst["closed or failed (primary)"]),
                         "processor": r["processor"], "values": vals, "anchor": anc, "anchor record": has})
    if missing:
        raise SystemExit(f"{len(missing)} development institutions have no v3 result yet: {missing[:20]}")
    provenance["processors of the development results"] = processors
    return rows, provenance


def j_of(flag: np.ndarray, y: np.ndarray) -> float | None:
    e = int(y.sum())
    if e == 0 or e == len(y):
        return None
    return float((flag & (y == 1)).sum() / e - (flag & (y == 0)).sum() / (len(y) - e))


def fit(X: np.ndarray, y: np.ndarray):
    scaler = StandardScaler().fit(X)
    model = LogisticRegression(C=1.0, max_iter=MAX_ITER).fit(scaler.transform(X), y)
    return scaler, model


def fit_and_freeze(X: np.ndarray, y: np.ndarray, fp: np.ndarray, names: list[str]) -> tuple[dict, dict]:
    np_ = ~fp
    strata = y * 2 + fp.astype(int)
    folds = list(StratifiedKFold(n_splits=10, shuffle=True, random_state=CV_SEED).split(X, strata))
    oof = np.zeros(len(y))
    grid_j = np.zeros((len(folds), len(GRID_NP), len(GRID_FP)))
    for f, (tr, te) in enumerate(folds):
        scaler, model = fit(X[tr], y[tr])
        p = model.predict_proba(scaler.transform(X[te]))[:, 1]
        oof[te] = p
        yy, ff = y[te], fp[te]
        for i, tn in enumerate(GRID_NP):
            base = (~ff) & (p >= tn)
            for j, tf in enumerate(GRID_FP):
                grid_j[f, i, j] = j_of(base | (ff & (p >= tf)), yy)
    mean_j = grid_j.mean(axis=0)
    i, j = sorted(map(tuple, np.argwhere(mean_j == mean_j.max())))[0]   # lowest nonprofit, then for-profit cut
    t_np, t_fp = GRID_NP[i], GRID_FP[j]
    scaler, model = fit(X, y)
    oof_flag = np.where(fp, oof >= t_fp, oof >= t_np)
    frozen = {
        "features": names,
        "scaler": {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()},
        "coefficients": dict(zip(names, model.coef_[0].tolist())),
        "intercept": float(model.intercept_[0]),
        "converged in iterations": int(model.n_iter_[0]),
        "threshold, public and private nonprofit": t_np,
        "threshold, for-profit": t_fp,
    }
    estimates = {
        "mean J across folds at the cuts": float(mean_j[i, j]),
        "out-of-fold J, all institutions": j_of(oof_flag, y),
        "out-of-fold J, public and private nonprofit": j_of(oof_flag[np_], y[np_]),
        "out-of-fold closures flagged, public and private nonprofit":
            f"{int((oof_flag & np_ & (y == 1)).sum())} of {int(y[np_].sum())}",
        "out-of-fold nonprofit institutions flagged": int((oof_flag & np_).sum()),
        "out-of-fold AUC, public and private nonprofit": float(roc_auc_score(y[np_], oof[np_])),
    }
    return frozen, estimates, oof


def fit_anchor(A: np.ndarray, offset: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Non-negative coefficients of the anchor inputs, no intercept, with the tracker's log-odds as offset
    and the same L2 penalty as scikit-learn's default (C = 1)."""
    def nll(b):
        z = offset - A @ b              # anchoring lowers the log-odds of closure
        return float(np.sum(np.logaddexp(0.0, z) - y * z) + 0.5 * b @ b)
    def grad(b):
        p = expit(offset - A @ b)
        return -(A.T @ (p - y)) + b
    r = minimize(nll, np.zeros(A.shape[1]), jac=grad, method="L-BFGS-B",
                 bounds=[(0.0, None)] * A.shape[1], options={"maxiter": 10_000})
    if not r.success:
        raise SystemExit(f"The anchor fit did not converge: {r.message}")
    return r.x


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", required=True)
    a = ap.parse_args()
    if OUT_PATH.exists():
        raise SystemExit("Classifier v3 has already been frozen. Refusing to fit again.")
    hashes = v3c.pipeline_hashes()
    allrows, provenance = development_set(a.compact, hashes)
    dropped = [r for r in allrows if "values" not in r]
    rows = [r for r in allrows if "values" in r]
    bad = [{"unitid": r["unitid"], "non-finite": [k for k, v in r["values"].items() if v is None or not math.isfinite(v)]}
           for r in rows if any(v is None or not math.isfinite(v) for v in r["values"].values())]
    if bad:
        raise SystemExit(f"Development institutions without a finite value for a feature: {json.dumps(bad)}")
    y = np.array([r["closed"] for r in rows])
    fp = np.array([r["values"]["forprofit"] == 1.0 for r in rows])
    np_ = ~fp
    X = np.array([[r["values"][k] for k in FEATURES] for r in rows], dtype=float)
    Xb = np.array([[r["values"][k] for k in BASELINE_FEATURES] for r in rows], dtype=float)
    A = np.array([[r["anchor"][k] for k in ANCHOR_INPUTS] for r in rows], dtype=float)
    v3, v3_est, oof = fit_and_freeze(X, y, fp, FEATURES)
    base, base_est, _ = fit_and_freeze(Xb, y, fp, BASELINE_FEATURES)

    # anchor sensor: offset = classifier v3's out-of-fold log-odds
    oof_c = np.clip(oof, 1e-12, 1 - 1e-12)
    offset = np.log(oof_c / (1 - oof_c))
    b = fit_anchor(A, offset, y)
    anch_p = expit(offset - A @ b)
    t_np, t_fp = v3["threshold, public and private nonprofit"], v3["threshold, for-profit"]
    flag = np.where(fp, oof >= t_fp, oof >= t_np)
    anch_flag = np.where(fp, anch_p >= t_fp, anch_p >= t_np)
    anchor = {
        "inputs": ANCHOR_INPUTS,
        "coefficients (kappa_anch times theta_k; non-negative)": dict(zip(ANCHOR_INPUTS, b.tolist())),
        "cap on f_approp and f_gift": 1.0,
        "penalty": "L2, C = 1, no intercept, classifier v3's out-of-fold log-odds as offset",
        "cuts": "classifier v3's frozen cuts (anchoring can only clear a flag)",
        "development institutions without an anchor record or total expenses (inputs set to 0)":
            int(sum(1 for r in rows if not r["anchor record"])),
    }
    anchor_est = {
        "out-of-fold J, classifier v3 flag": j_of(flag, y),
        "J, anchored flag (anchor coefficients fitted in-sample)": j_of(anch_flag, y),
        "flags cleared by anchoring": int((flag & ~anch_flag).sum()),
        "of which closed": int((flag & ~anch_flag & (y == 1)).sum()),
        "AUC of the scale-free anchor capacity for survival, among flagged institutions":
            (float(roc_auc_score(1 - y[flag], (A @ b)[flag]))
             if 0 < int(y[flag].sum()) < int(flag.sum()) else None),
    }

    out = {
        "protocol": "sampling protocol v3.md, phase 1 (classifier v3 and the size-and-sector baseline, "
                    "frozen before the test frame is listed)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **provenance,
        "classifier v2 (commit, time)": committed(CLASSIFIER_V2),
        "development set": {
            "scored institutions": int(len(y)), "closed or failed (primary)": int(y.sum()),
            "by scoring year": {str(e): {"N": sum(1 for r in rows if r["scoring year"] == e),
                                         "closed": sum(r["closed"] for r in rows if r["scoring year"] == e)}
                                for e in (2014, 2019)},
            "public and private nonprofit": {"N": int(np_.sum()), "closed": int(y[np_].sum())},
            "for-profit": {"N": int(fp.sum()), "closed": int(y[fp].sum())}},
        "model": f"standardized features, logistic regression, L2 penalty, C = 1 (max_iter {MAX_ITER})",
        "threshold rule": "two cuts, nonprofit (grid 0.01-0.99) and for-profit (grid 0.00-0.99), 0.01 steps, "
                          "fixed together by 10-fold cross-validation stratified on outcome and sector, seed "
                          "20261114, maximum mean J across folds, lowest nonprofit then lowest for-profit cut on ties",
        "classifier v3": v3,
        "size-and-sector baseline": base,
        "anchor sensor": anchor,
        "cross-validated estimates (in-sample only; not a test result)": {
            "classifier v3": v3_est,
            "size-and-sector baseline": base_est,
            "anchor sensor": anchor_est,
            "J of flagging every for-profit institution and nothing else": j_of(fp, y),
        },
        "development institutions scored in v2 but unscorable with the drift terms":
            [{k: r[k] for k in ("unitid", "name", "scoring year", "closed", "unscorable with the drift terms")}
             for r in dropped],
        "pipeline file hashes": hashes,
        "pipeline files": list(v3c.PIPELINE_FILES),
        "machine": v2.machine(),
    }
    v2.write_json(OUT_PATH, out)
    print(f"Wrote {OUT_PATH}: classifier v3 cuts nonprofit {v3['threshold, public and private nonprofit']}, "
          f"for-profit {v3['threshold, for-profit']}; in-sample estimates: {json.dumps(v3_est)}; "
          f"baseline: {json.dumps(base_est)}; anchor: {json.dumps(anchor)} {json.dumps(anchor_est)}")


if __name__ == "__main__":
    main()
