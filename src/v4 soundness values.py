"""
v4 soundness dimension: inputs, frozen norms and readings
("channel selection protocol.md", Amendment 6; Spine Definitions 15.2.15,
15.2.16).

Reads the IPEDS staffing (S{y}_OC), new-hire (S{y}_NH) and finance files
(F1A, F2, F3) and step 1's inputs (frames, control, FTE). No closure
outcome is read.

  x_exit(t)  = max(0, NH(t) - (FT(t) - FT(t-1))) / FT(t-1), t = 2013..2019
  B_cov(t)   = total revenues / total expenses, fiscal t
  wealth(t)  = endowment per FTE (private nonprofit), state appropriations
               per FTE (public); none for for-profit (pooled, flagged)
  norms      per comparability segment (Amendment 7): fitted on staffing
             years 2013 and 2014 for the 2014 frame and 2016 and 2017 for the
             2019 frame (IPEDS widened the new-hire window from July 1 to
             October 31 to a full twelve months in 2016), over every institution
             in either frame, then frozen: wealth terciles by control;
             x_norm = median x_exit by control and band (m_min = 20, merge
             with the adjacent band holding more colleges, the lower on a
             tie; then pool the control; then unavailable); x_ref = 95th
             percentile of x_ex by control (n_pos = 20), 90th and 97.5th
             as sensitivity
  readings   at t = 2014 and 2019: s_p, s_ins, D_op, D_om, D_pm, sign

Writes data/v4 channels/"soundness norms.json" and
"soundness values at scoring years.csv" (and "soundness inputs.csv").

Usage (GitHub Actions only, via v4_soundness_values.yml):
    cd src
    python "v4 soundness values.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import json
from pathlib import Path

import numpy as np

import meta_channel as mc

HERE = Path(__file__).resolve().parent
DIR = HERE.parent / "data" / "v4 channels"
_g = importlib.util.spec_from_file_location("gaps", HERE / "v4 gap values.py")
gv = importlib.util.module_from_spec(_g)
_g.loader.exec_module(gv)
_s = importlib.util.spec_from_file_location("step1", HERE / "v4 step 1 calibrations.py")
s1 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(s1)

STAFF_YEARS = range(2012, 2020)
FISCAL = range(2013, 2020)
NORM_YEARS = (2013, 2014)
NORM_YEARS_B = (2016, 2017)   # Amendment 7: the new-hire definition changed in 2016
FRAMES = (2014, 2019)
M_MIN, N_POS = 20, 20
FIN = {"public": ("F1A", "F1D01", "F1D02"), "private nonprofit": ("F2", "F2B01", "F2B02"),
       "for-profit": ("F3", "F3D09", "F3B02")}
WEALTH = {"public": ("F1A", "F1B11"), "private nonprofit": ("F2", "F2H02")}
num = s1.num


def staff(y: int):
    oc, nh = s1.table(f"S{y}_OC"), s1.table(f"S{y}_NH")
    ft = {u: num(next((r.get("HRTOTLT") for r in rows if r.get("FTPT") == "2" and r.get("OCCUPCAT") == "100"), None))
          for u, rows in (oc or {}).items()}
    new = {u: num(next((r.get("HRTOTLT") for r in rows if r.get("SNHCAT") == "10000"), None))
           for u, rows in (nh or {}).items()}
    return ft, new, {"S_OC": "missing" if oc is None else len(oc), "S_NH": "missing" if nh is None else len(nh)}


def finance(f: int):
    a, b = (f - 1) % 100, f % 100
    t = {form: s1.table(f"F{a:02d}{b:02d}_{form}") for form in ("F1A", "F2", "F3")}
    return t, {k: "missing" if v is None else len(v) for k, v in t.items()}


def main() -> None:
    meta, fte = {}, {}
    with open(DIR / "inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            meta[r["unitid"]] = {"name": r["name"], "control": r["control"],
                                 2014: r["in 2014 frame"] == "True", 2019: r["in 2019 frame"] == "True"}
            fte[(r["unitid"], int(r["fiscal year"]))] = num(r["FTE"])
    log = {}
    FT, NH = {}, {}
    for y in STAFF_YEARS:
        FT[y], NH[y], log[f"staff {y}"] = staff(y)
        print("staff", y, log[f"staff {y}"], flush=True)
    rows = {}
    for f in FISCAL:
        tabs, log[f"finance {f}"] = finance(f)
        print("finance", f, log[f"finance {f}"], flush=True)
        for u, m in meta.items():
            c = m["control"]
            rec = {"unitid": u, "year": f, "control": c}
            form, rv, ex = FIN.get(c, (None, None, None))
            row = (tabs.get(form) or {}).get(u, [{}])[0] if form else {}
            rev, exp = num(row.get(rv)) if rv else None, num(row.get(ex)) if ex else None
            rec["B_cov"] = rev / exp if (rev is not None and exp and exp > 0) else None
            w = WEALTH.get(c)
            wv = num((tabs.get(w[0]) or {}).get(u, [{}])[0].get(w[1])) if w else None
            n = fte.get((u, f))
            rec["wealth per FTE"] = wv / n if (wv is not None and n) else None
            ft0, ft1, nh = FT[f - 1].get(u), FT[f].get(u), NH[f].get(u)
            rec["FT(t-1)"], rec["FT(t)"], rec["NH(t)"] = ft0, ft1, nh
            rec["x_exit"] = (max(0.0, nh - (ft1 - ft0)) / ft0
                             if (ft0 and ft0 > 0 and ft1 is not None and nh is not None) else None)
            rows[(u, f)] = rec
    if sum(1 for r in rows.values() if r["x_exit"] is not None) < 3000:
        raise SystemExit("Too few exit rates; staffing files misread. Nothing recorded.")

    # ---------- norms, fixed per comparability segment and frozen (Amendment 7)
    in_dev = {u for u, m in meta.items() if m[2014] or m[2019]}

    def fit_norms(years):
        fit = [r for (u, f), r in rows.items() if f in years and u in in_dev and r["x_exit"] is not None]
        norms = {"norm years": list(years), "m_min": M_MIN, "n_pos": N_POS, "by control": {}}
        for c in ("public", "private nonprofit", "for-profit"):
            g = [r for r in fit if r["control"] == c]
            nc = {"fit college-years": len(g)}
            wv = [r["wealth per FTE"] for r in g if r["wealth per FTE"] is not None]
            if c in WEALTH and len(wv) >= 3 * M_MIN:
                cuts = [float(np.percentile(wv, 100 / 3)), float(np.percentile(wv, 200 / 3))]
                nc["tercile cuts"] = cuts
                band = lambda v, cuts=cuts: None if v is None else (0 if v <= cuts[0] else 1 if v <= cuts[1] else 2)
                cells = {k: [r["x_exit"] for r in g if band(r["wealth per FTE"]) == k] for k in (0, 1, 2)}
                final = {}
                for k in (0, 1, 2):
                    if len(cells[k]) >= M_MIN:
                        final[k] = {"bands": [k], "values": cells[k]}
                        continue
                    adj = [j for j in (k - 1, k + 1) if j in cells]
                    j = max(adj, key=lambda j: (len(cells[j]), -j))
                    merged = cells[k] + cells[j]
                    final[k] = ({"bands": sorted([k, j]), "values": merged} if len(merged) >= M_MIN else
                                {"bands": [0, 1, 2], "values": [r["x_exit"] for r in g]})
                nc["cells"] = {str(k): {"bands merged": v["bands"], "n": len(v["values"]),
                                        "x_norm": float(np.median(v["values"]))} for k, v in final.items()}
            pooled = [r["x_exit"] for r in g]
            nc["pooled"] = {"n": len(pooled), "x_norm": float(np.median(pooled)) if len(pooled) >= M_MIN else None}
            norms["by control"][c] = nc
        for c in ("public", "private nonprofit", "for-profit"):
            nc = norms["by control"][c]
            ex = [max(0.0, r["x_exit"] - x_norm(r, norms)[0]) for r in fit
                  if r["control"] == c and x_norm(r, norms)[0] is not None]
            pos = [e for e in ex if e > 0]
            nc["positive excess exit (fit)"] = len(pos)
            for q in (90, 95, 97.5):
                nc[f"x_ref p{q}"] = (float(np.percentile(ex, q)) if len(pos) >= N_POS and np.percentile(ex, q) > 0 else None)
        return norms

    def x_norm(r, norms):
        nc = norms["by control"][r["control"]]
        if "tercile cuts" in nc and r["wealth per FTE"] is not None:
            cuts = nc["tercile cuts"]
            k = 0 if r["wealth per FTE"] <= cuts[0] else 1 if r["wealth per FTE"] <= cuts[1] else 2
            return nc["cells"][str(k)]["x_norm"], "band"
        return nc["pooled"]["x_norm"], "pooled (no wealth band)"

    segments = {"A (new hires July 1 to October 31; staffing years 2013-2015)": fit_norms(NORM_YEARS),
                "B (new hires over twelve months; staffing years 2016 on)": fit_norms(NORM_YEARS_B)}
    seg_for = {2014: list(segments)[0], 2019: list(segments)[1]}

    # ---------- readings at the scoring years
    out = []
    for t in FRAMES:
        for u, m in sorted(meta.items()):
            if not m[t]:
                continue
            r = rows.get((u, t), {"B_cov": None, "x_exit": None, "wealth per FTE": None, "control": m["control"]})
            rec = {"unitid": u, "name": m["name"], "control": m["control"], "frame": t, "B_cov": r["B_cov"],
                   "x_exit": r["x_exit"], "wealth per FTE": r["wealth per FTE"]}
            rec["iota_sound"] = int(r["B_cov"] is not None)
            if r["B_cov"] is not None:
                rec["s_p"] = min(1.0, max(0.0, r["B_cov"]))
                rec["D_op_sound"] = gv.g_js(1 - rec["s_p"])
            norms = segments[seg_for[t]]
            rec["exit segment"] = seg_for[t]
            xn, how = x_norm(r, norms) if r["x_exit"] is not None else (None, "")
            xr = norms["by control"][m["control"]]["x_ref p95"]
            rec["norm used"] = how
            rec["meta available"] = int(r["x_exit"] is not None and xn is not None and xr is not None)
            if rec["meta available"]:
                rec["x_ex"] = max(0.0, r["x_exit"] - xn)
                rec["s_ins"] = 1 - min(1.0, rec["x_ex"] / xr)
                rec["D_om_sound"] = gv.g_js(1 - rec["s_ins"])
                for q in (90, 97.5):
                    xq = norms["by control"][m["control"]][f"x_ref p{q}"]
                    rec[f"D_om_sound (x_ref p{q})"] = gv.g_js(min(1.0, rec["x_ex"] / xq)) if xq else None
                if "s_p" in rec:
                    rec["D_pm_sound"] = gv.js(rec["s_p"], rec["s_ins"])
                    rec["sign s_p - s_ins"] = (rec["s_p"] > rec["s_ins"]) - (rec["s_p"] < rec["s_ins"])
            out.append(rec)
    DIR.mkdir(parents=True, exist_ok=True)
    cols = list(dict.fromkeys(k for r in out for k in r))
    with open(DIR / "soundness values at scoring years.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    icols = ["unitid", "year", "control", "B_cov", "wealth per FTE", "FT(t-1)", "FT(t)", "NH(t)", "x_exit"]
    with open(DIR / "soundness inputs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=icols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows[k] for k in sorted(rows))
    summary = {}
    for t in FRAMES:
        g = [r for r in out if r["frame"] == t]
        summary[str(t)] = {c: {"institutions": sum(r["control"] == c for r in g),
                               "coverage available": sum(r["control"] == c and r["iota_sound"] for r in g),
                               "exit reading available": sum(r["control"] == c and r["meta available"] for r in g),
                               "median B_cov": float(np.median([r["B_cov"] for r in g if r["control"] == c and r["B_cov"] is not None] or [np.nan])),
                               "median x_exit": float(np.median([r["x_exit"] for r in g if r["control"] == c and r["x_exit"] is not None] or [np.nan])),
                               "share with excess exit": float(np.mean([r["x_ex"] > 0 for r in g if r["control"] == c and r["meta available"]] or [np.nan]))}
                           for c in ("public", "private nonprofit", "for-profit")}
    (DIR / "soundness norms.json").write_text(json.dumps({
        "note": "v4 soundness dimension (Amendment 6): frozen norms and summary. No closure outcome was read.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "norms by comparability segment (Amendment 7)": segments, "segment used by frame": seg_for, "summary at scoring years": summary, "files read": log,
        "limitations": ["x_exit is a residual under a headcount model; new hires are counted July 1 to October 31 only",
                        "private revenue includes investment return, so coverage moves with markets"]},
        indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
