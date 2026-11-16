"""
Exploratory: the v3 anchor sensor and test results cross-referenced with
the point-of-no-return mathematics of the RICD Spine (§10.3a, Definitions
10.3a.7-10.3a.9, Propositions 10.3a.7 and 10.3a.9).

The v3 test outcomes are already known, so nothing here is a test and no
v3 verdict changes. The analyses below are fixed in this file so that the
same code can be run blind on the prospective retest, with its scores
committed before its outcomes exist.

What the Spine predicts, and how each prediction is read from what the
collapse-causal tracker (C-CT) already records for each scored institution:

A. Break-even is the tipping point. Coverage c = total work / exchange
   base (the tracker's coverage_final) at or above 1 means a container is
   past break-even. Prediction: closure is more frequent past break-even.
B. Anchors move the point of no return, not the tipping point. Anchor
   capacity per unit of work, A/W, is read as the share of expenses that
   one-directional external inflows cover, f_approp + f_gift (from
   data/v3/anchors.json, capped at 1 each), and system membership S_par.
   Prediction: past break-even, anchored institutions close less often
   than unanchored ones; below break-even, where no deficit is being
   carried, the anchor difference is smaller. The difference between the
   two differences is reported.
C. The recovery window narrows with velocity. Prediction: past break-even,
   institutions still sliding (slide rate g > 0) close more often than
   those whose slide has stopped or reversed (g <= 0).
D. Distance to the point of no return, Delta_PNR = R_avail + A - deltaR.
   The tracker does not hold the three terms in common units (reserve
   adequacy is log endowment per student, resource debt is in the model's
   own scale, anchor capacity is a share of expenses), so here each is
   standardized across the scored institutions and the distance is read
   only as a ranking: Delta = z(reserve_adequacy) + z(A/W) - z(delta_R_final).
   Prediction: a smaller distance ranks closures higher (area under the
   ROC curve of -Delta above 0.5), most of all past break-even. Putting
   the terms in common units (dollars, or years of expenses) is a task
   for the retest pipeline.

Every analysis is reported for all scored institutions and for public and
private nonprofit institutions alone, with 95% bootstrap intervals
(institutions resampled; seed fixed below).

Usage:
    cd src
    python "anchor cross reference.py"
"""

from __future__ import annotations

import datetime
import json
import math
import statistics
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
V3 = ROOT / "data" / "v3"
OUT = ROOT / "data" / "v3 exploratory" / "anchor cross reference.json"
SEED = 20261115
BOOT = 2000


