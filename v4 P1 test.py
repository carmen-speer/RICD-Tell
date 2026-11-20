"""
Prediction P1 of RICD 17.7 (Spine §15.2.1; Definition 15.2.8), tested as
fixed in "channel selection protocol.md", Amendment 5.

P1: colleges whose excess discount widened since their baseline, with the
published price not cut, are distressed more often than other colleges,
most of all among tuition-dependent private colleges.

For each development frame t (2014 and 2019):
  baseline t0   the first fiscal year in t-5 .. t at which the price gap is
                available (iota_price = 1)
  widening      Delta_ex = delta_ex(t) - delta_ex(t0), computed only where
                the price gap is available at both years under the same
                finance form and the same need fit (Definition 15.2.8)
  widened       Delta_ex above the 75th percentile of Delta_ex among the
                frame's colleges of the same control
  price not cut S_post at t, computed with the in-state weight of t0, at
                least S_post at t0, in nominal dollars; an inflation-
                adjusted version (CPI-U annual averages) is reported as a
                sensitivity check
  P1 flag       widened and price not cut
  outcome       closure, merger or deletion after the scoring year, primary
                coding of protocol v2 (HD files from year t on)
Reported, for private nonprofit colleges (primary group, Amendment 5), for
all colleges and for each control: closure rates of flagged and other
colleges, the ratio of the two rates with a 95% interval (log method), and
Fisher's exact test (one-sided, flagged more often; two-sided also given).

Output: data/v4 channels/P1 test.json

Usage (GitHub Actions only, via v4_P1_test.yml):
    cd src
    python "v4 P1 test.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("stages", HERE / "v4 selection stages 1 and 2.py")
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)
_spec3 = importlib.util.spec_from_file_location("stage3", HERE / "v4 selection stage 3.py")
s3 = importlib.util.module_from_spec(_spec3)
_spec3.loader.exec_module(s3)
OUT = st.DIR / "P1 test.json"
FRAMES = (2014, 2019)
WINDOW = 5
# CPI-U, U.S. city average, all items, annual averages (BLS series CUUR0000SA0), for the sensitivity check only
CPI = {2009: 214.537, 2010: 218.056, 2011: 224.939, 2012: 229.594, 2013: 232.957, 2014: 236.736,
       2015: 237.017, 2016: 240.007, 2017: 245.120, 2018: 251.107, 2019: 255.657}


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load():
    gaps, inputs, meta = {}, {}, {}
    with open(st.DIR / "gap values by year.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] == "price":
                gaps[(r["unitid"], int(r["year"]))] = r
    with open(st.DIR / "inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            inputs[(r["unitid"], int(r["fiscal year"]))] = r
            meta[r["unitid"]] = {"name": r["name"], "control": r["control"],
                                 2014: r["in 2014 frame"] == "True", 2019: r["in 2019 frame"] == "True"}
    return gaps, inputs, meta


def avail(g) -> bool:
    return g is not None and g.get("iota_price") in ("1", "1.0")


def s_post(inp, w):
    p_in, p_out = f(inp.get("published in-state")), f(inp.get("published out-of-state"))
    if p_in is None:
        return None
    if p_out is None or w is None:
        return p_in
    return w * p_in + (1 - w) * p_out


def widening(u, t, gaps, inputs) -> dict | None:
    g_t = gaps.get((u, t))
    if not avail(g_t):
        return None
    t0 = next((y for y in range(t - WINDOW, t + 1) if avail(gaps.get((u, y)))), None)
    if t0 is None or t0 == t:
        return None
    g0 = gaps[(u, t0)]
    if g0["finance form"] != g_t["finance form"] or g0["need fit"] != g_t["need fit"]:
        return {"t0": t0, "comparable": False}
    w0 = f(inputs[(u, t0)].get("in-state share"))
    s0, s_t = s_post(inputs[(u, t0)], w0), s_post(inputs[(u, t)], w0)
    if s0 is None or s_t is None:
        return {"t0": t0, "comparable": False}
    return {"t0": t0, "comparable": True, "delta_ex t0": f(g0["delta_ex"]), "delta_ex t": f(g_t["delta_ex"]),
            "Delta_ex": f(g_t["delta_ex"]) - f(g0["delta_ex"]), "S_post t0": s0, "S_post t (t0 weights)": s_t,
            "price not cut (nominal)": s_t >= s0,
            "price not cut (inflation-adjusted)": s_t / CPI[t] >= s0 / CPI[t0]}


def compare(rows, flag_key) -> dict:
    a = sum(1 for r in rows if r[flag_key] and r["closed"])
    b = sum(1 for r in rows if r[flag_key] and not r["closed"])
    c = sum(1 for r in rows if not r[flag_key] and r["closed"])
    d = sum(1 for r in rows if not r[flag_key] and not r["closed"])
    out = {"flagged": a + b, "flagged closed": a, "others": c + d, "others closed": c,
           "closure rate, flagged": a / (a + b) if a + b else None,
           "closure rate, others": c / (c + d) if c + d else None}
    if a + b and c + d and c:
        rr = (a / (a + b)) / (c / (c + d))
        out["rate ratio"] = rr
        if a:
            se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
            out["rate ratio 95% interval"] = [rr * math.exp(-1.959964 * se), rr * math.exp(1.959964 * se)]
    if a + b and c + d:
        out["Fisher exact p, one-sided (flagged more often)"] = float(fisher_exact([[a, b], [c, d]], alternative="greater")[1])
        out["Fisher exact p, two-sided"] = float(fisher_exact([[a, b], [c, d]])[1])
    return out


def run_frame(t, gaps, inputs, meta, closed) -> dict:
    rows = []
    for u, m in meta.items():
        if not m[t]:
            continue
        w = widening(u, t, gaps, inputs)
        if w and w["comparable"]:
            rows.append({"unitid": u, "control": m["control"], "closed": closed[u]} | w)
    thresholds = {}
    for ctrl in ("public", "private nonprofit", "for-profit"):
        v = [r["Delta_ex"] for r in rows if r["control"] == ctrl]
        thresholds[ctrl] = float(np.percentile(v, 75)) if v else None
    for r in rows:
        th = thresholds[r["control"]]
        r["widened"] = th is not None and r["Delta_ex"] > th
        r["P1 flag"] = r["widened"] and r["price not cut (nominal)"]
        r["P1 flag (inflation-adjusted)"] = r["widened"] and r["price not cut (inflation-adjusted)"]
    groups = {"private nonprofit (primary)": [r for r in rows if r["control"] == "private nonprofit"],
              "all": rows, "public": [r for r in rows if r["control"] == "public"],
              "for-profit": [r for r in rows if r["control"] == "for-profit"]}
    in_frame = sum(1 for m in meta.values() if m[t])
    return {"institutions in frame": in_frame, "with a comparable widening": len(rows),
            "75th-percentile thresholds by control": thresholds,
            "results": {g: {"nominal (primary)": compare(rs, "P1 flag"),
                            "inflation-adjusted (sensitivity)": compare(rs, "P1 flag (inflation-adjusted)"),
                            "widened alone, price not considered": compare(rs, "widened")}
                        for g, rs in groups.items()}}


def main() -> None:
    gaps, inputs, meta = load()
    result = {"test": "Prediction P1 (Spine §15.2.1), as fixed in channel selection protocol.md, Amendment 5",
              "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "limitation": "the excess discount is measured against a need-associated discount that in practice "
                            "is close to a sector average, so the widening is relative to comparable practice",
              "frames": {}}
    ids14 = [u for u, m in meta.items() if m[2014]]
    st.FRAME = 2014
    out14, files14 = st.outcomes(ids14)
    ids19 = [u for u, m in meta.items() if m[2019]]
    out19, files19, nf19 = s3.outcomes_2019(ids19)
    for t, out, files in ((2014, out14, files14), (2019, out19, files19)):
        closed = {u: bool(c["closed or failed (primary)"]) for u, c in out.items()}
        result["frames"][str(t)] = run_frame(t, gaps, inputs, meta, closed) | {"header files": files}
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    for t, fr in result["frames"].items():
        print(t, fr["with a comparable widening"], json.dumps(fr["results"]["private nonprofit (primary)"]["nominal (primary)"]))


if __name__ == "__main__":
    main()
