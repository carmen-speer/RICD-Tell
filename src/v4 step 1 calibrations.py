"""
v4 channel selection, step 1: the inputs and the calibrations
("channel selection protocol.md", sections 2 and 3; RICD 17.7, Spine
§15.2.1, Definitions 15.2.4 to 15.2.13).

No closure outcome is read here. This step:

1. Builds the development frames: every four-year, degree-granting
   institution (SECTOR 1, 2 or 3; DEGGRANT 1) in HD2014 and in HD2019.
2. Reads, for every institution in either frame and every fiscal year
   2009-2019, the inputs of the three gaps, from the fields confirmed by
   the field check:
     price      IC_AY (TUITION2+FEE2, TUITION3+FEE3), EF C residence of
                first-time students (EFRES01 by EFCSTATE, against the
                institution's own state), finance net tuition (F1A F1B01,
                F2 F2D01, F3 F3D01), 12-month FTE (EFIA FTEUG+FTEGD+FTEDPP)
     need       SFA income bands (GIS4N12..GIS4N52 over GIS4N2) and the
                Pell share (PGRNT_P)
     outcome    Outcome Measures at eight years (OMAWDP8, OMENRAP) for the
                first-time, full-time cohort where released; otherwise the
                Graduation Rates file (bachelor's subcohort completers
                within 150% and transfer-outs, over the adjusted
                subcohort); retention of the same entering cohort (EF D
                RET_PCF of the year after entry)
     four-year  GR200 BANC100 and BANC150
   Fiscal year f reads IC{f-1}_AY, EF{f-1}C, F{f-1}{f}, SFA{f-1}{f} and
   EFIA{f}. Completion files are indexed by their own file year.
3. Fits and freezes the calibrations:
     delta_need  fractional logit of the clipped discount rate on the
                 income-band shares plus control (and a separate Pell-share
                 fit), on fiscal years <= 2013, validated on 2014-2018
     h_ret       isotonic (nondecreasing) fit of C_low on retention, per
                 completion source: Graduation Rates on files <= 2013,
                 validated on 2014-2018; Outcome Measures on 2015-2016,
                 validated on 2017-2018
4. Writes data/v4 channels/inputs.csv (every institution-year input, with
   flags and sources) and data/v4 channels/calibrations.json (the frozen
   fits and their diagnostics).

Codes whose meaning is read from labels (GRTYPE, OM cohort) are resolved
from each year's dictionary at run time; a code that cannot be resolved
makes that file unavailable for that year, recorded, never guessed.

Usage (GitHub Actions only, via v4_step1_calibrations.yml):
    cd src
    python "v4 step 1 calibrations.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import io
import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression

import meta_channel as mc
import v2_training_outcomes as coding

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "data" / "v4 channels"
FISCAL = range(2009, 2020)
COMPLETION_FILES = range(2008, 2020)
FIT_LAST, VAL = 2013, range(2014, 2019)
OM_FIT, OM_VAL = (2015, 2016), (2017, 2018)
R_LO, R_HI, ETA_PR = 0.05, 1.10, 0.05
MIN_ROWS = 1500
CONTROL = {"1": "public", "2": "private nonprofit", "3": "for-profit"}

_spec = importlib.util.spec_from_file_location("fieldcheck", HERE / "v4 field check.py")
fieldcheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fieldcheck)


# ------------------------------------------------------------------ reading
def num(v):
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def table(name: str) -> dict[str, list[dict]] | None:
    """Rows of an IPEDS table by UNITID (a list, since some tables have several rows per institution)."""
    got = mc.fetch(f"{name}.zip", False)
    if got is None:
        return None
    _, text = mc.first_csv(got[0])
    out: dict[str, list[dict]] = {}
    for r in mc.rows(text):
        u = r.get("UNITID", "")
        if u:
            out.setdefault(u, []).append(r)
    return out


def labels(name: str, var: str) -> dict[str, str]:
    """Code -> label for one variable, from the table's dictionary (xlsx or xls)."""
    got = mc.fetch(f"{name}_Dict.zip", False)
    if got is None:
        return {}
    rows, _ = fieldcheck.dictionary_rows(got[0])
    out = {}
    for r in rows:
        # frequency-sheet rows read: varnumber | VARNAME | code | label | frequency | percent
        for i, c in enumerate(r[:-2]):
            if c.strip().upper() == var:
                code = r[i + 1].strip()
                code = code[:-2] if code.endswith(".0") else code
                if re.fullmatch(r"-?\d+", code) and r[i + 2].strip():
                    out[code] = r[i + 2].strip()
                break
    return out


