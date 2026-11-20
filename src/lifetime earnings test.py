"""
Item 13: sector-level lifetime-earnings comparison of the professions and
the trades ("lifetime earnings protocol.md"). Separate from the closure
model: no closure outcome is read.

Reads three sources: the College Scorecard most recent cohorts
field-of-study file (national earnings 1, 5 and 7 years after completion by
4-digit CIP and credential level; program median debt), the BLS OEWS
national file for May 2024 (occupational wage median, 25th and 90th
percentiles, employment), and the NCES-BLS CIP 2020 to SOC 2018 crosswalk.
For each field and credential level it computes early position, the
occupational ladder, graduates' growth and payoff to cost, then compares the
trades with the professions on the three pre-registered predictions.

Outputs: data/item 13/lifetime earnings.json and
data/item 13/lifetime earnings test.json.

Usage (GitHub Actions only, via item13_lifetime_earnings.yml):
    cd src
    python "lifetime earnings test.py"
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import importlib.util
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "item 13"
OUT_UNITS = DATA / "lifetime earnings.json"
OUT_TEST = DATA / "lifetime earnings test.json"
_spec = importlib.util.spec_from_file_location("fc12", HERE / "v4 item 12 field check.py")
fc12 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc12)

FOS_FILE = "Most-Recent-Cohorts-Field-of-Study.csv"
OEWS_URL = "https://www.bls.gov/oes/special-requests/oesm24nat.zip"
OEWS_LOCAL = DATA / "oesm24nat.zip"
XWALK_URL = "https://nces.ed.gov/ipeds/cipcode/Files/CIP2020_SOC2018_Crosswalk.xlsx"
XWALK_LOCAL = DATA / "CIP2020_SOC2018_Crosswalk.xlsx"
TOPCODE = 239200.0          # BLS annual top code, May 2024 (technical notes)
UA = {"User-Agent": "RICD-Tell research (github.com/carmen-speer/RICD-Tell)",
      "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
TRADE_FAMILIES = {"12", "46", "47", "48", "49"}
SEED, BOOT = 20261125, 2000
MISSING = {"", "NULL", "PS", "PRIVACYSUPPRESSED", "NA"}


def num(v):
    v = (v or "").strip()
    if v.upper() in MISSING:
        return None
    try:
        return float(v.replace(",", ""))
    except ValueError:
        return None


def get(url: str, local: Path) -> tuple[bytes, str]:
    try:
        r = requests.get(url, headers=UA, timeout=300)
        if r.status_code == 200 and r.content[:2] == b"PK":
            return r.content, url
        note = f"HTTP {r.status_code}"
    except requests.RequestException as e:
        note = f"{type(e).__name__}"
    if local.exists():
        return local.read_bytes(), f"{local.relative_to(HERE.parent)} (committed by hand; {url} gave {note})"
    raise SystemExit(f"{url} gave {note}, and no hand-downloaded copy is at {local.relative_to(HERE.parent)}. "
                     "Download it once by hand, commit it there, and run again. Nothing recorded.")


def sheet_rows(content: bytes, want) -> list[dict]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    for ws in wb.worksheets:
        it = ws.iter_rows(values_only=True)
        for row in it:
            cells = [str(c).strip() if c is not None else "" for c in row]
            if want(cells):
                header = [c.upper() for c in cells]
                return [dict(zip(header, ["" if c is None else str(c).strip() for c in r])) for r in it]
    raise SystemExit("No sheet with the expected header was found. Nothing recorded.")


def crosswalk() -> tuple[dict, str]:
    content, src = get(XWALK_URL, XWALK_LOCAL)
    rows = sheet_rows(content, lambda c: any("CIP2020CODE" in x.upper() for x in c)
                      and any("SOC2018CODE" in x.upper() for x in c))
    ck = next(k for k in rows[0] if "CIP2020CODE" in k)
    sk = next(k for k in rows[0] if "SOC2018CODE" in k)
    links = defaultdict(set)
    for r in rows:
        cip, soc = r.get(ck, ""), r.get(sk, "")
        if not cip or not soc or soc.startswith("99-9999"):
            continue
        digits = cip.replace(".", "").zfill(6)
        links[digits[:4]].add(soc)
    return dict(links), src


def oews() -> tuple[dict, str]:
    content, src = get(OEWS_URL, OEWS_LOCAL)
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".xlsx") and "nat" in n.lower())
        rows = sheet_rows(zf.read(name), lambda c: "OCC_CODE" in [x.upper() for x in c])
    occ = {}
    for r in rows:
        if r.get("O_GROUP", "").lower() not in ("detailed", "detail"):
            continue
        vals, top = {}, []
        for k, out in (("A_MEDIAN", "median"), ("A_PCT25", "p25"), ("A_PCT90", "p90")):
            v = r.get(k, "")
            if v == "#":
                vals[out] = TOPCODE
                top.append(out)
            else:
                vals[out] = num(v)
        occ[r["OCC_CODE"]] = vals | {"employment": num(r.get("TOT_EMP")), "top-coded": top,
                                     "title": r.get("OCC_TITLE", "")}
    return occ, f"{src} ({name})"


def weighted_median(pairs):
    pairs = sorted((v, w) for v, w in pairs if v is not None and w and w > 0)
    if not pairs:
        return None
    tot, acc = sum(w for _, w in pairs), 0.0
    for v, w in pairs:
        acc += w
        if acc >= tot / 2:
            return v
    return pairs[-1][0]


def scorecard() -> tuple[dict, dict, str]:
    zpath, url = fc12.download_asset()
    units, labels = {}, {}
    with zipfile.ZipFile(zpath) as zf:
        name = next(n for n in zf.namelist() if n.endswith(FOS_FILE) and not n.startswith("__MACOSX"))
        with zf.open(name) as raw:
            for r in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")):
                key = (r["CIPCODE"].strip().zfill(4), r["CREDLEV"].strip())
                labels[key[1]] = r.get("CREDDESC", "").strip()
                u = units.setdefault(key, {"cip": key[0], "credential level": key[1], "field": r.get("CIPDESC", "").strip(),
                                           "debt pairs": [], "programs": 0})
                u["programs"] += 1
                for col in ("EARN_MDN_1YR_NAT", "EARN_MDN_5YR_NAT", "EARN_MDN_7YR_NAT", "EARN_P25_5YR_NAT", "EARN_P75_5YR_NAT"):
                    if u.get(col) is None:
                        u[col] = num(r.get(col))
                u["debt pairs"].append((num(r.get("DEBT_ALL_STGP_EVAL_MDN")), num(r.get("DEBT_ALL_STGP_EVAL_N"))))
    zpath.unlink()
    for u in units.values():
        u["median debt (weighted median of program medians)"] = weighted_median(u.pop("debt pairs"))
    return units, labels, f"{url} ({name})"


def ratio(a, b):
    return a / b if a is not None and b else None


def main() -> None:
    links, xsrc = crosswalk()
    occ, osrc = oews()
    units, cred_labels, ssrc = scorecard()
    unlinked = []
    for (cip, lev), u in units.items():
        socs = [s for s in links.get(cip, ()) if s in occ and occ[s]["employment"]]
        u["linked occupations"] = len(socs)
        if not socs:
            unlinked.append(f"{cip} {u['field']}")
        for excl_top in (False, True):
            use = [s for s in socs if not (excl_top and occ[s]["top-coded"])]
            w = sum(occ[s]["employment"] for s in use)
            agg = {}
            for k in ("median", "p25", "p90"):
                pairs = [(occ[s][k], occ[s]["employment"]) for s in use if occ[s][k] is not None]
                ww = sum(p[1] for p in pairs)
                agg[k] = sum(v * x for v, x in pairs) / ww if ww else None
            suffix = " (top-coded occupations left out)" if excl_top else ""
            u["occupations' median wage" + suffix] = agg["median"]
            u["early position" + suffix] = ratio(u["EARN_MDN_5YR_NAT"], agg["median"])
            u["occupational ladder" + suffix] = ratio(agg["p90"], agg["p25"])
            u["payoff to cost" + suffix] = ratio(agg["median"], u["median debt (weighted median of program medians)"])
            if not excl_top:
                u["share of linked employment top-coded"] = (sum(occ[s]["employment"] for s in socs if occ[s]["top-coded"]) / w
                                                             if w else None)
        u["graduates' growth"] = ratio(u["EARN_MDN_7YR_NAT"], u["EARN_MDN_1YR_NAT"])
        u["early payoff"] = ratio(u["EARN_MDN_5YR_NAT"], u["median debt (weighted median of program medians)"])
        u["sector"] = ("trades" if lev in ("1", "2") and cip[:2] in TRADE_FAMILIES
                       else "professions" if lev == "7" else "other")

    rng = np.random.default_rng(SEED)

    def compare(measure, predicted_sign):
        p = [u[measure] for u in units.values() if u["sector"] == "professions" and u.get(measure) is not None]
        t = [u[measure] for u in units.values() if u["sector"] == "trades" and u.get(measure) is not None]
        if len(p) < 3 or len(t) < 3:
            return {"professions units": len(p), "trades units": len(t), "verdict": "too few units; not computed"}
        diff = float(np.median(p) - np.median(t))
        boots = [np.median(rng.choice(p, len(p))) - np.median(rng.choice(t, len(t))) for _ in range(BOOT)]
        ci = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
        if predicted_sign < 0:
            verdict = ("supported" if ci[1] < 0 else "in the predicted direction" if diff < 0 else "not supported")
        else:
            verdict = ("supported" if ci[0] > 0 else "in the predicted direction" if diff > 0 else "not supported")
        return {"professions units": len(p), "trades units": len(t), "median, professions": float(np.median(p)),
                "median, trades": float(np.median(t)), "difference (professions - trades)": diff,
                "95% interval": ci, "verdict": verdict}

    tests = {}
    for suffix in ("", " (top-coded occupations left out)"):
        tests["P1 early position lower for professions" + suffix] = compare("early position" + suffix, -1)
        tests["P2 occupational ladder higher for professions" + suffix] = compare("occupational ladder" + suffix, +1)
    tests["P3 graduates' growth higher for professions"] = compare("graduates' growth", +1)
    payoff = {s: {m: (lambda v: {"units": len(v), "median": float(np.median(v))} if v else None)(
        [u[m] for u in units.values() if u["sector"] == s and u.get(m) is not None])
        for m in ("payoff to cost", "early payoff", "median debt (weighted median of program medians)")}
        for s in ("trades", "professions")}
    by_level = {}
    for lev in sorted({k[1] for k in units}):
        sel = [u for (c, l), u in units.items() if l == lev]
        by_level[f"{lev} {cred_labels.get(lev, '')}"] = {
            m: (lambda v: float(np.median(v)) if v else None)([u[m] for u in sel if u.get(m) is not None])
            for m in ("EARN_MDN_1YR_NAT", "EARN_MDN_5YR_NAT", "EARN_MDN_7YR_NAT", "early position", "occupational ladder",
                      "graduates' growth", "payoff to cost")} | {"units": len(sel)}

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    DATA.mkdir(parents=True, exist_ok=True)
    sources = {"Scorecard field of study": ssrc, "OEWS": osrc, "CIP-SOC crosswalk": xsrc,
               "top code used for #": TOPCODE}
    OUT_UNITS.write_text(json.dumps({
        "protocol": "lifetime earnings protocol.md", "written at (UTC)": now, "sources": sources,
        "credential levels (from the file)": cred_labels, "fields with no linked occupation": sorted(set(unlinked)),
        "units": [u for _, u in sorted(units.items())]}, indent=1) + "\n", encoding="utf-8")
    OUT_TEST.write_text(json.dumps({
        "test": "Item 13: professions against trades, lifetime earnings (separate from the closure model)",
        "protocol": "lifetime earnings protocol.md", "written at (UTC)": now, "sources": sources,
        "sectors": {s: sum(1 for u in units.values() if u["sector"] == s) for s in ("trades", "professions", "other")},
        "predictions": tests, "payoff to cost by sector (no prediction)": payoff,
        "by credential level (medians across fields)": by_level,
        "limitations": ["The crosswalk links programs to the occupations they prepare for, not where graduates work.",
                        "The occupational ladder is a cross-section of all workers, not a followed career.",
                        "Top-coded wages are set at the top code, so results using them are lower bounds.",
                        "Debt is the median of program medians weighted by borrowers, an approximation."]},
        indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v.get("verdict") for k, v in tests.items()}, indent=1))


if __name__ == "__main__":
    main()
