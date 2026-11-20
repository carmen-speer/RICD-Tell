"""
v4 channel selection: the gap values ("channel selection protocol.md",
section 3 and section 6; RICD 17.7, Spine §15.2.1, Definitions 15.2.2 to
15.2.13).

Reads only what step 1 committed (data/v4 channels/inputs.csv,
"completion inputs.csv" and calibrations.json); downloads nothing and reads
no closure outcome. Writes:

  data/v4 channels/gap values by year.csv
      the price gap for every institution and fiscal year 2009-2019, and the
      outcome and four-year gaps for every institution and completion file
      year, with every flag, the source of each input and the fit used
  data/v4 channels/gap values at scoring years.csv
      one row per institution and development frame (2014, 2019): the gaps
      as of that scoring year, taken only from inputs dated at or before it
      (price: fiscal year t; outcome: the newest Outcome Measures file of a
      year <= t, or, where none was yet collected, the Graduation Rates file
      of year t; four-year: the GR200 file of year t), with the available set
  data/v4 channels/gap values summary.json
      coverage and distributions by frame and sector (no outcome)

Definitions used:
  g_JS(x) = H2(1 - x/2) - H2(1 - x)/2                              (15.2.2)
  r_paid = (1 - delta_disc) / (1 - delta_need)
  delta_ex = max(0, 1 - r_paid);  D_price = g_JS(delta_ex)          (15.2.6)
  iota_price: price valid, need profile present, 1 - delta_need >= eta_pr
  C_low = C_rep; C_high = min(1, C_rep + tau_out), or 1 if tau_out is
      unreported (four-year frames: c_trn = 0)                       (15.2.9)
  Q*_ret = h_ret(Q_ret), the frozen isotonic fit for the source     (15.2.10)
  D_outcome = JS(C_low, Q*) if Q* < C_low (overclaiming), JS(C_high, Q*)
      if Q* > C_high (underclaiming), 0 inside the band              (15.2.11)
  D_4yr = g_JS(1 - r_on)                                             (15.2.13)

Usage (GitHub Actions, via v4_gap_values.yml; also runs locally, since it
needs no network):
    cd src
    python "v4 gap values.py"
"""

from __future__ import annotations

import csv
import datetime
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DIR = HERE.parent / "data" / "v4 channels"
FRAMES = (2014, 2019)
OM_FIRST = 2015


# ------------------------------------------------------------------ divergences
def h2(a: float) -> float:
    if a <= 0 or a >= 1:
        return 0.0
    return -a * math.log2(a) - (1 - a) * math.log2(1 - a)


def js(a: float, b: float) -> float:
    """Two-point Jensen-Shannon divergence, base 2 (Lemma 15.2.1)."""
    return max(0.0, h2((a + b) / 2) - h2(a) / 2 - h2(b) / 2)


def g_js(x: float) -> float:
    """The discount function (Definition 15.2.2)."""
    x = min(1.0, max(0.0, x))
    return max(0.0, h2(1 - x / 2) - h2(1 - x) / 2)


# ------------------------------------------------------------------ reading
def val(v):
    if v in (None, "", "None"):
        return None
    if v in ("True", "False"):
        return v == "True"
    try:
        return float(v)
    except ValueError:
        return v


def logistic(b, x):
    z = b[0] + sum(bi * xi for bi, xi in zip(b[1:], x))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def dummies(control: str) -> list[float]:
    return [1.0 if control == "private nonprofit" else 0.0, 1.0 if control == "for-profit" else 0.0]