def find_code(lab: dict[str, str], *patterns: str, exclude: tuple[str, ...] = ()) -> str | None:
    """The one code whose label matches every pattern and no exclusion; None if zero or several match."""
    hits = [c for c, l in lab.items()
            if all(re.search(p, l, re.I) for p in patterns) and not any(re.search(x, l, re.I) for x in exclude)]
    return hits[0] if len(hits) == 1 else None


def fips(v) -> str:
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        return ""


_RES: dict[int, dict | None] = {}
_RET: dict[int, dict | None] = {}


def residence_file(y: int) -> dict | None:
    """EF{y}C reduced to UNITID -> {state code: first-time count}, kept in memory for carry-forward."""
    if y not in _RES:
        t = table(f"EF{y}C")
        _RES[y] = None if t is None else {u: {fips(x.get("EFCSTATE")): num(x.get("EFRES01")) for x in rows}
                                          for u, rows in t.items()}
    return _RES[y]


def residence(u: str, year: int, state: str):
    """In-state share of first-time students from the most recent EF C collection at or before year (protocol: carried forward)."""
    for y in range(year, year - 4, -1):
        by = (residence_file(y) or {}).get(u)
        if not by:
            continue
        total, mine = by.get("99"), by.get(state)
        if total and total > 0 and mine is not None:
            return mine / total, y
    return None, None


# ------------------------------------------------------------------ frames
def frame(year: int) -> dict[str, dict]:
    hd = coding.download_hd(year)
    out = {}
    for r in mc.rows(hd["csv"]):
        if r.get("SECTOR") in ("1", "2", "3") and r.get("DEGGRANT") == "1":
            out[r["UNITID"]] = {"control": CONTROL.get(r.get("CONTROL", ""), "unknown"),
                                "state": fips(r.get("FIPS")), "name": r.get("INSTNM", "")}
    if len(out) < MIN_ROWS:
        raise SystemExit(f"HD{year} yielded {len(out)} four-year institutions; misread. Nothing recorded.")
    return out


# ------------------------------------------------------------------ inputs by fiscal year
def fiscal_inputs(f: int, ids: set[str], states: dict[str, str], ctrl: dict[str, str]) -> tuple[dict, dict]:
    a, b = (f - 1) % 100, f % 100
    log = {}
    ic = table(f"IC{f-1}_AY")
    efc = residence_file(f - 1)
    efia = table(f"EFIA{f}")
    fin = {form: table(f"F{a:02d}{b:02d}_{form}") for form in ("F1A", "F2", "F3")}
    sfa = table(f"SFA{a:02d}{b:02d}")
    for k, v in (("IC_AY", ic), ("EF_C", efc), ("EFIA", efia), ("SFA", sfa), *((f"F_{x}", y) for x, y in fin.items())):
        log[k] = "missing" if v is None else len(v)
    net_field = {"F1A": "F1B01", "F2": "F2D01", "F3": "F3D01"}
    out = {}
    for u in ids:
        rec = {}
        r = (ic or {}).get(u, [{}])[0]
        ins = [num(r.get("TUITION2")), num(r.get("FEE2"))]
        oos = [num(r.get("TUITION3")), num(r.get("FEE3"))]
        p_in = sum(x for x in ins if x is not None) if ins[0] is not None else None
        p_out = sum(x for x in oos if x is not None) if oos[0] is not None else None
        w, w_year = residence(u, f - 1, states.get(u, ""))
        rec["published in-state"], rec["published out-of-state"], rec["in-state share"] = p_in, p_out, w
        rec["residence year"] = w_year
        if p_in is not None and p_out is not None and w is not None:
            rec["S_post"] = w * p_in + (1 - w) * p_out
        elif p_in is not None and (p_out is None or p_out == p_in):
            rec["S_post"] = p_in
        else:
            rec["S_post"] = None
        net, form = None, None
        for fm in ("F1A", "F2", "F3"):
            row = (fin[fm] or {}).get(u)
            if row and num(row[0].get(net_field[fm])) is not None:
                net, form = num(row[0].get(net_field[fm])), fm
                break
        er = (efia or {}).get(u, [{}])[0]
        fte_ug, fte_gd, fte_dp = num(er.get("FTEUG")), num(er.get("FTEGD")) or 0, num(er.get("FTEDPP")) or 0
        fte = (fte_ug + fte_gd + fte_dp) if fte_ug else None
        rec["finance form"], rec["net tuition"], rec["FTE"] = form, net, fte
        rec["graduate FTE share"] = ((fte_gd + fte_dp) / fte) if fte else None
        rec["N_net"] = (net / fte) if (net is not None and fte) else None
        if rec["S_post"] and rec["S_post"] > 0 and rec["N_net"] is not None:
            rr = rec["N_net"] / rec["S_post"]
            rec["r_raw"] = rr
            rec["price valid"] = R_LO <= rr <= R_HI
            rec["price flag"] = ("r_raw above 1, kept and flagged" if rec["price valid"] and rr > 1
                                 else ("r_raw outside [0.05, 1.10]: price unavailable" if not rec["price valid"] else ""))
            rec["delta_disc"] = min(1.0, max(0.0, 1 - rr))
        else:
            rec["r_raw"], rec["price valid"], rec["price flag"], rec["delta_disc"] = None, False, "price inputs missing", None
        s = (sfa or {}).get(u, [{}])[0]
        # Amendment 1 (November 20): public colleges report the bands for in-state aid recipients (GIS4...),
        # private nonprofit and for-profit colleges for all aid recipients (GRN4...)
        pre = "GIS4" if ctrl.get(u) == "public" else "GRN4"
        tot = num(s.get(f"{pre}N2"))
        bands = [num(s.get(f"{pre}N{k}2")) for k in range(1, 6)]
        ok = bool(tot and tot > 0 and all(b is not None for b in bands))
        rec["income bands"] = [b / tot for b in bands] if ok else None
        rec["income band field"] = pre if ok else None
        pell = num(s.get("PGRNT_P"))
        rec["Pell share"] = pell / 100 if pell is not None else None
        out[u] = rec
    return out, log


