"""
v4 value dimension (item 12): the single held-out comparison on the 2019
frame ("channel selection protocol.md", Amendments 8, 10 and 11).

Reads the College Scorecard yearly files from the repository's release
asset: the primary reading D_value = 1 - (BBRR2_FED_UG_MAKEPROG +
BBRR2_FED_UG_PAIDINFULL) and CDR3 from the 2018-19 file, and ten-year
median earnings from the latest file up to 2018-19 with a value (searched
back to the 2009-10 file). Joins them
to the 2019 frame and its outcomes (HD2019 onward), then compares size and
sector alone with size, sector and D_value:

  primary   each OPEID6 counted once (campus weight 1/k), stratified group
            10-fold cross-validation by OPEID6, paired bootstrap resampling
            OPEID6 identifiers
  check     campus level, unweighted (Amendment 2 settings)

The secondary readings (CDR3, D_earn) are compared at campus level and
reported only. No development stage exists for this dimension (the
repayment columns begin with the 2018-19 file); stated in the output.

Output: data/v4 channels/value dimension 2019.json and
"value dimension values.csv".

Usage (GitHub Actions only, via v4_value_dimension.yml):
    cd src
    python "v4 value dimension.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "v4 channels" / "value dimension 2019.json"
OUT_CSV = HERE.parent / "data" / "v4 channels" / "value dimension values.csv"


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


st = _load("stages", "v4 selection stages 1 and 2.py")
s3 = _load("stage3", "v4 selection stage 3.py")
fc12 = _load("fc12", "v4 item 12 field check.py")

FILE_YEAR = 2018                      # MERGED2018_19: the latest file ending by scoring year 2019
EARLIEST_EARNINGS = 2009              # earnings fallback searched back to the 2009-10 file
MISSING = {"", "NULL", "PRIVACYSUPPRESSED", "PS", "NA"}


def num(v):
    v = (v or "").strip()
    if v.upper() in MISSING:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def scorecard() -> tuple[dict, str]:
    zpath, url = fc12.download_asset()
    vals = {}
    with zipfile.ZipFile(zpath) as zf:
        files = {}
        for n in zf.namelist():
            m = fc12.bsc.NAME_RE.search(n)
            if m and not (n.startswith("__MACOSX") or "/._" in n or n.startswith("._")):
                files[int(m.group(1))] = n
        for year in sorted((y for y in files if EARLIEST_EARNINGS <= y <= FILE_YEAR), reverse=True):
            with zf.open(files[year]) as raw:
                for r in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")):
                    r = {k.strip().lstrip("﻿").upper(): v for k, v in r.items() if k}
                    u = r.get("UNITID", "").strip()
                    v = vals.setdefault(u, {})
                    if year == FILE_YEAR:
                        mp, pf = num(r.get("BBRR2_FED_UG_MAKEPROG")), num(r.get("BBRR2_FED_UG_PAIDINFULL"))
                        v["OPEID6"] = r.get("OPEID6", "").strip()
                        v["D_value"] = (1 - (mp + pf)) if mp is not None and pf is not None else None
                        v["CDR3"] = num(r.get("CDR3"))
                    if v.get("earnings") is None:
                        e = num(r.get("MD_EARN_WNE_P10"))
                        if e is not None:
                            v["earnings"], v["earnings file year"] = e, year
            print(files[year], "read", flush=True)
    zpath.unlink()
    return vals, url


def weighted_compare(rows, feat) -> dict:
    y = np.array([r["closed"] for r in rows], int)
    groups = np.array([r["OPEID6"] or r["unitid"] for r in rows])
    k = Counter(groups)
    w = np.array([1.0 / k[g] for g in groups])
    if y.sum() < st.FOLDS:
        return {"N": len(y), "closures": int(y.sum()), "verdict": "too few closures for 10-fold cross-validation"}

    def oof(X):
        p = np.zeros(len(y))
        cv = StratifiedGroupKFold(st.FOLDS, shuffle=True, random_state=st.CV_SEED)
        for tr, te in cv.split(X, y, groups):
            mu, sd = X[tr].mean(0), X[tr].std(0)
            sd[sd == 0] = 1
            m = LogisticRegression(C=1e6, max_iter=5000).fit((X[tr] - mu) / sd, y[tr], sample_weight=w[tr])
            p[te] = m.predict_proba((X[te] - mu) / sd)[:, 1]
        return p

    pa, pb = oof(st.design(rows, [])), oof(st.design(rows, [feat]))
    aa, ab = roc_auc_score(y, pa, sample_weight=w), roc_auc_score(y, pb, sample_weight=w)
    ug = sorted(set(groups))
    idx = {g: np.where(groups == g)[0] for g in ug}
    rng = np.random.default_rng(st.BOOT_SEED)
    diffs = []
    for _ in range(st.BOOT_N):
        i = np.concatenate([idx[g] for g in rng.choice(ug, len(ug))])
        if 0 < y[i].sum() < len(i):
            diffs.append(roc_auc_score(y[i], pb[i], sample_weight=w[i]) - roc_auc_score(y[i], pa[i], sample_weight=w[i]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"N campuses": len(y), "OPEID6 identifiers": len(ug), "closures (campuses)": int(y.sum()),
            "closures (weighted)": float((w * y).sum()), "AUC, size and sector": float(aa),
            "AUC, size, sector and D_value": float(ab), "gain": float(ab - aa), "gain 95% bootstrap": [float(lo), float(hi)],
            "bootstrap resamples used": len(diffs),
            "verdict": ("gain, interval above 0" if lo > 0 else "positive, interval includes 0" if ab > aa else "no gain")}


def main() -> None:
    rows = s3.load_2019()
    out, files, nf = s3.outcomes_2019([r["unitid"] for r in rows])
    for r in rows:
        r["closed"] = bool(out[r["unitid"]]["closed or failed (primary)"])
    base = [r for r in rows if r["log FTE"] is not None]
    vals, url = scorecard()
    for r in base:
        v = vals.get(r["unitid"], {})
        r["OPEID6"], r["D_value"], r["CDR3"] = v.get("OPEID6", ""), v.get("D_value"), v.get("CDR3")
        r["earnings"], r["earnings file year"] = v.get("earnings"), v.get("earnings file year")
    med = {c: float(np.median([r["earnings"] for r in base if r["control"] == c and r["earnings"] is not None]))
           for c in ("public", "private nonprofit", "for-profit")
           if any(r["earnings"] is not None for r in base if r["control"] == c)}
    for r in base:
        r["D_earn"] = (1 - min(1.0, r["earnings"] / med[r["control"]])) if r["earnings"] is not None and r["control"] in med else None

    cov = [r for r in base if r["D_value"] is not None]
    primary = weighted_compare(cov, "D_value")
    check = st.compare(cov, [], ["D_value"], "size and sector", "size, sector and D_value")
    secondary = {}
    for feat in ("CDR3", "D_earn"):
        c = [r for r in base if r[feat] is not None]
        secondary[feat] = st.compare(c, [], [feat], "size and sector", f"size, sector and {feat}") | {
            "coverage": st.describe(c, [r for r in base if r[feat] is None])}
    lo = primary.get("gain 95% bootstrap", [0])[0]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "protocol": "channel selection protocol.md, Amendments 8, 10 and 11: value dimension, 2019 frame",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "label": "single held-out comparison with no development stage (repayment columns begin with the 2018-19 file)",
        "scorecard": {"downloaded from": url, "sha256": fc12.bsc.EXPECTED_SHA256, "primary file year": FILE_YEAR},
        "header files": files, "header files not yet released": nf,
        "institutions with size": len(base), "closures": sum(r["closed"] for r in base),
        "coverage of D_value": st.describe(cov, [r for r in base if r["D_value"] is None]),
        "primary (OPEID6 counted once)": primary, "check (campus level, unweighted)": check,
        "verdict": ("enters v4: gain interval above zero" if lo > 0 else "does not enter v4"),
        "secondary readings (reported only)": secondary,
        "earnings medians by control (D_earn reference)": med,
        "note": "Selection-stage performance, used only to choose; never an estimate of v4's accuracy."},
        indent=1) + "\n", encoding="utf-8")
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["unitid", "control", "OPEID6", "D_value", "CDR3", "earnings", "earnings file year", "D_earn"])
        for r in base:
            wr.writerow([r["unitid"], r["control"], r["OPEID6"], r["D_value"], r["CDR3"], r["earnings"],
                         r["earnings file year"], r["D_earn"]])
    print(json.dumps({"primary": primary, "verdict": "enters" if lo > 0 else "does not enter"}, indent=1))


if __name__ == "__main__":
    main()