def load():
    cal = json.loads((DIR / "calibrations.json").read_text(encoding="utf-8"))
    price, meta = {}, {}
    with open(DIR / "inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            u, f = r["unitid"], int(r["fiscal year"])
            meta[u] = {"name": r["name"], "control": r["control"],
                       2014: r["in 2014 frame"] == "True", 2019: r["in 2019 frame"] == "True"}
            rec = {k: val(v) for k, v in r.items()}
            rec["income bands"] = json.loads(r["income bands"]) if r["income bands"] not in ("", "None") else None
            price[(u, f)] = rec
    comp = {}
    with open(DIR / "completion inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            comp.setdefault((r["unitid"], int(r["file year"])), {})[r["source"]] = {k: val(v) for k, v in r.items()}
    return cal, price, comp, meta


# ------------------------------------------------------------------ the gaps
def price_gap(rec: dict, control: str, cal: dict, eta: float) -> dict:
    out = {"fiscal year": rec["fiscal year"], "finance form": rec["finance form"], "r_raw": rec["r_raw"],
           "price flag": rec["price flag"] or "", "graduate FTE share": rec["graduate FTE share"],
           "residence year": rec.get("residence year"), "delta_disc": rec["delta_disc"],
           "delta_need": None, "need fit": None, "delta_ex": None, "D_price": None, "iota_price": 0, "price reason": ""}
    if not rec["price valid"] or rec["delta_disc"] is None:
        out["price reason"] = rec["price flag"] or "price inputs missing"
        return out
    nd = cal["delta_need"]
    if rec["income bands"] is not None:
        out["need fit"] = f"income bands ({rec.get('income band field') or 'field not recorded'})"
        out["delta_need"] = logistic(nd["income bands"]["coefficients"], rec["income bands"][:4] + dummies(control))
    elif rec["Pell share"] is not None:
        out["need fit"] = "Pell share"
        out["delta_need"] = logistic(nd["Pell share"]["coefficients"], [rec["Pell share"]] + dummies(control))
    else:
        out["price reason"] = "no need profile (neither income bands nor Pell share)"
        return out
    if 1 - out["delta_need"] < eta:
        out["price reason"] = f"1 - delta_need below the floor {eta}"
        return out
    r_paid = (1 - rec["delta_disc"]) / (1 - out["delta_need"])
    out["delta_ex"] = max(0.0, 1 - r_paid)
    out["D_price"] = g_js(out["delta_ex"])
    out["iota_price"] = 1
    return out


def h_ret(cal: dict, source: str, q: float) -> float:
    f = cal["h_ret"][source]
    return float(np.interp(q, f["breakpoints (retention)"], f["values (calibrated completion)"]))


def outcome_gap(e: dict | None, source: str, cal: dict) -> dict:
    out = {"outcome source": source, "outcome file year": None, "entering cohort": None, "C_rep": None,
           "tau_out": None, "tau_out reported": None, "C_low": None, "C_high": None, "Q_ret": None,
           "Q*_ret": None, "D_outcome_ret": None, "D_over": None, "D_under": None, "iota_outcome_ret": 0,
           "outcome reason": ""}
    if e is None:
        out["outcome reason"] = f"no {source} completion record"
        return out
    out["outcome file year"], out["entering cohort"] = int(e["file year"]), int(e["entering cohort"])
    c, tau, q = e["C_rep"], e["tau_out"], e["Q_ret"]
    out["C_rep"], out["tau_out"], out["Q_ret"] = c, tau, q
    out["tau_out reported"] = tau is not None
    if c is None or q is None:
        out["outcome reason"] = "retention of the same cohort missing" if q is None else "completion missing"
        return out
    c = min(1.0, max(0.0, c))
    lo, hi = c, (min(1.0, c + tau) if tau is not None else 1.0)
    qs = h_ret(cal, source, q)
    d = js(lo, qs) if qs < lo else (js(hi, qs) if qs > hi else 0.0)
    out.update({"C_low": lo, "C_high": hi, "Q*_ret": qs, "D_outcome_ret": d,
                "D_over": d if qs < lo else 0.0, "D_under": d if qs > hi else 0.0, "iota_outcome_ret": 1})
    return out


def four_year_gap(e: dict | None) -> dict:
    out = {"4yr file year": None, "r_on": None, "D_4yr": None, "iota_4yr": 0,
           "program length check": "not built (no IPEDS field states program length)", "4yr reason": ""}
    if e is None or e.get("r_on") is None:
        out["4yr reason"] = "no GR200 record with BANC150 > 0"
        return out
    out["4yr file year"], out["r_on"] = int(e["file year"]), e["r_on"]
    out["D_4yr"], out["iota_4yr"] = g_js(1 - e["r_on"]), 1
    return out


# ------------------------------------------------------------------ main
def summarize(rows: list[dict]) -> dict:
    out = {}
    for frame in FRAMES:
        fr = [r for r in rows if r["frame"] == frame]
        out[str(frame)] = {}
        for ctrl in ["all", "public", "private nonprofit", "for-profit"]:
            g = fr if ctrl == "all" else [r for r in fr if r["control"] == ctrl]
            s = {"institutions": len(g)}
            for d, i in (("D_price", "iota_price"), ("D_outcome_ret", "iota_outcome_ret"), ("D_over", "iota_outcome_ret"),
                         ("D_under", "iota_outcome_ret"), ("D_4yr", "iota_4yr")):
                v = [r[d] for r in g if r[i] == 1]
                s[d] = {"available": len(v)} | ({"mean": float(np.mean(v)), "median": float(np.median(v)),
                                                  "90th percentile": float(np.percentile(v, 90)),
                                                  "share above 0": float(np.mean(np.array(v) > 0))} if v else {})
            s["all three available"] = sum(1 for r in g if r["iota_price"] and r["iota_outcome_ret"] and r["iota_4yr"])
            s["none available"] = sum(1 for r in g if not (r["iota_price"] or r["iota_outcome_ret"] or r["iota_4yr"]))
            s["price ratio above 1 (kept, flagged)"] = sum(1 for r in g if "above 1" in (r["price flag"] or ""))
            s["outcome source"] = {src: sum(1 for r in g if r["outcome source"] == src and r["iota_outcome_ret"]) for src in ("OM", "GR")}
            s["tau_out reported (of outcome available)"] = sum(1 for r in g if r["iota_outcome_ret"] and r["tau_out reported"])
            out[str(frame)][ctrl] = s
    return out


def main() -> None:
    cal, price, comp, meta = load()
    eta = cal["rules"]["eta_pr"]
    by_year = []
    for (u, f), rec in sorted(price.items()):
        by_year.append({"unitid": u, "kind": "price", "year": f} | price_gap(rec, meta[u]["control"], cal, eta))
    for (u, y), srcs in sorted(comp.items()):
        for src in ("OM", "GR"):
            if src in srcs:
                by_year.append({"unitid": u, "kind": f"outcome ({src})", "year": y} | outcome_gap(srcs[src], src, cal))
        if "GR200" in srcs:
            by_year.append({"unitid": u, "kind": "four-year", "year": y} | four_year_gap(srcs["GR200"]))
    at = []
    for t in FRAMES:
        om_files = [y for y in range(OM_FIRST, t + 1)]
        for u, m in sorted(meta.items()):
            if not m[t]:
                continue
            row = {"unitid": u, "name": m["name"], "control": m["control"], "frame": t}
            p = price.get((u, t))
            row |= price_gap(p, m["control"], cal, eta) if p else price_gap(
                {"fiscal year": t, "finance form": None, "r_raw": None, "price flag": "no inputs row", "graduate FTE share": None,
                 "price valid": False, "delta_disc": None}, m["control"], cal, eta)
            if om_files:
                y = max(om_files)
                row |= outcome_gap(comp.get((u, y), {}).get("OM"), "OM", cal)
            else:
                row |= outcome_gap(comp.get((u, t), {}).get("GR"), "GR", cal)
            row |= four_year_gap(comp.get((u, t), {}).get("GR200"))
            row["available set"] = "+".join(n for n, i in (("price", "iota_price"), ("outcome", "iota_outcome_ret"),
                                                            ("4yr", "iota_4yr")) if row[i]) or "none"
            at.append(row)
    for name, rows in (("gap values by year.csv", by_year), ("gap values at scoring years.csv", at)):
        cols = list(dict.fromkeys(k for r in rows for k in r))
        with open(DIR / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    summary = summarize(at)
    (DIR / "gap values summary.json").write_text(json.dumps({
        "note": "v4 channel selection: gap values from the frozen step 1 calibrations (channel selection protocol.md). "
                "No closure outcome was read.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "calibrations written at (UTC)": cal.get("written at (UTC)"),
        "scoring-year rule": "price: fiscal year t; outcome: newest Outcome Measures file of a year <= t, or the "
                             "Graduation Rates file of year t where no Outcome Measures file was yet collected; four-year: GR200 file of year t",
        "open item": "the program-length check of Definition 15.2.13 is not built: no IPEDS field states a college's "
                     "standard bachelor's length, so no college is yet marked unavailable or flagged for longer programs",
        "by frame and control": summary}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