def completion_inputs(ids: set[str]) -> tuple[dict, dict]:
    """By completion-file year Y: the outcome band inputs, the four-year inputs, and retention of the same cohort."""
    out, log = {}, {}
    def retention(cohort: int, u: str):
        y = cohort + 1
        if y not in _RET:
            t = table(f"EF{y}D")
            _RET[y] = None if t is None else {k: num(v[0].get("RET_PCF")) for k, v in t.items()}
        v = (_RET[y] or {}).get(u)
        return v / 100 if v is not None else None

    for Y in COMPLETION_FILES:
        yy = Y % 100
        entry = {}
        # Outcome Measures, eight-year status point, first-time full-time cohort
        om = table(f"OM{Y}") if Y >= 2015 else None
        om_code = None
        if om is not None:
            ex = (r"non-first", r"not first", r"pell", r"part-time")
            om_code = find_code(labels(f"OM{Y}", "OMCHRT"), r"first-time", r"full-time", exclude=ex) or \
                      find_code(labels(f"OM{Y}", "OMRCHRT"), r"first-time", r"full-time", exclude=ex)
        # Graduation Rates, bachelor's subcohort
        gr = table(f"GR{Y}")
        gl = labels(f"GR{Y}", "GRTYPE") if gr is not None else {}
        g_adj = find_code(gl, r"bachelor", r"adjusted cohort")
        g_cmp = find_code(gl, r"bachelor", r"completers within 150% of normal time", r"total")
        g_trn = find_code(gl, r"bachelor", r"transfer.?out")
        g200 = table(f"GR200_{yy:02d}")
        log[str(Y)] = {"OM": "missing" if om is None else (f"cohort code {om_code}" if om_code else "cohort code unresolved"),
                       "GR": "missing" if gr is None else {"adjusted": g_adj, "completers 150%": g_cmp, "transfer-out": g_trn},
                       "GR200": "missing" if g200 is None else len(g200)}
        for u in ids:
            rec = {}
            if om is not None and om_code:
                row = next((r for r in om.get(u, []) if r.get("OMCHRT", r.get("OMRCHRT")) == om_code), None)
                if row:
                    aw, ea = num(row.get("OMAWDP8")), num(row.get("OMENRAP"))
                    if aw is not None:
                        rec["OM"] = {"cohort": Y - 8, "C_rep": aw / 100, "tau_out": ea / 100 if ea is not None else None,
                                     "Q_ret": retention(Y - 8, u)}
            if gr is not None and g_adj and g_cmp:
                rows = {r.get("GRTYPE"): r for r in gr.get(u, [])}
                adj = num(rows.get(g_adj, {}).get("GRTOTLT"))
                cmpl = num(rows.get(g_cmp, {}).get("GRTOTLT"))
                trn = num(rows.get(g_trn, {}).get("GRTOTLT")) if g_trn else None
                if adj and adj > 0 and cmpl is not None:
                    rec["GR"] = {"cohort": Y - 6, "C_rep": cmpl / adj, "tau_out": (trn / adj) if trn is not None else None,
                                 "Q_ret": retention(Y - 6, u)}
            if g200 is not None:
                r = g200.get(u, [{}])[0]
                n100, n150 = num(r.get("BANC100")), num(r.get("BANC150"))
                if n150 and n150 > 0 and n100 is not None:
                    rec["4yr"] = {"cohort": Y - 8, "r_on": min(1.0, n100 / n150)}
            if rec:
                entry[u] = rec
        out[Y] = entry
    return out, log


