"""
Item 17 (exploratory): adjunct absorption ("channel selection protocol.md",
Amendment 9).

Reads the IPEDS employees-by-position files (EAP{y}) and full-time new-hire
files (S{y}_NH), fall 2012 to the latest served, finding every category by
its label in that year's data dictionary, and computes for each institution
and fall year:

  pool share      part-time instructional headcount / all instructional
  contract mix    full-time instructional staff with faculty status on annual
                  or less-than-annual contracts / all full-time instructional
                  staff with faculty status
  turnover        max(0, NH(t) - (FT(t) - FT(t-1))) / FT(t-1), full-time
                  instructional staff, for the tenure line (tenured + on
                  track) and off the track (not on track + without faculty
                  status), segment A through fall 2015, B from fall 2016
  depletion       (PT(t) - PT(t-1)) / PT(t-1), part-time instructional

Then the crossing-curves test on the 2014 frame at equal wealth: heavy
absorbers (top quarter of pool share at fall 2014 within control and the
frozen segment-A wealth tercile; for-profits one pooled cell) against the
rest, cumulative closure curves by year from 2015.

Outputs: data/meta channel/adjunct absorption.json and
data/v3 exploratory/adjunct absorption test.json.

Exploratory: the 2014 frame's outcomes are known in aggregate. The
prediction is tested blind with the HD2026 retest.

Usage (GitHub Actions only, via adjunct_absorption.yml):
    cd src
    python "adjunct absorption.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import json
from pathlib import Path

import numpy as np

import meta_channel as mc
import v2_training_outcomes as coding

HERE = Path(__file__).resolve().parent
DIR4 = HERE.parent / "data" / "v4 channels"
OUT_MEASURES = HERE.parent / "data" / "meta channel" / "adjunct absorption.json"
OUT_TEST = HERE.parent / "data" / "v3 exploratory" / "adjunct absorption test.json"
_spec = importlib.util.spec_from_file_location("sfc", HERE / "v4 soundness field check.py")
sfc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sfc)

FIRST_FALL = 2012
FRAME, READ_FALL = 2014, 2014
SEED, BOOT = 20261124, 2000
MIN_HD_ROWS = 3000

OCC_LABELS = {"instructional staff total", "instructional staff"}
FAC_LABELS = {
    "all": {"all staff", "all full time new hires"},
    "faculty total": {"with faculty status total"},
    "tenured": {"with faculty status tenured"},
    "track": {"with faculty status on tenure track"},
    "off track": {"with faculty status not on tenure track no tenure system total"},
    "annual": {"with faculty status not on tenure track no tenure system annual contract"},
    "less than annual": {"with faculty status not on tenure track no tenure system less than annual contract"},
    "no faculty status": {"without faculty status"},
}


def resolve(name: str) -> tuple[dict, dict, str]:
    """Codes for the instructional occupation and each faculty-status category, by label."""
    d = sfc.variables(name)
    if d["status"] != "read":
        raise SystemExit(f"{name}: data dictionary not read ({d['status']}). Nothing recorded.")
    labels = d.get("code labels", {})
    occ = [c for c, l in labels.get("OCCUPCAT", {}).items() if mc.norm(l) in OCC_LABELS]
    found, unresolved = {}, {}
    if len(occ) == 1:
        found["occupation"] = occ[0]
    else:
        unresolved["occupation"] = occ
    for cat, want in FAC_LABELS.items():
        hits = [c for c, l in labels.get("FACSTAT", {}).items() if mc.norm(l) in want]
        if len(hits) == 1:
            found[cat] = hits[0]
        else:
            unresolved[cat] = hits
    return found, unresolved, d.get("dictionary url", "")


def read(table: str, fields: tuple[str, ...], required: bool):
    got = mc.fetch(f"{table}.zip", required)
    if got is None:
        return None
    found, unresolved, durl = resolve(table)
    by_code = {v: k for k, v in found.items() if k != "occupation"}
    name, text = mc.first_csv(got[0])
    values = {}
    for r in mc.rows(text):
        u = r.get("UNITID")
        if not u or r.get("OCCUPCAT") != found.get("occupation"):
            continue
        cat = by_code.get(r.get("FACSTAT"))
        if cat is None:
            continue
        values.setdefault(u, {})[cat] = [int(mc.number(r.get(f)) or 0) for f in fields]
    return {"file": {"table": table, "url": got[1], "csv": name, "dictionary url": durl,
                     "categories": found, "unresolved categories": unresolved}, "values": values}


def ratio(a, b):
    return a / b if b and b > 0 else None


def measures(eap: dict, nh: dict | None, prev: dict | None, res: set, res_nh: set, res_prev: set) -> dict:
    """eap values are [EAPTOT, EAPFT, EAPPT]; nh values are [HRTOTLT]."""
    out = {}
    for u, rec in eap.items():
        m = {}
        allc = rec.get("all")
        if "all" in res and allc:
            m["pool share"] = ratio(allc[2], allc[0])
        if {"faculty total", "annual", "less than annual"} <= res and rec.get("faculty total"):
            m["contract mix"] = ratio(rec.get("annual", [0, 0, 0])[1] + rec.get("less than annual", [0, 0, 0])[1],
                                      rec["faculty total"][1])
        if prev is not None and u in prev:
            p = prev[u]
            if "all" in res and "all" in res_prev and p.get("all") and allc:
                m["pool depletion"] = ratio(allc[2] - p["all"][2], p["all"][2])
            for line, cats in (("tenure line", ("tenured", "track")), ("off track", ("off track", "no faculty status"))):
                if not (set(cats) <= res and set(cats) <= res_prev and set(cats) <= res_nh) or nh is None:
                    continue
                ft = sum(rec.get(c, [0, 0, 0])[1] for c in cats)
                ft0 = sum(p.get(c, [0, 0, 0])[1] for c in cats)
                new = sum(nh.get(u, {}).get(c, [0])[0] for c in cats)
                if ft0 > 0:
                    m[f"turnover, {line}"] = max(0.0, new - (ft - ft0)) / ft0
        out[u] = m
    return out


def frame_2014() -> dict:
    rows = {}
    with open(DIR4 / "inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["fiscal year"]) == FRAME and r["in 2014 frame"] == "True":
                rows[r["unitid"]] = {"name": r["name"], "control": r["control"], "wealth": None}
    with open(DIR4 / "soundness inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["unitid"] in rows and int(r["year"]) == FRAME and r["wealth per FTE"]:
                rows[r["unitid"]]["wealth"] = float(r["wealth per FTE"])
    norms = json.loads((DIR4 / "soundness norms.json").read_text())["norms by comparability segment (Amendment 7)"]
    seg_a = next(v for k, v in norms.items() if k.startswith("A"))["by control"]
    for g in rows.values():
        cuts = seg_a.get(g["control"], {}).get("tercile cuts")
        if g["control"] == "for-profit" or not cuts:
            g["cell"] = (g["control"], "pooled")
        elif g["wealth"] is None:
            g["cell"] = (g["control"], "no wealth value")
        else:
            g["cell"] = (g["control"], 0 if g["wealth"] <= cuts[0] else 1 if g["wealth"] <= cuts[1] else 2)
    return rows


def closure_years(ids: list[str]) -> tuple[dict, list, int]:
    coding.SCORING_YEAR = FRAME
    tables, files = {}, []
    for y in range(FRAME, datetime.date.today().year + 1):
        try:
            hd = coding.download_hd(y)
        except SystemExit:
            if y <= 2025:
                raise
            continue
        t = coding.rows_by_id(hd["csv"])
        if len(t) < MIN_HD_ROWS:
            raise SystemExit(f"HD{y} yielded {len(t)} institutions; misread. Nothing recorded.")
        tables[y] = t
        files.append({k: v for k, v in hd.items() if k != "csv"} | {"institutions read": len(t)})
    years = sorted(tables)
    coding.FILES = years
    out = {}
    for u in ids:
        rows = {y: tables[y].get(u) for y in years}
        c = coding.code(u, rows)
        if not c["closed or failed (primary)"]:
            out[u] = None
            continue
        standing = [e["year"] for e in c["events"] if not e["voided by reappearance as active"]]
        if standing:
            out[u] = max(FRAME + 1, min(standing))
        else:
            present = [y for y, r in rows.items() if r]
            out[u] = (max(present) + 1) if present else FRAME + 1
    return out, files, years[-1]


def curves(group, years):
    n = len(group)
    return {str(y): sum(1 for g in group if g["closed"] and g["closed"] <= y) / n for y in years} if n else {}


def main() -> None:
    falls, not_served = {}, []
    for y in range(FIRST_FALL, datetime.date.today().year + 1):
        eap = read(f"EAP{y}", ("EAPTOT", "EAPFT", "EAPPT"), required=(y <= 2023))
        if eap is None:
            not_served.append(f"EAP{y}")
            continue
        nh = read(f"S{y}_NH", ("HRTOTLT",), required=False)
        falls[y] = {"EAP": eap, "NH": nh}
    if READ_FALL not in falls:
        raise SystemExit(f"EAP{READ_FALL} not read. Nothing recorded.")
    by_fall, files = {}, []
    for y in sorted(falls):
        e, n = falls[y]["EAP"], falls[y]["NH"]
        p = falls.get(y - 1, {}).get("EAP")
        res = set(e["file"]["categories"])
        by_fall[y] = measures(e["values"], n["values"] if n else None, p["values"] if p else None, res,
                              set(n["file"]["categories"]) if n else set(),
                              set(p["file"]["categories"]) if p else set())
        files += [e["file"]] + ([n["file"]] if n else [f"S{y}_NH not served"])

    keys = ("pool share", "contract mix", "pool depletion", "turnover, tenure line", "turnover, off track")
    sec = mc.sectors()
    summary = {str(y): {name: {k: mc.quantiles([m[k] for u, m in v.items() if sec["sector"].get(u) == code
                                                and m.get(k) is not None]) for k in keys}
                        for code, name in mc.SECTOR_NAMES.items()} for y, v in by_fall.items()}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    OUT_MEASURES.parent.mkdir(parents=True, exist_ok=True)
    OUT_MEASURES.write_text(json.dumps({
        "measures": "Amendment 9 (item 17): pool share, contract mix, turnover by line, pool depletion; fall year Y",
        "turnover segments": "A through fall 2015 (new hires July 1 to October 31); B from fall 2016 (twelve months)",
        "written at (UTC)": now, "files": files, "files not served": not_served,
        "medians and quartiles by fall year and sector": summary,
        "by fall year": {str(y): v for y, v in by_fall.items()}}, indent=1) + "\n", encoding="utf-8")

    # The crossing-curves test (exploratory)
    fr = frame_2014()
    read14 = by_fall[READ_FALL]
    scored = {u: g | {"pool share": read14.get(u, {}).get("pool share")} for u, g in fr.items()}
    have = {u: g for u, g in scored.items() if g["pool share"] is not None}
    cells = {}
    for u, g in have.items():
        cells.setdefault(g["cell"], []).append(u)
    for cell, us in cells.items():
        cut = float(np.percentile([have[u]["pool share"] for u in us], 75))
        for u in us:
            have[u]["heavy"] = have[u]["pool share"] > cut
            have[u]["cell cut"] = cut
    closed, hd_files, last = closure_years(list(fr))
    for u, g in scored.items():
        g["closed"] = closed[u]
    years = list(range(FRAME + 1, last + 1))
    rng = np.random.default_rng(SEED)

    def diff_ci(a, b, y):
        d = []
        for _ in range(BOOT):
            ia, ib = rng.choice(len(a), len(a)), rng.choice(len(b), len(b))
            d.append(np.mean([a[i]["closed"] is not None and a[i]["closed"] <= y for i in ia])
                     - np.mean([b[i]["closed"] is not None and b[i]["closed"] <= y for i in ib]))
        return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]

    def block(sel):
        h = [g for g in sel if g["heavy"]]
        r = [g for g in sel if not g["heavy"]]
        if not h or not r:
            return {"heavy absorbers": len(h), "others": len(r), "note": "a group is empty; not computed"}
        ch, cr = curves(h, years), curves(r, years)
        out = {"heavy absorbers": len(h), "others": len(r),
               "heavy closed": sum(1 for g in h if g["closed"]), "others closed": sum(1 for g in r if g["closed"]),
               "cumulative closure rate by year, heavy": ch, "cumulative closure rate by year, others": cr,
               "first year the heavy curve is above the others'": next((y for y in years if ch[str(y)] > cr[str(y)]), None)}
        for y in (2017, last):
            out[f"difference at {y} (heavy - others)"] = ch[str(y)] - cr[str(y)]
            out[f"95% interval at {y}"] = diff_ci(h, r, y)
        return out

    groups = list(have.values())
    overall = block(groups)
    verdict = "not computed"
    if "difference at 2017 (heavy - others)" in overall:
        e, l = overall["difference at 2017 (heavy - others)"], overall[f"difference at {last} (heavy - others)"]
        ie, il = overall["95% interval at 2017"], overall[f"95% interval at {last}"]
        if e < 0 and l > 0 and ie[1] < 0 and il[0] > 0:
            verdict = "supported"
        elif e < 0 and l > 0:
            verdict = "in the predicted direction, not separated from zero"
        else:
            verdict = "not supported"
    med = lambda sel, k: mc.quantiles([by_fall[y].get(g["unitid"], {}).get(k) for g in sel
                                       for y in [READ_FALL] if by_fall[y].get(g["unitid"], {}).get(k) is not None])
    for u, g in have.items():
        g["unitid"] = u
    OUT_TEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_TEST.write_text(json.dumps({
        "test": "Item 17 (exploratory): crossing curves of heavy adjunct absorbers at equal wealth, 2014 frame",
        "written at (UTC)": now, "protocol": "channel selection protocol.md, Amendment 9",
        "frame": {"institutions in the 2014 frame": len(fr), "with a pool share at fall 2014": len(have),
                  "without (reported as their own group)": {
                      "institutions": len(fr) - len(have),
                      "closed": sum(1 for u, g in scored.items() if u not in have and g["closed"])},
                  "cells (control, wealth tercile): institutions and top-quarter cut": {
                      f"{c[0]}, {c[1]}": {"institutions": len(us), "cut": have[us[0]]["cell cut"]}
                      for c, us in sorted(cells.items(), key=lambda x: str(x[0]))}},
        "header files read": hd_files,
        "verdict (overall)": verdict, "overall": overall,
        "by control": {c: block([g for g in groups if g["control"] == c])
                       for c in ("public", "private nonprofit", "for-profit")},
        "descriptive, fall 2014 (heavy against others)": {
            k: {"heavy": med([g for g in groups if g["heavy"]], k), "others": med([g for g in groups if not g["heavy"]], k)}
            for k in keys},
        "note": ("Exploratory: the outcomes are already known in aggregate. A disappearance can include a campus "
                 "folded into another report. The prediction is tested blind with the HD2026 retest.")},
        indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "overall": {k: v for k, v in overall.items() if "by year" not in k}}, indent=1))


if __name__ == "__main__":
    main()
