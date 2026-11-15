"""
Phase 4 of "sampling protocol v2.md": classifier v2 fit and freeze.

Fits classifier v2 on every scored training institution, with its primary
outcome coding, exactly as the protocol fixes it:

  model      the features standardized, then logistic regression with
             scikit-learn's default L2 penalty (C = 1); fitted on all
             scored training institutions;
  features   the eight current features plus gap_trailing and
             gap_internal;
  threshold  10-fold stratified cross-validation on the training set
             (random seed 20261114): the probability cut, on a grid of
             0.01 steps from 0.01 to 0.99, that maximizes the mean J
             across folds, rounded to two decimals. Where several cuts
             share the maximum, the lowest is taken;
  freeze     the scaler, the coefficients, the threshold and the git blob
             hash of every file in the scoring pipeline are written to
             data/v2/classifier v2.json, which is committed before the
             test draw.

The cross-validated J is reported as an in-sample estimate only.

For the protocol's pre-specified analysis of the missing-data signal, the
same procedure is also run without gap_trailing and gap_internal, and that
variant is frozen beside the classifier, marked as analysis only; it never
decides a flag or a trigger.

The solver is given up to 10,000 iterations instead of scikit-learn's
default 100, so that the fit converges; this changes no setting of the
model itself.

The fit runs only if the training outcomes are committed and the event
floor is met (or the one second pass has been drawn and scored), and it
refuses if any scored institution lacks a finite value for any feature,
listing them, rather than dropping them silently.

Usage (GitHub Actions only, via fit_classifier_v2.yml):
    cd src
    python fit_classifier_v2.py
"""

from __future__ import annotations

import datetime
import json
import math
import subprocess

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

import v2_common as v2
from score_v2_training import PIPELINE_FILES, SCORES_DIR, pipeline_hashes
from v2_training_outcomes import OUT_PATH as OUTCOMES_PATH, committed

OUT_PATH = v2.V2_DIR / "classifier v2.json"
BASE_FEATURES = ["d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy", "debt_spike",
                 "delta_R_trend", "reserve_adequacy", "research_ratio"]
GAP_FEATURES = ["gap_trailing", "gap_internal"]
CV_SEED = 20261114
GRID = [round(0.01 * k, 2) for k in range(1, 100)]
MAX_ITER = 10_000


def j_at(prob: np.ndarray, y: np.ndarray, cut: float) -> float:
    flag = prob >= cut
    e = y.sum()
    s = (flag & (y == 1)).sum() / e
    f = (flag & (y == 0)).sum() / (len(y) - e)
    return float(s - f)


def fit(X: np.ndarray, y: np.ndarray):
    scaler = StandardScaler().fit(X)
    model = LogisticRegression(C=1.0, max_iter=MAX_ITER).fit(scaler.transform(X), y)
    return scaler, model


def fit_and_freeze(X: np.ndarray, y: np.ndarray, names: list[str]) -> dict:
    skf = StratifiedKFold(n_splits=10, shuffle=True, random_state=CV_SEED)
    per_fold = []
    for tr, te in skf.split(X, y):
        scaler, model = fit(X[tr], y[tr])
        prob = model.predict_proba(scaler.transform(X[te]))[:, 1]
        per_fold.append([j_at(prob, y[te], c) for c in GRID])
    per_fold = np.array(per_fold)
    mean_j = per_fold.mean(axis=0)
    best = int(np.flatnonzero(mean_j == mean_j.max())[0])
    cut = GRID[best]
    scaler, model = fit(X, y)
    prob_all = model.predict_proba(scaler.transform(X))[:, 1]
    return {
        "features": names,
        "scaler": {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()},
        "coefficients": dict(zip(names, model.coef_[0].tolist())),
        "intercept": float(model.intercept_[0]),
        "converged in iterations": int(model.n_iter_[0]),
        "threshold": cut,
        "cross-validated mean J at the threshold (in-sample estimate only)": float(mean_j[best]),
        "cross-validated J at the threshold, by fold": per_fold[:, best].tolist(),
        "cross-validated mean J on the whole grid": dict(zip([f"{c:.2f}" for c in GRID], mean_j.round(6).tolist())),
        "training institutions flagged at the threshold (in-sample)": int((prob_all >= cut).sum()),
    }


def main() -> None:
    outcomes_commit = committed(OUTCOMES_PATH)
    scores_commit = committed(SCORES_DIR)
    oc = json.loads(OUTCOMES_PATH.read_text())
    if oc["event floor"]["verdict"].startswith("not met:"):
        raise SystemExit("The event floor is not met and the one second pass has not been drawn and scored. "
                         "Draw it (draw_v2_sample.yml, training-second), score it, and run the outcomes again first.")
    results = {}
    for p in sorted(SCORES_DIR.glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            results[r["unitid"]] = r
    names = BASE_FEATURES + GAP_FEATURES
    rows, ys, ids, bad = [], [], [], []
    for inst in oc["institutions"]:
        if inst["status"] != "scored":
            continue
        r = results[inst["unitid"]]
        vals = [r["features"].get(k) for k in BASE_FEATURES] + [r.get(k) for k in GAP_FEATURES]
        if any(v is None or not math.isfinite(v) for v in vals):
            bad.append({"unitid": inst["unitid"], "name": inst["name"],
                        "non-finite": [k for k, v in zip(names, vals) if v is None or not math.isfinite(v)]})
            continue
        rows.append(vals)
        ys.append(int(inst["closed or failed (primary)"]))
        ids.append(inst["unitid"])
    if bad:
        raise SystemExit("These scored institutions lack a finite value for a feature; nothing is fitted "
                         "until this is settled: " + json.dumps(bad))
    X, y = np.array(rows, dtype=float), np.array(ys)
    if y.sum() < 10 or y.sum() == len(y):
        raise SystemExit(f"Only {y.sum()} closures among {len(y)} scored institutions; 10-fold stratified "
                         "cross-validation needs at least 10.")
    classifier = fit_and_freeze(X, y, names)
    without = fit_and_freeze(X[:, :len(BASE_FEATURES)], y, BASE_FEATURES)
    hashes = pipeline_hashes()
    out = {
        "protocol": "sampling protocol v2.md, phase 4 (classifier v2, frozen before the test draw)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "training scores (commit, time)": scores_commit,
        "training outcomes (commit, time)": outcomes_commit,
        "training set": {"scored institutions": int(len(y)), "closed or failed (primary)": int(y.sum()),
                         "closure rate": float(y.mean())},
        "model": "standardized features, logistic regression, L2 penalty, C = 1 (scikit-learn defaults; "
                 f"max_iter {MAX_ITER})",
        "threshold rule": "10-fold stratified cross-validation, seed 20261114, grid 0.01-0.99 in 0.01 steps, "
                          "maximum mean J across folds, lowest cut on ties",
        "classifier v2": classifier,
        "without the missing-data features (analysis only; never decides a flag)": without,
        "pipeline file hashes": hashes,
        "pipeline files": list(PIPELINE_FILES),
        "machine": v2.machine(),
    }
    v2.write_json(OUT_PATH, out)
    print(f"Wrote {OUT_PATH}: threshold {classifier['threshold']}, cross-validated mean J "
          f"{classifier['cross-validated mean J at the threshold (in-sample estimate only)']:.3f} "
          f"(in-sample estimate), on {len(y)} institutions with {y.sum()} closures.")


if __name__ == "__main__":
    main()