# ------------------------------------------------------------------ calibrations
def c_low(c_rep: float, tau: float | None) -> float:
    return c_rep   # development frames are four-year: c_trn = 0, so C_low = C_rep (Definition 15.2.9)


def frac_logit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    X1 = np.column_stack([np.ones(len(X)), X])

    def nll(b):
        z = X1 @ b
        p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        p = np.clip(p, 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)) + 1e-6 * np.sum(b[1:] ** 2)
    return minimize(nll, np.zeros(X1.shape[1]), method="BFGS").x


def predict(b: np.ndarray, X: np.ndarray) -> np.ndarray:
    z = np.column_stack([np.ones(len(X)), X]) @ b
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def control_dummies(c: str) -> list[float]:
    return [1.0 if c == "private nonprofit" else 0.0, 1.0 if c == "for-profit" else 0.0]


def diagnostics(obs, pred, groups) -> dict:
    obs, pred = np.asarray(obs), np.asarray(pred)
    out = {}
    for g in ["all"] + sorted(set(groups)):
        m = np.ones(len(obs), bool) if g == "all" else np.array([x == g for x in groups])
        if m.sum() < 5:
            out[g] = {"n": int(m.sum())}
            continue
        o, p = obs[m], pred[m]
        slope = float(np.polyfit(p, o, 1)[0]) if np.std(p) > 0 else None
        out[g] = {"n": int(m.sum()), "mean observed": float(o.mean()), "mean predicted": float(p.mean()),
                  "mean absolute error": float(np.abs(o - p).mean()), "calibration slope": slope}
    return out


def fit_need(fis: dict, ctrl: dict) -> dict:
    res = {}
    for kind in ("income bands", "Pell share"):
        def rows(years):
            X, y, g = [], [], []
            for f in years:
                for u, r in fis.get(f, {}).items():
                    if not r.get("price valid") or r.get("delta_disc") is None:
                        continue
                    v = r.get(kind)
                    if v is None:
                        continue
                    feats = (v[:4] if kind == "income bands" else [v]) + control_dummies(ctrl[u])
                    X.append(feats), y.append(r["delta_disc"]), g.append(ctrl[u])
            return np.array(X, float), np.array(y, float), g
        Xf, yf, gf = rows([f for f in FISCAL if f <= FIT_LAST])
        Xv, yv, gv = rows(list(VAL))
        if len(yf) < 200:
            raise SystemExit(f"delta_need ({kind}): only {len(yf)} fitting rows; inputs misread. Nothing recorded.")
        b = frac_logit(Xf, yf)
        res[kind] = {"coefficients": b.tolist(),
                     "features": ["intercept"] + (["share 0-30k", "share 30-48k", "share 48-75k", "share 75-110k"]
                                                  if kind == "income bands" else ["Pell share"]) + ["private nonprofit", "for-profit"],
                     "fit rows (fiscal <= 2013)": int(len(yf)), "validation rows (fiscal 2014-2018)": int(len(yv)),
                     "fit diagnostics": diagnostics(yf, predict(b, Xf), gf),
                     "validation diagnostics": diagnostics(yv, predict(b, Xv), gv) if len(yv) else {}}
    return res


