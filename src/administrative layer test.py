"""
Exploratory test of the hypothesis that the thinner a college's
administrative layer, the healthier it is (the less resource debt it
carries), on the 670 development institutions only (the v2 training draw,
scored for 2014, and the v2 test draw, scored for 2019), whose outcomes
are already known and already used to fit the classifiers. The v3 test
institutions are not used, so the prospective retest can test the same
hypothesis blind.

Inputs: the administrative shares of "administrative layer.py"
(data/meta channel/administrative layer.json); the two-channel resource
debt of each development institution (data/v3 reanalysis/rescored/); and
the development outcomes (data/v2/training outcomes.json and
data/v2/test outcomes.json). The share is taken from the fall before the
scoring year (fiscal year = scoring year), or the latest earlier fall from
2012 on.

Predictions, fixed here:
  1. A thicker layer goes with more resource debt: Spearman correlation
     between the core administrative share and delta_R_final (and
     delta_R_trend) above zero, overall and within each sector.
  2. A thicker layer goes with closure: closure rate rises across thirds
     of the core share, and the core share ranks closures above
     non-closures (area under the ROC curve above 0.5), overall and among
     public and private nonprofit institutions alone.
  3. A thicker layer goes with weaker operations in the ways that drive
     official-operational divergence: lower adaptive capacity (Spearman
     with d_A_final below zero), a higher research-to-instruction ratio
     (spending on form over function; above zero), and a lower full-time
     share of instructional staff (more adjunct teaching; below zero,
     from "instructional staff share.json", same fall as the share).
The official-operational divergence D_op itself is not stored per
institution by the scoring runs, so it cannot be tested here; the retest
pipeline records it. The same is reported for the broad share. 95% bootstrap intervals
(institutions resampled, seed fixed below).

Usage:
    cd src
    python "administrative layer test.py"
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "meta channel" / "administrative layer test.json"
SEED = 20261116
BOOT = 2000

_spec = importlib.util.spec_from_file_location("administrative_layer",
                                               Path(__file__).resolve().parent / "administrative layer.py")
al = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(al)


def outcomes() -> dict:
    out = {}
    for year, f in ((2014, "training outcomes.json"), (2019, "test outcomes.json")):
        for r in json.loads((ROOT / "data" / "v2" / f).read_text())["institutions"]:
            out[f"{year}:{r['unitid']}"] = bool(r["closed or failed (primary)"])
    return out


def share_at(layer: dict, unitid: str, scoring_year: int, cats: tuple) -> float | None:
    for fall in range(scoring_year - 1, 2011, -1):
        rec = layer["by fall year"].get(str(fall), {}).get(unitid)
        s = al.shares(rec, cats, True) if rec else None
        if s is not None:
            return s
    return None


def load() -> list[dict]:
    layer = json.loads((ROOT / "data" / "meta channel" / "administrative layer.json").read_text())
    ft = json.loads((ROOT / "data" / "meta channel" / "instructional staff share.json").read_text())["by fall year"]

    def ft_share(unitid, scoring_year):
        for fall in range(scoring_year - 1, 2011, -1):
            v = ft.get(str(fall), {}).get(unitid)
            if v and sum(v) > 0:
                return v[0] / sum(v)
        return None
    out_ = outcomes()
    rows = []
    for p in sorted((ROOT / "data" / "v3 reanalysis" / "rescored").glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            if r["key"].startswith("v3test:") or r["status"] != "scored" or r["key"] not in out_:
                continue
            core = share_at(layer, r["unitid"], r["scoring year"], al.CORE)
            broad = share_at(layer, r["unitid"], r["scoring year"], al.BROAD)
            rows.append({"key": r["key"], "sector": r["sector"], "closed": out_[r["key"]],
                         "core": core, "broad": broad,
                         "debt": r["features"]["delta_R_final"], "debt trend": r["features"]["delta_R_trend"],
                         "adaptive capacity": r["features"]["d_A_final"],
                         "research ratio": r["features"]["research_ratio"],
                         "full-time share": ft_share(r["unitid"], r["scoring year"])})
    return rows


def ranks(x: np.ndarray) -> np.ndarray:
    from scipy.stats import rankdata
    return rankdata(x)          # average ranks for ties


def spearman(a, b) -> float | None:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 5 or a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(ranks(a), ranks(b))[0, 1])


def auc(score, closed) -> float | None:
    s, c = np.asarray(score, float), np.asarray(closed, bool)
    if c.all() or not c.any():
        return None
    r = ranks(s)
    n1, n0 = c.sum(), (~c).sum()
    return float((r[c].sum() - n1 * (n1 - 1) / 2) / (n1 * n0))


def boot(rows, stat):
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(BOOT):
        s = [rows[i] for i in rng.integers(0, len(rows), len(rows))]
        v = stat(s)
        if v is not None:
            vals.append(v)
    if len(vals) < BOOT // 2:
        return None
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)]


def block(rows: list[dict], measure: str) -> dict:
    rs = [r for r in rows if r[measure] is not None]
    if len(rs) < 20:
        return {"institutions with a value": len(rs)}
    rho = lambda s, k: spearman([r[measure] for r in s], [r[k] for r in s])
    au = lambda s: auc([r[measure] for r in s], [r["closed"] for r in s])
    ftr = [r for r in rs if r["full-time share"] is not None]
    ft_rho = None if len(ftr) < 20 else round(rho(ftr, "full-time share"), 4)
    cuts = np.quantile([r[measure] for r in rs], [1 / 3, 2 / 3])
    thirds = {}
    for name, lo, hi in (("thinnest third", -1, cuts[0]), ("middle third", cuts[0], cuts[1]), ("thickest third", cuts[1], 2)):
        g = [r for r in rs if lo < r[measure] <= hi]
        thirds[name] = {"institutions": len(g), "closed": sum(r["closed"] for r in g),
                        "closure rate": round(sum(r["closed"] for r in g) / len(g), 4) if g else None}
    by_sector = {}
    for sec in sorted({r["sector"] for r in rs}):
        g = [r for r in rs if r["sector"] == sec]
        v = rho(g, "debt")
        by_sector[sec] = {"institutions": len(g), "Spearman with resource debt": None if v is None else round(v, 4),
                          "95% interval": boot(g, lambda s: rho(s, "debt"))}
    return {"institutions with a value": len(rs), "closed": sum(r["closed"] for r in rs),
            "share thirds cut at": [round(float(c), 4) for c in cuts],
            "1. Spearman with resource debt (delta_R_final)": round(rho(rs, "debt"), 4),
            "95% interval (debt)": boot(rs, lambda s: rho(s, "debt")),
            "1. Spearman with resource-debt trend (delta_R_trend)": round(rho(rs, "debt trend"), 4),
            "95% interval (debt trend)": boot(rs, lambda s: rho(s, "debt trend")),
            "1. within each sector": by_sector,
            "2. closure by thirds of the share": thirds,
            "3. Spearman with adaptive capacity (d_A_final; predicted below 0)": round(rho(rs, "adaptive capacity"), 4),
            "95% interval (adaptive capacity)": boot(rs, lambda s: rho(s, "adaptive capacity")),
            "3. Spearman with research-to-instruction ratio (predicted above 0)": round(rho(rs, "research ratio"), 4),
            "95% interval (research ratio)": boot(rs, lambda s: rho(s, "research ratio")),
            "3. Spearman with full-time instructional share (predicted below 0)": ft_rho,
            "95% interval (full-time share)": boot(ftr, lambda s: rho(s, "full-time share")) if ftr else None,
            "2. area under the ROC curve (closure)": None if au(rs) is None else round(au(rs), 4),
            "95% interval (area)": boot(rs, au)}


def main() -> None:
    rows = load()
    nonprofit = [r for r in rows if r["sector"] != "forprofit"]
    res = {"note": ("Exploratory: development institutions only, outcomes already known. "
                    "The v3 test institutions are held back for the prospective retest."),
           "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "development institutions scored": len(rows),
           "bootstrap": {"resamples": BOOT, "seed": SEED}}
    for m in ("core", "broad"):
        res[f"{m} administrative share, all"] = block(rows, m)
        res[f"{m} administrative share, public and private nonprofit"] = block(nonprofit, m)
    OUT.write_text(json.dumps(res, indent=2))
    print(OUT.read_text())


if __name__ == "__main__":
    main()
