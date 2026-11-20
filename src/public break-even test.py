"""
Item 19 (exploratory): at public colleges, does a thicker administrative
layer sit closer to or past break-even, with appropriations held constant?

No closure outcome is read. Inputs already committed:
  administrative layer   data/meta channel/administrative layer.json
                         (core and broad shares, FTE-weighted, from the
                         IPEDS employees-by-position files; fall Y is
                         fiscal Y + 1)
  coverage, wealth       data/v4 channels/soundness inputs.csv (operating
                         coverage B_cov = total revenues / total expenses,
                         and state appropriations per FTE for public
                         colleges), fiscal 2013 to 2019
  frame, size            data/v4 channels/inputs.csv (public four-year
                         institutions in either development frame; FTE)

Prediction (the hypothesis, fixed here): a thicker administrative layer
goes with lower coverage, closer to or past break-even (B_cov < 1), at equal
appropriations per FTE and size.

Reported, over college-years pooled (institutions resampled in the
bootstrap, 2,000 resamples, seed 20261122):
  - the partial Spearman correlation of the core share with B_cov,
    controlling log appropriations per FTE and log FTE (ranks residualized
    on the controls' ranks), with a 95% interval; the same for the broad
    share
  - within each tercile of appropriations per FTE, coverage and the share
    of college-years past break-even across thirds of the core share
  - the same partial correlation by fiscal year

Output: data/meta channel/public break-even test.json

Usage (GitHub Actions or locally; no network needed):
    cd src
    python "public break-even test.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "meta channel" / "public break-even test.json"
SEED, BOOT = 20261122, 2000
_spec = importlib.util.spec_from_file_location("al", Path(__file__).resolve().parent / "administrative layer.py")
al = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(al)


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def load():
    layer = json.loads((ROOT / "data" / "meta channel" / "administrative layer.json").read_text(encoding="utf-8"))
    resolved = al.resolved_by_fall(layer)
    public, fte = set(), {}
    with open(ROOT / "data" / "v4 channels" / "inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["control"] == "public":
                public.add(r["unitid"])
                fte[(r["unitid"], int(r["fiscal year"]))] = f(r["FTE"])
    rows = []
    with open(ROOT / "data" / "v4 channels" / "soundness inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            u, y = r["unitid"], int(r["year"])
            if u not in public:
                continue
            b, w, n = f(r["B_cov"]), f(r["wealth per FTE"]), fte.get((u, y))
            rec = layer["by fall year"].get(str(y - 1), {}).get(u)
            if b is None or w is None or not n or w <= 0 or rec is None:
                continue
            res = resolved.get(str(y - 1), set())
            core = al.shares(rec, al.CORE, True, res)
            broad = al.shares(rec, al.BROAD, True, res)
            if core is None:
                continue
            rows.append({"unitid": u, "year": y, "B_cov": b, "log approp": math.log(w), "log FTE": math.log(n),
                         "core": core, "broad": broad})
    return rows


def partial_spearman(x, y, z) -> float:
    rx, ry = rankdata(x), rankdata(y)
    Z = np.column_stack([np.ones(len(x))] + [rankdata(c) for c in z])
    ex = rx - Z @ np.linalg.lstsq(Z, rx, rcond=None)[0]
    ey = ry - Z @ np.linalg.lstsq(Z, ry, rcond=None)[0]
    return float(np.corrcoef(ex, ey)[0, 1])


def with_interval(rows, share) -> dict:
    g = [r for r in rows if r[share] is not None]
    arr = lambda k, s: np.array([r[k] for r in s])
    est = partial_spearman(arr(share, g), arr("B_cov", g), [arr("log approp", g), arr("log FTE", g)])
    ids = sorted({r["unitid"] for r in g})
    by = {}
    for r in g:
        by.setdefault(r["unitid"], []).append(r)
    rng, boots = np.random.default_rng(SEED), []
    for _ in range(BOOT):
        s = [r for u in rng.choice(ids, len(ids)) for r in by[u]]
        boots.append(partial_spearman(arr(share, s), arr("B_cov", s), [arr("log approp", s), arr("log FTE", s)]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"college-years": len(g), "institutions": len(ids), "partial Spearman (share, B_cov | appropriations, size)": est,
            "95% interval": [float(lo), float(hi)],
            "direction": ("thicker layer, lower coverage (as predicted)" if hi < 0 else
                          "thicker layer, higher coverage (opposite to prediction)" if lo > 0 else "not separated from zero")}


def main() -> None:
    rows = load()
    if len(rows) < 300:
        raise SystemExit(f"Only {len(rows)} public college-years with every input; inputs misread. Nothing recorded.")
    ap = np.array([r["log approp"] for r in rows])
    ap_cuts = np.percentile(ap, [100 / 3, 200 / 3])
    table = {}
    for k, name in enumerate(("lowest", "middle", "highest")):
        g = [r for r in rows if (k == 0 and r["log approp"] <= ap_cuts[0]) or
             (k == 1 and ap_cuts[0] < r["log approp"] <= ap_cuts[1]) or (k == 2 and r["log approp"] > ap_cuts[1])]
        c = np.percentile([r["core"] for r in g], [100 / 3, 200 / 3])
        cells = {}
        for j, third in enumerate(("thinnest third", "middle third", "thickest third")):
            h = [r for r in g if (j == 0 and r["core"] <= c[0]) or (j == 1 and c[0] < r["core"] <= c[1]) or
                 (j == 2 and r["core"] > c[1])]
            cells[third] = {"college-years": len(h), "median B_cov": float(np.median([r["B_cov"] for r in h])),
                            "share past break-even (B_cov < 1)": float(np.mean([r["B_cov"] < 1 for r in h]))}
        table[f"{name} appropriations per FTE"] = cells
    by_year = {}
    for y in sorted({r["year"] for r in rows}):
        g = [r for r in rows if r["year"] == y]
        arr = lambda k: np.array([r[k] for r in g])
        by_year[str(y)] = {"n": len(g), "partial Spearman": partial_spearman(arr("core"), arr("B_cov"),
                                                                              [arr("log approp"), arr("log FTE")])}
    result = {"test": "Item 19 (exploratory): administrative layer and break-even at public four-year colleges",
              "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "prediction": "a thicker administrative layer goes with lower coverage at equal appropriations per FTE and size",
              "no closure outcome was read": True,
              "core share": with_interval(rows, "core"), "broad share (sensitivity)": with_interval(rows, "broad"),
              "by appropriations tercile and core-share third": table, "core share by fiscal year": by_year,
              "limitations": ["coverage counts all revenues, appropriations included, against all expenses",
                              "staffing shares are from the employees-by-position files; fall Y is fiscal Y + 1"]}
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("core share", "broad share (sensitivity)")}, indent=1))


if __name__ == "__main__":
    main()