def fit_ret(comp: dict, ctrl: dict) -> dict:
    res = {}
    for src, fit_years, val_years in (("GR", [y for y in COMPLETION_FILES if y <= FIT_LAST], list(VAL)),
                                      ("OM", list(OM_FIT), list(OM_VAL))):
        def rows(years):
            x, y, g = [], [], []
            for Y in years:
                for u, rec in comp.get(Y, {}).items():
                    e = rec.get(src)
                    if e and e["Q_ret"] is not None:
                        x.append(e["Q_ret"]), y.append(c_low(e["C_rep"], e["tau_out"])), g.append(ctrl[u])
            return np.array(x), np.array(y), g
        xf, yf, gf = rows(fit_years)
        xv, yv, gv = rows(val_years)
        if len(yf) < 200:
            raise SystemExit(f"h_ret ({src}): only {len(yf)} fitting rows; inputs misread. Nothing recorded.")
        iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip").fit(xf, yf)
        res[src] = {"breakpoints (retention)": iso.X_thresholds_.tolist(), "values (calibrated completion)": iso.y_thresholds_.tolist(),
                    "fit files": fit_years, "validation files": val_years,
                    "fit rows": int(len(yf)), "validation rows": int(len(yv)),
                    "fit diagnostics": diagnostics(yf, iso.predict(xf), gf),
                    "validation diagnostics": diagnostics(yv, iso.predict(xv), gv) if len(yv) else {}}
    return res


# ------------------------------------------------------------------ main
def main() -> None:
    f14, f19 = frame(2014), frame(2019)
    ids = set(f14) | set(f19)
    meta = {**f19, **f14}
    ctrl = {u: meta[u]["control"] for u in ids}
    states = {u: meta[u]["state"] for u in ids}
    fis, logs = {}, {}
    for f in FISCAL:
        fis[f], logs[f"fiscal {f}"] = fiscal_inputs(f, ids, states, ctrl)
        print("fiscal", f, logs[f"fiscal {f}"], flush=True)
    comp, comp_log = completion_inputs(ids)
    print("completion files", json.dumps(comp_log, indent=1), flush=True)
    need = fit_need(fis, ctrl)
    ret = fit_ret(comp, ctrl)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["unitid", "name", "control", "in 2014 frame", "in 2019 frame", "fiscal year", "published in-state",
            "published out-of-state", "in-state share", "residence year", "S_post", "finance form", "net tuition", "FTE",
            "graduate FTE share", "N_net", "r_raw", "price valid", "price flag", "delta_disc", "income bands",
            "income band field", "Pell share"]
    with open(OUT_DIR / "inputs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for f in FISCAL:
            for u in sorted(fis[f]):
                r = fis[f][u]
                w.writerow([u, meta[u]["name"], ctrl[u], u in f14, u in f19, f] +
                           [json.dumps(r[c]) if isinstance(r[c], list) else r[c] for c in cols[6:]])
    with open(OUT_DIR / "completion inputs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["unitid", "file year", "source", "entering cohort", "C_rep", "tau_out", "Q_ret", "r_on"])
        for Y in COMPLETION_FILES:
            for u in sorted(comp[Y]):
                rec = comp[Y][u]
                for src in ("OM", "GR"):
                    if src in rec:
                        e = rec[src]
                        w.writerow([u, Y, src, e["cohort"], e["C_rep"], e["tau_out"], e["Q_ret"], ""])
                if "4yr" in rec:
                    w.writerow([u, Y, "GR200", rec["4yr"]["cohort"], "", "", "", rec["4yr"]["r_on"]])
    (OUT_DIR / "calibrations.json").write_text(json.dumps({
        "note": "v4 channel selection, step 1 (channel selection protocol.md): inputs and frozen calibrations. "
                "No closure outcome was read.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "frames": {"2014": len(f14), "2019": len(f19), "union": len(ids)},
        "rules": {"r_lo": R_LO, "r_hi": R_HI, "eta_pr": ETA_PR, "fit fiscal years": f"<= {FIT_LAST}",
                  "validation fiscal years": f"{VAL.start}-{VAL.stop - 1}"},
        "delta_need": need, "h_ret": ret,
        "files read": {"fiscal": logs, "completion": comp_log},
    }, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if "diagnostics" not in kk} for k, v in need.items()}, indent=1))
    print("Wrote", OUT_DIR)


if __name__ == "__main__":
    main()
