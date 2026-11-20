"""
v4 soundness dimension: selection stages ("channel selection protocol.md",
Amendment 6), with the settings of Amendments 2 and 4.

    --stage 12   stages 1 and 2 on the 2014 frame (HD2014..HD2019 outcomes)
    --stage 3    stage 3 on the 2019 frame (HD2019 onward), only after the
                 stage 1 and 2 result is committed

Readings: coverage alone (D_op_sound), exit alone (D_om_sound); combined by
the maximum of the carried readings, and as separate features (with D_pm_sound
when both are carried). Baseline: log FTE and control; out-of-fold AUC
(stratified 10-fold, seed 20261120); paired bootstrap (2,000, seed 20261121).

Outputs: data/v4 channels/"soundness selection stages 1 and 2.json" and
"soundness selection stage 3.json".

Usage (GitHub Actions only, via v4_soundness_selection.yml):
    cd src
    python "v4 soundness selection.py" --stage 12
"""

from __future__ import annotations

import argparse
import csv
import datetime
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
_a = importlib.util.spec_from_file_location("stages", HERE / "v4 selection stages 1 and 2.py")
st = importlib.util.module_from_spec(_a)
_a.loader.exec_module(st)
_b = importlib.util.spec_from_file_location("stage3", HERE / "v4 selection stage 3.py")
s3 = importlib.util.module_from_spec(_b)
_b.loader.exec_module(s3)

READINGS = {"coverage": ("D_op_sound", "iota_sound"), "exit": ("D_om_sound", "meta available")}


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load(frame: int) -> list[dict]:
    fte = {}
    with open(st.DIR / "inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["fiscal year"]) == frame and f(r["FTE"]):
                fte[r["unitid"]] = f(r["FTE"])
    rows = []
    with open(st.DIR / "soundness values at scoring years.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["frame"]) != frame:
                continue
            rec = {"unitid": r["unitid"], "name": r["name"], "control": r["control"],
                   "log FTE": math.log(fte[r["unitid"]]) if fte.get(r["unitid"], 0) > 0 else None}
            for k in ("D_op_sound", "D_om_sound", "D_pm_sound"):
                rec[k] = f(r.get(k))
            rec["iota_sound"] = r.get("iota_sound") in ("1", "1.0")
            rec["meta available"] = r.get("meta available") in ("1", "1.0")
            rows.append(rec)
    return rows


def combos(cov: list[dict], carried: list[str], against_feats, against_label) -> dict:
    for r in cov:
        r["D_max"] = max(r[READINGS[d][0]] for d in carried)
    sep = [READINGS[d][0] for d in carried] + (["D_pm_sound"] if len(carried) == 2 else [])
    return {"combined by the maximum": st.compare(cov, against_feats, ["D_max"], against_label, "size, sector and the maximum"),
            "separate features": st.compare(cov, against_feats, sep, against_label, "size, sector and the separate readings")}


def available(r, carried) -> bool:
    return all(r[READINGS[d][1]] for d in carried) and (len(carried) < 2 or r["D_pm_sound"] is not None)


def stage12() -> dict:
    st.FRAME = 2014
    rows = load(2014)
    out, files = st.outcomes([r["unitid"] for r in rows])
    for r in rows:
        r["closed"] = bool(out[r["unitid"]]["closed or failed (primary)"])
    base = [r for r in rows if r["log FTE"] is not None]
    s1 = {}
    for d, (feat, iota) in READINGS.items():
        cov = [r for r in base if r[iota]]
        s1[d] = st.compare(cov, [], [feat], "size and sector", f"size, sector and {d}")
        s1[d]["coverage"] = st.describe(cov, [r for r in base if not r[iota]])
    ranked = sorted((d for d in s1 if "gain" in s1[d]), key=lambda d: -s1[d]["gain"])
    carried = [d for d in ranked if s1[d]["gain"] > 0][:3]
    s2 = {"carried (Decision B)": carried}
    if carried:
        cov = [r for r in base if available(r, carried)]
        s2 |= combos(cov, carried, [], "size and sector")
        s2["coverage"] = st.describe(cov, [r for r in base if r not in cov])
    return {"protocol": "channel selection protocol.md, Amendment 6: soundness stages 1 and 2 (2014 frame)",
            "frame": 2014, "header files": files, "institutions with size": len(base),
            "closures": sum(r["closed"] for r in base), "stage 1": s1, "ranking by gain": ranked, "stage 2": s2}


def stage3() -> dict:
    prior = json.loads((st.DIR / "soundness selection stages 1 and 2.json").read_text(encoding="utf-8"))
    carried = prior["stage 2"]["carried (Decision B)"]
    rows = load(2019)
    out, files, nf = s3.outcomes_2019([r["unitid"] for r in rows])
    for r in rows:
        r["closed"] = bool(out[r["unitid"]]["closed or failed (primary)"])
    base = [r for r in rows if r["log FTE"] is not None]
    res = {"protocol": "channel selection protocol.md, Amendment 6: soundness stage 3 (2019 frame)", "frame": 2019,
           "header files": files, "header files not yet released": nf, "carried": carried,
           "institutions with size": len(base), "closures": sum(r["closed"] for r in base),
           "note": "Selection-stage performance, used only to choose; never an estimate of v4's accuracy."}
    if not carried:
        res["verdict"] = "nothing carried; the soundness dimension does not enter v4"
        return res
    cov = [r for r in base if available(r, carried)]
    enters = {}
    for d in carried:
        g = st.compare(cov, [], [READINGS[d][0]], "size and sector", f"size, sector and {d}")
        res[f"{d} against size and sector"] = g
        enters[d] = g.get("gain 95% bootstrap", [0])[0] > 0
    best = carried[0]
    if len(carried) >= 2:
        c = combos(cov, carried, [READINGS[best][0]], f"size, sector and {best}")
        res["(2) maximum against (1) best single"] = c["combined by the maximum"]
        res["(3) separate features against (1) best single"] = c["separate features"]
        lo2, lo3 = c["combined by the maximum"]["gain 95% bootstrap"][0], c["separate features"]["gain 95% bootstrap"][0]
        res["prediction (several parts beat one)"] = (
            "supported" if lo2 > 0 and lo3 > 0 else
            "in the predicted direction, not separated from zero"
            if c["combined by the maximum"]["gain"] > 0 and c["separate features"]["gain"] > 0 else "not supported")
    else:
        res["prediction (several parts beat one)"] = "not testable: only one reading was carried"
    res["coverage"] = st.describe(cov, [r for r in base if r not in cov])
    res["enters v4 (Amendment 4)"] = enters
    res["verdict"] = ("enter v4: " + ", ".join(d for d, v in enters.items() if v)) if any(enters.values()) else \
        "no soundness reading is confirmed; the dimension does not enter v4"
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["12", "3"], required=True)
    a = ap.parse_args()
    res = stage12() if a.stage == "12" else stage3()
    res["written at (UTC)"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    name = "soundness selection stages 1 and 2.json" if a.stage == "12" else "soundness selection stage 3.json"
    (st.DIR / name).write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("header files",)}, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