def load() -> list[dict]:
    outcomes = {r["unitid"]: r for r in json.loads((V3 / "test outcomes.json").read_text())["institutions"]}
    anchors = json.loads((V3 / "anchors.json").read_text())["cohorts"]["2019"]["records"]
    rows = []
    for p in sorted((V3 / "test scores").glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            if r["status"] != "scored":
                continue
            a = anchors.get(r["unitid"]) or {}
            has = a.get("W") is not None
            share = (min(a.get("f_approp") or 0.0, 1.0) + min(a.get("f_gift") or 0.0, 1.0)) if has else 0.0
            rows.append({"unitid": r["unitid"], "sector": r["sector"],
                         "closed": bool(outcomes[r["unitid"]]["closed or failed (primary)"]),
                         "coverage": r["drift features"]["coverage_final"],
                         "slide": r["drift features"]["slide_rate"],
                         "anchor share": share, "system member": bool(has and a.get("S_par")),
                         "reserve": r["features (seed 7)"]["reserve_adequacy"],
                         "debt": r["features (seed 7)"]["delta_R_final"]})
    return rows


def rate(rs: list[dict]) -> float | None:
    return sum(r["closed"] for r in rs) / len(rs) if rs else None


def auc(score: list[float], closed: list[bool]) -> float | None:
    pos = [s for s, c in zip(score, closed) if c]
    neg = [s for s, c in zip(score, closed) if not c]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def group(rs: list[dict]) -> dict:
    return {"institutions": len(rs), "closed": sum(r["closed"] for r in rs),
            "closure rate": None if not rs else round(rate(rs), 4)}


def analyses(rows: list[dict]) -> dict:
    past = [r for r in rows if r["coverage"] >= 1]
    below = [r for r in rows if r["coverage"] < 1]
    med = statistics.median(r["anchor share"] for r in rows)
    anchored = lambda r: r["anchor share"] > med or r["system member"]

    def a_stat(rs):
        p, b = rate(rs[0]), rate(rs[1])
        return None if p is None or b is None or b == 0 else p / b

    def b_stat(past, below):
        pa, pu = [r for r in past if anchored(r)], [r for r in past if not anchored(r)]
        ba, bu = [r for r in below if anchored(r)], [r for r in below if not anchored(r)]
        if not (pa and pu and ba and bu):
            return None
        return (rate(pu) - rate(pa)) - (rate(bu) - rate(ba))

    def c_stat(past):
        s, n = [r for r in past if r["slide"] > 0], [r for r in past if r["slide"] <= 0]
        return None if not s or not n else rate(s) - rate(n)

    def z(vals):
        m, s = statistics.fmean(vals), statistics.pstdev(vals) or 1.0
        return [(v - m) / s for v in vals]

    zr, za, zd = z([r["reserve"] for r in rows]), z([r["anchor share"] for r in rows]), z([r["debt"] for r in rows])
    for r, a, b, c in zip(rows, zr, za, zd):
        r["distance"] = a + b - c

    def d_stat(rs):
        return auc([-r["distance"] for r in rs], [r["closed"] for r in rs])

    rng = np.random.default_rng(SEED)
    idx = np.arange(len(rows))
    boots = {"A": [], "B": [], "C": [], "D all": [], "D past": []}
    for _ in range(BOOT):
        s = [rows[i] for i in rng.choice(idx, len(idx))]
        sp, sb = [r for r in s if r["coverage"] >= 1], [r for r in s if r["coverage"] < 1]
        for k, v in (("A", a_stat((sp, sb))), ("B", b_stat(sp, sb)), ("C", c_stat(sp)),
                     ("D all", d_stat(s)), ("D past", d_stat(sp))):
            if v is not None and math.isfinite(v):
                boots[k].append(v)
    ci = lambda k: [round(float(np.percentile(boots[k], 2.5)), 4), round(float(np.percentile(boots[k], 97.5)), 4)] \
        if len(boots[k]) > BOOT // 2 else None
    rnd = lambda v: None if v is None else round(v, 4)
    return {
        "A. break-even is the tipping point": {
            "past break-even (coverage >= 1)": group(past), "below break-even": group(below),
            "closure-rate ratio, past over below": rnd(a_stat((past, below))), "95% interval": ci("A")},
        "B. anchors move the point of no return": {
            "anchored means": f"anchor share above the median ({round(med, 4)}) or a system member",
            "past break-even, anchored": group([r for r in past if anchored(r)]),
            "past break-even, unanchored": group([r for r in past if not anchored(r)]),
            "below break-even, anchored": group([r for r in below if anchored(r)]),
            "below break-even, unanchored": group([r for r in below if not anchored(r)]),
            "difference in differences (unanchored minus anchored closure rate, past minus below)":
                rnd(b_stat(past, below)), "95% interval": ci("B")},
        "C. the recovery window narrows with velocity": {
            "past break-even, still sliding (g > 0)": group([r for r in past if r["slide"] > 0]),
            "past break-even, slide stopped or reversed (g <= 0)": group([r for r in past if r["slide"] <= 0]),
            "closure-rate difference, sliding minus not": rnd(c_stat(past)), "95% interval": ci("C")},
        "D. distance to the point of no return (ranking only)": {
            "area under the ROC curve, all scored": rnd(d_stat(rows)), "95% interval, all": ci("D all"),
            "area under the ROC curve, past break-even": rnd(d_stat(past)), "95% interval, past": ci("D past")},
    }


def main() -> None:
    rows = load()
    nonprofit = [dict(r) for r in rows if r["sector"] != "forprofit"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": ("Exploratory: the v3 test outcomes were already known. The analyses are fixed in "
                 "src/anchor cross reference.py so that they can be run blind on the prospective retest."),
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inputs": ["data/v3/test scores/", "data/v3/test outcomes.json", "data/v3/anchors.json"],
        "bootstrap": {"resamples": BOOT, "seed": SEED},
        "all scored institutions": analyses([dict(r) for r in rows]),
        "public and private nonprofit institutions": analyses(nonprofit),
    }, indent=2))
    print(OUT.read_text())


if __name__ == "__main__":
    main()
