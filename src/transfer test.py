"""
Transfer test, step 2b: the analysis fixed in "transfer test protocol.md"
(with Amendments 1 and 2), run on the parsed Texas reports.

Prediction: within the same receiving Texas public university, students
transferring from community colleges with a higher contingent share of
instructional staff more often have a first-year GPA below 2.0, more often
are not enrolled the following fall, and less often graduate.

Inputs: data/transfer test/reports.json and inputs.json (from
"transfer data.py"); data/meta channel/instructional staff share.json.
Output: data/transfer test/results.json

Usage:
    cd src
    python "transfer test.py"          [--root DIR for testing]
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

SEED = 20261116
BOOT = 2000
MIN_STAFF = 25
SKIP = {"OTHER PUBLIC 4YR INSTITUTION", "INSTITUTION TOTAL"}

# Amendment 2: multi-college districts. The Coordinating Board publishes a report for a district and for
# each of its colleges, and the district report covers the same students as its colleges' reports, so the
# two are never used together. Which one is used follows how IPEDS reports the district's staff: where
# IPEDS reports each college separately, the colleges' reports are used; where it reports one unit for the
# whole district, the district's report is used, with that unit's staff. Fixed from the IPEDS structure
# alone, before the corrected reports were parsed.
ALAMO = {"000309", "000307", "023413", "009163", "003608"}
DALLAS = {"021002", "003561", "008510", "004453", "008503", "020774", "008504"}
LONE_STAR = {"000823", "000717", "000819", "000719", "000721", "000722", "000720", "000821"}
SAN_JACINTO = {"003609", "012713", "000090"}
TARRANT = {"008897", "008899", "010964", "008900", "000326", "008901"}
TSTC = {"009642", "119642", "203634", "009225", "033965", "133965", "003634", "009932"}


def district_rule(fice: str, cohort: int):
    """(use this report?, the FICE whose IPEDS units stand for it if not its own, or None)."""
    if fice in ("003607", "103574"):            # Alamo and Howard County districts: colleges reported separately
        return False, None
    if fice in LONE_STAR or fice in TARRANT or fice in SAN_JACINTO:
        return False, None                      # one IPEDS unit for the district: the district report is used
    if fice == "029137":                        # San Jacinto district: IPEDS unit filed under the Central campus
        return True, "003609"
    if fice == "009331" or fice in DALLAS:      # Dallas: one IPEDS unit (filed under El Centro) from fall 2020
        if cohort <= 2020:
            return fice != "009331", None
        if cohort == 2021:
            return False, None                  # falls 2019 and 2020 straddle the change
        return fice == "009331", "004453"
    if fice in TSTC:                            # Texas State Technical College: one IPEDS unit from fall 2015
        return cohort <= 2015, None
    return True, None


def college_year(inputs, staff, fice, cohort, units_of=None):
    """Contingent share (mean of falls cohort-2 and cohort-1) and Pell share for one college and cohort.
    units_of: the FICE whose IPEDS units stand for this report (Amendment 2), if not its own."""
    xw = inputs["crosswalk (fall year -> FICE -> IPEDS unit IDs)"]
    pell = inputs["Pell share (PCTPELL)"]["by unit id"]
    shares, pells = [], []
    for fall in (cohort - 2, cohort - 1):
        ids = (xw.get(str(fall)) or {}).get(units_of or fice, [])
        recs = [staff.get(str(fall), {}).get(u) for u in ids]
        recs = [r for r in recs if r]
        ft, pt = sum(r[0] for r in recs), sum(r[1] for r in recs)
        if ft + pt < MIN_STAFF:
            return None, None, "fewer than 25 instructional staff, or not found, in a fall before transfer"
        shares.append(pt / (ft + pt))
        pells += [pell[u][str(fall)] for u in ids if u in pell and str(fall) in pell[u]]
    return float(np.mean(shares)), (float(np.mean(pells)) if pells else None), None


def build(root: Path):
    t = root / "data" / "transfer test"
    reports = json.loads((t / "reports.json").read_text())
    inputs = json.loads((t / "inputs.json").read_text())
    staff = json.loads((root / "data" / "meta channel" / "instructional staff share.json").read_text())["by fall year"]
    cache, excluded, set_aside = {}, {}, {}

    def cy(fice, cohort):
        if (fice, cohort) not in cache:
            use, units_of = district_rule(fice, cohort)
            if not use:
                cache[(fice, cohort)] = (None, None)
                set_aside[f"{fice} {cohort}"] = "district rule (Amendment 2): covered by another report"
            else:
                x, p, why = college_year(inputs, staff, fice, cohort, units_of)
                cache[(fice, cohort)] = (x, p)
                if why:
                    excluded[f"{fice} {cohort}"] = why
        return cache[(fice, cohort)]

    pairs = {"first-year GPA below 2.0": [], "not enrolled the following fall": [], "not graduated": []}
    level2 = []
    for rep in reports["performance"]:
        if "error" in rep:
            continue
        x, p = cy(rep["fice"], rep["cohort (fall)"])
        if x is None:
            continue
        for r in rep["rows"]:
            if r["university"] in SKIP or "problems" in r:
                continue
            d, nd = r["dev ed"], r["no dev ed"]
            known = d["n"] - d["unknown"] + nd["n"] - nd["unknown"]
            base = {"fice": rep["fice"], "group": f"{r['university']}|{rep['cohort (fall)']}", "x": x, "pell": p}
            if known > 0:
                pairs["first-year GPA below 2.0"].append({**base, "w": known, "y": (d["gpa"][0] + nd["gpa"][0]) / known})
            if r["transfers"] > 0:
                pairs["not enrolled the following fall"].append(
                    {**base, "w": r["transfers"],
                     "y": 1 - (d["enrolled next fall"] + nd["enrolled next fall"]) / r["transfers"]})
    for rep in reports["graduation"]:
        if "error" in rep:
            continue
        x, p = cy(rep["fice"], rep["cohort (fall)"])
        if x is None:
            continue
        for r in rep["rows"]:
            if r["university"] in SKIP or "problems" in r or r["transfers"] == 0:
                continue
            pairs["not graduated"].append({"fice": rep["fice"], "group": f"{r['university']}|{rep['cohort (fall)']}",
                                           "x": x, "pell": p, "w": r["transfers"],
                                           "y": 1 - r["graduated"] / r["transfers"]})
        tot = rep["total"]
        if tot["transfers"] > 0:
            level2.append({"fice": rep["fice"], "x": x, "pell": p, "rate": tot["graduated"] / tot["transfers"]})
    # Check (disclosed, not used): each district report's total against the sum of its colleges' totals.
    groups = {"003607": ALAMO, "009331": DALLAS, "011145": LONE_STAR, "029137": SAN_JACINTO,
              "003626": TARRANT, "103574": {"003574", "000574"}}
    totals = {(r["fice"], r["cohort (fall)"]): r["total"]["transfers"]
              for r in reports["performance"] if "error" not in r}
    check = {}
    for d, members in groups.items():
        for c in sorted({k[1] for k in totals if k[0] == d}):
            check[f"{d} {c}"] = {"district": totals[(d, c)],
                                 "sum of colleges": sum(v for (f, y), v in totals.items() if f in members and y == c)}
    return pairs, level2, excluded, reports, set_aside, check


def slope(rows, with_pell):
    rows = [r for r in rows if (r["pell"] is not None or not with_pell)]
    if len(rows) < 20:
        return None
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault(r["group"], []).append(i)
    w = np.array([r["w"] for r in rows], float)
    cols = {"y": np.array([r["y"] for r in rows]), "x": np.array([r["x"] for r in rows])}
    if with_pell:
        cols["pell"] = np.array([r["pell"] for r in rows])
    cen = {k: v.copy() for k, v in cols.items()}
    for idx in groups.values():
        ww = w[idx]
        for k, v in cols.items():
            cen[k][idx] = v[idx] - np.average(v[idx], weights=ww)
    X = np.column_stack([cen["x"]] + ([cen["pell"]] if with_pell else []))
    sw = np.sqrt(w)
    if np.linalg.matrix_rank(X * sw[:, None]) < X.shape[1]:
        return None
    beta = np.linalg.lstsq(X * sw[:, None], cen["y"] * sw, rcond=None)[0]
    return float(beta[0]), (float(beta[1]) if with_pell else None)


def cluster_boot(rows, stat):
    by = {}
    for r in rows:
        by.setdefault(r["fice"], []).append(r)
    keys = sorted(by)
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(BOOT):
        pick = rng.integers(0, len(keys), len(keys))
        sample = []
        for k in pick:                   # a college drawn twice contributes all its pairs twice
            sample += by[keys[k]]
        v = stat(sample)
        if v is not None and math.isfinite(v):
            vals.append(v)
    if len(vals) < BOOT // 2:
        return None
    return [round(float(np.percentile(vals, 2.5)), 5), round(float(np.percentile(vals, 97.5)), 5)]


def verdict(ci, sign):
    if ci is None:
        return "not computed"
    if (sign > 0 and ci[0] > 0) or (sign < 0 and ci[1] < 0):
        return "supported"
    if (sign > 0 and ci[1] < 0) or (sign < 0 and ci[0] > 0):
        return "contradicted"
    return "not decided"


def partial_spearman(rows, x, y, ctrl):
    rows = [r for r in rows if all(r[k] is not None for k in [x, y] + ctrl)]
    if len(rows) < 20:
        return None
    R = lambda k: rankdata([r[k] for r in rows])
    C = np.column_stack([np.ones(len(rows))] + [R(k) for k in ctrl])
    res = lambda v: v - C @ np.linalg.lstsq(C, v, rcond=None)[0]
    a, b = res(R(x)), res(R(y))
    return None if a.std() == 0 or b.std() == 0 else float(np.corrcoef(a, b)[0, 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    root = Path(ap.parse_args().root)
    pairs, level2, excluded, reports, set_aside, check = build(root)
    out = {"protocol": "transfer test protocol.md with Amendments 1 and 2 (pre-registered analysis of existing data; exploratory)",
           "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "bootstrap": {"resamples": BOOT, "seed": SEED, "resampled unit": "community college (cluster)"},
           "reports parsed": reports["parsed"] | {"failed": len(reports["parsed"]["failed"]),
                                                  "download errors": len(reports["parsed"]["download errors"])},
           "college-cohorts excluded": excluded,
           "college-cohorts set aside by the district rule": set_aside,
           "check: district totals against their colleges' totals (performance reports)": check,
           "level 1, pairs (primary)": {}, "level 2, sending colleges": {}}
    for outcome, rows in pairs.items():
        main_ = slope(rows, True)
        ci = cluster_boot(rows, lambda s: (slope(s, True) or (None,))[0])
        no_pell = slope(rows, False)
        ci_np = cluster_boot(rows, lambda s: (slope(s, False) or (None,))[0])
        col_pell = {}
        for r in rows:
            if r["pell"] is not None:
                col_pell.setdefault(r["fice"], []).append(r["pell"])
        means = {k: float(np.mean(v)) for k, v in col_pell.items()}
        cuts = np.quantile(list(means.values()), [1 / 3, 2 / 3]) if means else None
        thirds = {}
        if cuts is not None:
            for name, lo, hi in (("lowest Pell third", -1, cuts[0]), ("middle Pell third", cuts[0], cuts[1]),
                                 ("highest Pell third", cuts[1], 2)):
                g = [r for r in rows if r["fice"] in means and lo < means[r["fice"]] <= hi]
                s = slope(g, False)
                thirds[name] = {"pairs": len(g), "colleges": len({r["fice"] for r in g}),
                                "slope": None if s is None else round(s[0], 5),
                                "95% interval": cluster_boot(g, lambda q: (slope(q, False) or (None,))[0])}
        out["level 1, pairs (primary)"][outcome] = {
            "pairs": len(rows), "colleges": len({r["fice"] for r in rows}),
            "transfers (weight)": int(sum(r["w"] for r in rows)),
            "slope on contingent share, Pell held constant": None if main_ is None else round(main_[0], 5),
            "95% interval": ci, "verdict (predicted above zero)": verdict(ci, +1),
            "Pell share's own slope (no direction predicted)": None if main_ is None else round(main_[1], 5),
            "check: slope without Pell": None if no_pell is None else round(no_pell[0], 5),
            "check: 95% interval without Pell": ci_np,
            "check: within thirds of colleges by Pell share": thirds}
    for ctrl, label in (([], "Spearman"), (["pell"], "partial Spearman, Pell held constant")):
        v = partial_spearman(level2, "x", "rate", ctrl)
        ci = cluster_boot(level2, lambda s, ctrl=ctrl: partial_spearman(s, "x", "rate", ctrl))
        out["level 2, sending colleges"][label] = {
            "college-cohorts": len([r for r in level2 if all(r[k] is not None for k in ["x", "rate"] + ctrl)]),
            "colleges": len({r["fice"] for r in level2}),
            "correlation of transfers' graduation rate with contingent share": None if v is None else round(v, 4),
            "95% interval": ci, "verdict (predicted below zero)": verdict(ci, -1)}
    out["level 3, receiving universities"] = ("Deferred under Amendment 1: needs the annual Transfer Report's "
                                              "junior-cohort tables; reported separately when built.")
    (root / "data" / "transfer test" / "results.json").write_text(json.dumps(out, indent=2))
    print("Wrote results.json")


if __name__ == "__main__":
    main()
