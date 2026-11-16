"""
Exploratory test of the secure (tenure-protected) staff share as the meta
channel, on the 670 development colleges only (the v2 training draw, scored
for 2014, and the v2 test draw, scored for 2019), whose outcomes are already
known. The v3 test colleges are held back for a pre-registered retest, fixed
after this test and before it runs.

Hypothesis: the meta channel is the population that can transmit dissent
accurately, and job security is what makes that possible (RICD Spine §15.2).
A college with more tenure-protected instructional staff catches and
corrects official-operational divergence, so it carries less of its cost.

Predictions, fixed here, for each share version (secure, tenured only,
secure with indefinite contracts), with size and wealth held constant:
  1. a higher share goes with less resource debt (delta_R_final) and a
     flatter debt trend (delta_R_trend): partial correlation below zero;
  2. a higher share goes with less closure: partial correlation below zero;
  3. a higher share goes with more adaptive capacity (d_A_final): above zero.
Each is tested for all colleges together (sector added as a control) and
within private nonprofit colleges, and closure also within for-profit
colleges (sectors with at least 10 closures). Reported without prediction:
the same without controls, and the share against the core administrative
share and the full-time instructional share.

"Held constant" is a partial Spearman correlation (ranks residualized on the
controls' ranks). Size: log instructional staff headcount; wealth:
reserve_adequacy. The share is read in the fall before the scoring year, or
the latest earlier fall from 2012. 95% bootstrap intervals, colleges
resampled, 2,000 resamples, seed 20261116.

Output: data/meta channel/tenure share test.json

Usage:
    cd src
    python "tenure share test.py"      [--root DIR for testing]
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ts = _load("tenure_share", "tenure share.py")
rt = _load("retest", "administrative layer retest.py")
al = rt.al
MIN_CLOSURES = 10
PREDICTED = {"debt": -1, "debt trend": -1, "closed": -1, "adaptive capacity": +1}


def outcomes(root: Path) -> dict:
    out = {}
    for year, f in ((2014, "training outcomes.json"), (2019, "test outcomes.json")):
        for r in json.loads((root / "data" / "v2" / f).read_text())["institutions"]:
            out[f"{year}:{r['unitid']}"] = bool(r["closed or failed (primary)"])
    return out


def load(root: Path) -> list[dict]:
    mc = root / "data" / "meta channel"
    ten = json.loads((mc / "tenure share.json").read_text())
    ten_res = ts.resolved_by_fall(ten)
    layer = json.loads((mc / "administrative layer.json").read_text())
    lay_res = al.resolved_by_fall(layer)
    staff = json.loads((mc / "instructional staff share.json").read_text())["by fall year"]
    outs = outcomes(root)

    def latest(scoring_year, fn):
        for fall in range(scoring_year - 1, 2011, -1):
            v = fn(fall)
            if v is not None:
                return v
        return None

    rows = []
    for p in sorted((root / "data" / "v3 reanalysis" / "rescored").glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            if r["key"].startswith("v3test:") or r["status"] != "scored" or r["key"] not in outs:
                continue
            u, y, f = r["unitid"], r["scoring year"], r["features"]
            row = {"key": r["key"], "sector": r["sector"], "closed": float(outs[r["key"]]),
                   "debt": f["delta_R_final"], "debt trend": f["delta_R_trend"],
                   "adaptive capacity": f["d_A_final"], "wealth": f["reserve_adequacy"],
                   "public": float(r["sector"] == "public"), "forprofit": float(r["sector"] == "forprofit")}
            for v in ts.VERSIONS:
                row[v] = latest(y, lambda fall, v=v: (lambda rec: ts.share(rec, v, ten_res.get(str(fall), set()))
                                                        if rec else None)(ten["by fall year"].get(str(fall), {}).get(u)))
            row["core administrative share"] = latest(y, lambda fall: (lambda rec: al.shares(
                rec, al.CORE, True, lay_res.get(str(fall), set())) if rec else None)(
                layer["by fall year"].get(str(fall), {}).get(u)))
            st = latest(y, lambda fall: staff.get(str(fall), {}).get(u) if sum(staff.get(str(fall), {}).get(u) or [0]) > 0 else None)
            row["size"] = math.log(sum(st)) if st else None
            row["full-time share"] = st[0] / sum(st) if st else None
            rows.append(row)
    return rows


def block(rs, x, y, ctrl, sign):
    v, n = rt.partial(rs, x, y, ctrl)
    ci = rt.interval(rs, lambda s: rt.partial(s, x, y, ctrl)[0]) if v is not None else None
    out = {"colleges": n, "partial Spearman": None if v is None else round(v, 4), "95% interval": ci,
           "controls": ctrl}
    if sign:
        word = "below" if sign < 0 else "above"
        if ci is None:
            verdict = "not computed"
        elif (sign < 0 and ci[1] < 0) or (sign > 0 and ci[0] > 0):
            verdict = "supported"
        elif (sign < 0 and ci[0] > 0) or (sign > 0 and ci[1] < 0):
            verdict = "contradicted"
        else:
            verdict = "not decided"
        out[f"verdict (predicted {word} zero)"] = verdict
    return out


def analyse(rows, version):
    base = ["size", "wealth"]
    res = {"predictions (size and wealth held constant)": {}, "reported without prediction": {}}
    groups = {"all colleges (sector added as a control)": (rows, base + ["public", "forprofit"]),
              "private nonprofit": ([r for r in rows if r["sector"] == "private"], base),
              "for-profit": ([r for r in rows if r["sector"] == "forprofit"], base),
              "public": ([r for r in rows if r["sector"] == "public"], base)}
    for gname, (g, ctrl) in groups.items():
        closures = int(sum(r["closed"] for r in g))
        for y, sign in PREDICTED.items():
            tested = (gname != "public" and (gname != "for-profit" or y == "closed")
                      and (y != "closed" or closures >= MIN_CLOSURES))
            key = f"{y}, {gname}"
            (res["predictions (size and wealth held constant)"] if tested else res["reported without prediction"])[key] = \
                {"closures": closures, **block(g, version, y, ctrl, sign if tested else 0)}
            res["reported without prediction"][f"{y}, {gname}, no controls"] = block(g, version, y, [], 0)
        for other in ("core administrative share", "full-time share"):
            res["reported without prediction"][f"{other}, {gname}"] = block(g, version, other, ctrl, 0)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(HERE.parent))
    root = Path(ap.parse_args().root)
    rows = load(root)
    out = {"note": ("Exploratory: development colleges only, outcomes already known. The v3 test colleges are "
                    "held back for a pre-registered retest, fixed after this test."),
           "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "development colleges scored": len(rows), "closures": int(sum(r["closed"] for r in rows)),
           "bootstrap": {"resamples": rt.BOOT, "seed": rt.SEED}}
    for v in ts.VERSIONS:
        out[v] = {"colleges with a value": sum(r[v] is not None for r in rows), **analyse(rows, v)}
    path = root / "data" / "meta channel" / "tenure share test.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
