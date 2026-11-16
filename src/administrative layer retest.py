"""
Administrative layer retest (see "administrative layer retest protocol.md"):
the administrative-layer hypothesis, with the corrections found on
November 16 (equal size and wealth, sectors separately, the share read
jointly with the debt trend), on the 987 scored v3 test colleges, which the
first test held back. Pre-registered analysis of existing outcomes,
exploratory; changes no v3 verdict.

Inputs (all committed): data/meta channel/administrative layer.json and
instructional staff share.json; data/v3 reanalysis/test scores/ (two-channel
features, seed 7); data/v3/anchors.json (appropriations share, 2019 cohort);
data/v3/test outcomes.json.

Output: data/meta channel/administrative layer retest.json

Usage:
    cd src
    python "administrative layer retest.py"
    (--root DIR runs it on another copy of the data folders, for testing)
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

SEED = 20261116
BOOT = 2000
FALL = 2018          # fall before the 2019 scoring year
MIN_CLOSURES = 10

_spec = importlib.util.spec_from_file_location("administrative_layer",
                                               Path(__file__).resolve().parent / "administrative layer.py")
al = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(al)


def load(root: Path) -> list[dict]:
    layer = json.loads((root / "data" / "meta channel" / "administrative layer.json").read_text())
    resolved = al.resolved_by_fall(layer)
    staff = json.loads((root / "data" / "meta channel" / "instructional staff share.json").read_text())["by fall year"]
    anchors = json.loads((root / "data" / "v3" / "anchors.json").read_text())["cohorts"]["2019"]["records"]
    outcomes = {r["unitid"]: bool(r["closed or failed (primary)"])
                for r in json.loads((root / "data" / "v3" / "test outcomes.json").read_text())["institutions"]}

    def share(u, cats):
        for fall in range(FALL, 2011, -1):
            rec = layer["by fall year"].get(str(fall), {}).get(u)
            s = al.shares(rec, cats, True, resolved.get(str(fall), set())) if rec else None
            if s is not None:
                return s, fall
        return None, None

    rows = []
    for p in sorted((root / "data" / "v3 reanalysis" / "test scores").glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            if r["status"] != "scored" or r["unitid"] not in outcomes:
                continue
            u, f = r["unitid"], r["features (seed 7)"]
            core, fall = share(u, al.CORE)
            broad, _ = share(u, al.BROAD)
            st = staff.get(str(fall), {}).get(u) if fall else None
            rows.append({"unitid": u, "sector": r["sector"], "closed": float(outcomes[u]),
                         "core": core, "broad": broad,
                         "debt": f["delta_R_final"], "debt trend": f["delta_R_trend"],
                         "adaptive capacity": f["d_A_final"], "wealth": f["reserve_adequacy"],
                         "size": math.log(sum(st)) if st and sum(st) > 0 else None,
                         "full-time share": st[0] / sum(st) if st and sum(st) > 0 else None,
                         "appropriations": (anchors.get(u) or {}).get("f_approp"),
                         "public": float(r["sector"] == "public"), "forprofit": float(r["sector"] == "forprofit")})
    return rows


def partial(rs, x, y, ctrl):
    rs = [r for r in rs if all(r[k] is not None for k in [x, y] + ctrl)]
    if len(rs) < 20:
        return None, len(rs)
    R = lambda k: rankdata([r[k] for r in rs])
    C = np.column_stack([np.ones(len(rs))] + [R(k) for k in ctrl])
    res = lambda v: v - C @ np.linalg.lstsq(C, v, rcond=None)[0]
    a, b = res(R(x)), res(R(y))
    if a.std() == 0 or b.std() == 0:
        return None, len(rs)
    return float(np.corrcoef(a, b)[0, 1]), len(rs)


def interval(rs, stat):
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(BOOT):
        v = stat([rs[i] for i in rng.integers(0, len(rs), len(rs))])
        if v is not None and math.isfinite(v):
            vals.append(v)
    if len(vals) < BOOT // 2:
        return None
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)]


def verdict(ci):
    if ci is None:
        return "not computed"
    return "supported" if ci[0] > 0 else "contradicted" if ci[1] < 0 else "not decided"


def corr_block(rs, x, y, ctrl, predicted: bool):
    v, n = partial(rs, x, y, ctrl)
    ci = interval(rs, lambda s: partial(s, x, y, ctrl)[0]) if v is not None else None
    out = {"colleges": n, "partial Spearman": None if v is None else round(v, 4), "95% interval": ci,
           "controls": ctrl}
    if predicted:
        out["verdict (predicted above zero)"] = verdict(ci)
    return out


def joint(rs, measure):
    rs = [r for r in rs if r[measure] is not None and r["debt trend"] is not None]
    med = float(np.median([r[measure] for r in rs]))
    grp = lambda r: ("thick" if r[measure] > med else "thin", "rising" if r["debt trend"] > 0 else "flat or falling")
    rate = lambda g: sum(r["closed"] for r in g) / len(g) if g else None
    out = {"median share": round(med, 4), "groups": {}}
    for layer in ("thin", "thick"):
        for debt in ("flat or falling", "rising"):
            g = [r for r in rs if grp(r) == (layer, debt)]
            out["groups"][f"{layer}, {debt}"] = {"colleges": len(g), "closed": int(sum(r["closed"] for r in g)),
                                                 "closure rate": None if rate(g) is None else round(rate(g), 4)}

        def diff(s, layer=layer):
            a = [r for r in s if grp(r) == (layer, "rising")]
            b = [r for r in s if grp(r) == (layer, "flat or falling")]
            return None if not a or not b else rate(a) - rate(b)
        d = diff(rs)
        ci = interval(rs, diff)
        out[f"{layer} layer: closure rate, rising minus flat debt"] = {
            "difference": None if d is None else round(d, 4), "95% interval": ci,
            "verdict (predicted above zero)": verdict(ci)}
    return out


def analyse(rows, measure):
    sectors = {"private": "private nonprofit", "public": "public", "forprofit": "for-profit"}
    base = ["size", "wealth"]
    res = {"1. debt": {}, "2. closure": {}, "3. joint reading": {}, "reported without prediction": {}}
    for y in ("debt", "debt trend"):
        res["1. debt"][f"{y}, all colleges (sector added as a control)"] = corr_block(
            rows, measure, y, base + ["public", "forprofit"], True)
        res["1. debt"][f"{y}, private nonprofit"] = corr_block(
            [r for r in rows if r["sector"] == "private"], measure, y, base, True)
    res["2. closure"]["all colleges (sector added as a control)"] = corr_block(
        rows, measure, "closed", base + ["public", "forprofit"], True)
    for code, name in sectors.items():
        g = [r for r in rows if r["sector"] == code]
        closures = int(sum(r["closed"] for r in g))
        ctrl = base + (["appropriations"] if code == "public" else [])
        if closures >= MIN_CLOSURES:
            res["2. closure"][name] = corr_block(g, measure, "closed", ctrl, True)
            res["3. joint reading"][name] = joint(g, measure)
        else:
            res["2. closure"][name] = {"closures": closures,
                                       "note": f"fewer than {MIN_CLOSURES} closures; reported only",
                                       **corr_block(g, measure, "closed", ctrl, False)}
        for y in ("full-time share", "adaptive capacity"):
            res["reported without prediction"][f"{y}, {name}"] = corr_block(g, measure, y, ctrl, False)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    root = Path(ap.parse_args().root)
    rows = load(root)
    out = {"protocol": "administrative layer retest protocol.md (pre-registered; exploratory, outcomes already recorded)",
           "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "colleges scored": len(rows),
           "with a core share": sum(r["core"] is not None for r in rows),
           "closures": int(sum(r["closed"] for r in rows)),
           "bootstrap": {"resamples": BOOT, "seed": SEED},
           "core administrative share (primary)": analyse(rows, "core"),
           "broad administrative share": analyse(rows, "broad")}
    path = root / "data" / "meta channel" / "administrative layer retest.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
