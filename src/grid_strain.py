"""
Item 23k: the larger-grid strain test. How much financial strain
continuously anchoring an entropic system places on the wider grid: per
college and sector, fiscal year by fiscal year, the gap between what a
college spends and what it earns on its own, and who covers it: the
federal government, state and local governments (and through both the
taxpayers), donors and alumni (gifts, reported together), and the
endowment. Descriptive; no model is fitted and no outcome is predicted.

Extends item 15c (src/anchor efficiency.py), which split the frozen item-15
gap among appropriations, gifts and endowment spending for public and
private nonprofit colleges, into a full accounting by payer for every
sector, fiscal 2005 to 2024.

The accounting, per college-year (all from the same IPEDS finance files as
item 15, read through the frozen item-15 reader, unchanged):

  spending W              total expenses less depreciation (item 15)
  covered by              exchange income E + other operating income O
                          + anchors A (appropriations, gifts, endowment
                          spending; item 15) + what is left uncovered
  student grants          Pell and other federal grants, state grants and
                          local grants to students (the scholarship section
                          of each form) already sit inside E or O, wherever
                          a college books them; they are moved out of the
                          college's own earned income to the government that
                          paid them (decisions 2 and 4, November 27)
  own earned income       E + O - student grants
  gap (payer view)        W - own earned income: the strain the wider grid
                          carries; covered by
    federal               federal appropriations + federal student grants
    state                 state appropriations + state student grants
    local                 local appropriations + local student grants
    gifts                 donors and alumni together (IPEDS has one line)
    endowment             endowment spending (private nonprofits; item 15's
                          rule, estimated at 4.5% before fiscal 2020)
    uncovered             what no payer covers (negative: a surplus)
  frozen gap              item 15's gap (W - E - O), kept alongside so every
                          figure ties back to 15c and the README

Memo lines, outside the headline:
  federal loan volume     undergraduate federal loans (IPEDS student aid);
                          lent, not given, so not counted as anchoring
  default estimate        three-year cohort default rate (College Scorecard,
                          the repository's release copy, checked by SHA-256)
                          x undergraduate federal loan volume: a lower bound
                          (graduate and parent loans are not in the IPEDS
                          table), from the first year three-year rates exist;
                          per campus, so no chain is counted twice
  full-cost view          public colleges only: depreciation added to
                          spending, capital appropriations and capital grants
                          and gifts added to the anchors (private colleges
                          have no matching capital lines)
  unmeasured              local property-tax exemption (no national or
                          per-college source; New York's exemption code
                          25120 covers all nonprofit educational
                          organizations, not colleges alone)

For-profit colleges are included; the same federal channels are used for
every sector. Gifts on the for-profit form include private grants and
contracts (flagged). Dollars: CPI-U, fiscal 2024 dollars, totals (decision
8); HECA as the check. Every result is shown for all colleges and without
the colleges that run a hospital.

Writes data/grid_strain/:
  college_payers.csv     per college and fiscal year, nominal dollars
  sector_payers.csv      per sector, scope, fiscal year and deflator: totals
                         by payer, shares of the payer-view gap, memo lines
  results.json           headline comparisons (fiscal 2005, 2019, 2024),
                         by overleverage class (15c), resolution of the
                         student-aid fields, coverage and flags, files read

Usage (GitHub Actions only, via grid_strain.yml):
    cd src
    python grid_strain.py
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import importlib.util
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "data" / "grid_strain"
CLASSES = ROOT / "data" / "anchor efficiency" / "college classes.csv"

_e = importlib.util.spec_from_file_location("et", HERE / "ending types.py")
et = importlib.util.module_from_spec(_e)
_e.loader.exec_module(et)
_s = importlib.util.spec_from_file_location("ss", HERE / "strain_sources.py")
ss = importlib.util.module_from_spec(_s)
_s.loader.exec_module(ss)
_f = importlib.util.spec_from_file_location("etfc", HERE / "ending types field check.py")
etfc = importlib.util.module_from_spec(_f)
_f.loader.exec_module(etfc)
oc, s1, num, mc = et.oc, et.s1, et.num, etfc.mc

FIRST_FY, LAST_FY = et.FIRST_FY, et.LAST_FY
HEADLINE_YEARS = (2005, 2019, 2024)
PAYERS = ("federal", "state", "local", "gifts", "endowment", "uncovered")

# Student grants by source (scholarship section), by form.
GRANTS = {
    "F1A": {"federal": ("F1E01", "F1E02"), "state": ("F1E03",), "local": ("F1E04",)},
    "F2": {"federal": ("F2C01", "F2C02"), "state": ("F2C03",), "local": ("F2C04",)},
    # for-profit state and local grants are one line before fiscal 2014 (F3C03), split from 2014 (F3C03A, F3C03B)
    "F3": {"federal": ("F3C01", "F3C02"), "state": ("F3C03A",), "local": ("F3C03B",)},
}
PELL = {"F1A": "F1E01", "F2": "F2C01", "F3": "F3C01"}
# For-profit anchors (not read by item 15, whose rule leaves for-profits unanchored).
F3_APPROPS = {"federal": "F3D02A", "state": "F3D03A", "local": "F3D03C"}
F3_GIFTS = "F3D04"
F1_CAPITAL = ("F1B20", "F1B21")          # capital appropriations; capital grants and gifts

SCORECARD_URL = ("https://github.com/carmen-speer/RICD-Tell/releases/download/"
                 "scorecard-raw-data-2026-11-02/College_Scorecard_Raw_Data_11022026.zip")
SCORECARD_SHA256 = "ec66842e4c788a77818b81f23f2262020127d0524cc7132cf96e3207da463ec7"
SC_NAME = re.compile(r"MERGED(\d{4})_\d{2}_PP\.csv$", re.I)
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def total_of(r: dict, codes) -> float | None:
    vals = [num(r.get(c)) for c in codes]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


# ------------------------------------------------------------------ finance extras, from item 15's own downloads
EXTRA: dict = defaultdict(dict)


def hooked_table(orig):
    def table(name):
        t = orig(name)
        if t is None or "_" not in name or not name.startswith("F"):
            return t
        stem, form = name.split("_", 1)
        if form not in GRANTS or len(stem) != 5:
            return t
        fy = 2000 + int(stem[3:5])
        for u, rows in t.items():
            r = rows[0]
            rec = {"flags": []}
            for level, codes in GRANTS[form].items():
                rec[f"{level} student grants"] = total_of(r, codes) or 0.0
            if form == "F3" and fy < 2014:
                rec["state student grants"] = num(r.get("F3C03")) or 0.0
                rec["local student grants"] = 0.0
                rec["flags"].append("for-profit state and local student grants reported together (counted as state)")
            rec["Pell"] = num(r.get(PELL[form])) or 0.0
            if form == "F3":
                for level, c in F3_APPROPS.items():
                    rec[f"{level} appropriations (for-profit form)"] = num(r.get(c)) or 0.0
                rec["gifts (for-profit form)"] = num(r.get(F3_GIFTS)) or 0.0
            if form == "F1A":
                rec["capital appropriations"] = num(r.get(F1_CAPITAL[0])) or 0.0
                rec["capital grants and gifts"] = num(r.get(F1_CAPITAL[1])) or 0.0
            dep = next((v for c in ss.DEP_TOTAL[form] if (v := num(r.get(c))) is not None), None)
            rec["depreciation"] = dep
            rec["hospital spending"] = num(r.get(ss.ROWS[form]["hospitals"][0])) or 0.0
            EXTRA[u][fy] = rec
        return t
    return table


# ------------------------------------------------------------------ federal loans (IPEDS student aid)
LOAN_TITLE = re.compile(r"(total|amount).*federal.*loan.*undergraduate|undergraduate.*federal.*loan.*(total|amount)", re.I)
LOAN_NOT = re.compile(r"average|number|percent|first-time|full-time|grant|pell|private|other loan", re.I)


def loans() -> tuple[dict, dict]:
    """{unitid: {fy: undergraduate federal loan dollars}} and how each year's field was resolved."""
    out: dict = defaultdict(dict)
    resolved = {}
    for fy in range(FIRST_FY, LAST_FY + 1):
        a, b = (fy - 1) % 100, fy % 100
        base = f"SFA{a:02d}{b:02d}"
        var, title, cands = None, None, {}
        for dname in (base, f"{base}_P1", f"{base}_P2"):
            info = etfc.variables(dname)
            if info.get("status") != "read":
                continue
            vs = info["variables"]
            if "UFLOANT" in vs:
                var, title = "UFLOANT", vs["UFLOANT"]
                break
            found = {v: t for v, t in vs.items() if LOAN_TITLE.search(t) and not LOAN_NOT.search(t)}
            cands |= found
            if len(found) == 1:
                var, title = next(iter(found.items()))
                break
        if not var:
            resolved[fy] = {"status": "ambiguous" if cands else "no field resolved", "candidates": cands}
            continue
        table = None
        for tname in (base, f"{base}_P1", f"{base}_P2"):
            t = s1.table(tname)
            if t and any(var in rows[0] for rows in list(t.values())[:50]):
                table = tname
                break
        if table is None:
            resolved[fy] = {"variable": var, "title": title, "status": "no data table holds the field"}
            continue
        n = 0
        for u, rows in t.items():
            v = num(rows[0].get(var))
            if v is not None and v >= 0:
                out[u][fy] = v
                n += 1
        resolved[fy] = {"table": table, "variable": var, "title": title, "colleges with a value": n}
        print("loans", fy, table, var, n, flush=True)
    return out, resolved


# ------------------------------------------------------------------ default rates (College Scorecard, release copy)
def default_rates() -> tuple[dict, dict]:
    """{unitid: {fy: three-year cohort default rate}} from the release copy, checked by SHA-256."""
    path = OUT / "scorecard_tmp.zip"
    sha = hashlib.sha256()
    with requests.get(SCORECARD_URL, stream=True, timeout=900, headers=HEADERS) as r:
        if r.status_code != 200:
            raise SystemExit(f"College Scorecard release copy not downloaded (HTTP {r.status_code}). Nothing recorded.")
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                sha.update(chunk)
    if sha.hexdigest() != SCORECARD_SHA256:
        path.unlink()
        raise SystemExit(f"Scorecard file's SHA-256 is {sha.hexdigest()}, not the repository's {SCORECARD_SHA256}. Nothing recorded.")
    out: dict = defaultdict(dict)
    years = {}
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            m = SC_NAME.search(name)
            if not m or name.startswith("__MACOSX") or "/._" in name or name.startswith("._"):
                continue
            fy = int(m.group(1)) + 1                 # MERGED2018_19 -> fiscal 2019
            if not FIRST_FY <= fy <= LAST_FY:
                continue
            n = 0
            with zf.open(name) as raw:
                rd = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"))
                rd.fieldnames = [h.strip().lstrip("﻿").upper() for h in rd.fieldnames]
                if "CDR3" not in rd.fieldnames:
                    years[fy] = "no CDR3 column"
                    continue
                for row in rd:
                    v = num((row.get("CDR3") or "").strip())
                    if v is not None and 0 <= v <= 1:
                        out[row["UNITID"].strip()][fy] = v
                        n += 1
            years[fy] = n
            print("default rates", fy, n, flush=True)
    path.unlink()
    first = min((y for y, n in years.items() if isinstance(n, int) and n > 500), default=None)
    return out, {"source": SCORECARD_URL, "sha256": SCORECARD_SHA256, "colleges with a rate, by fiscal year": years,
                 "first fiscal year used (three-year rates exist)": first}


# ------------------------------------------------------------------ the accounting
def payer_record(rec: dict, ex: dict, sec: str, loan: float | None, cdr: float | None) -> dict:
    W, E, O = rec["W"], rec["E"], rec["O"] or 0.0
    anchors = rec["anchors"] or {}
    flags = list(rec["flags"]) + list(ex["flags"])
    sg = {lv: ex[f"{lv} student grants"] for lv in ("federal", "state", "local")}
    if sec == "for-profit":
        appro = {lv: ex[f"{lv} appropriations (for-profit form)"] for lv in ("federal", "state", "local")}
        gifts, endow = ex["gifts (for-profit form)"], 0.0
        flags.append("for-profit gifts include private grants and contracts")
        # item 15 counts these inside O for for-profits (no anchors); take them out so nothing is counted twice
        inside_O = sum(appro.values()) + gifts
    else:
        appro = {"federal": anchors.get("federal appropriations", 0.0),
                 "state": anchors.get("state appropriations", 0.0),
                 "local": anchors.get("local appropriations", 0.0)}
        gifts, endow = anchors.get("gifts", 0.0), anchors.get("endowment spending", 0.0)
        inside_O = 0.0
    O_own = O - inside_O
    own = E + O_own - sum(sg.values())
    if own < 0:
        flags.append("student grants exceed exchange and other income (own earned income set to zero)")
        own = 0.0
    gap = W - own
    paid = {"federal": appro["federal"] + sg["federal"], "state": appro["state"] + sg["state"],
            "local": appro["local"] + sg["local"], "gifts": gifts, "endowment": endow}
    paid["uncovered"] = gap - sum(paid.values())
    out = {"W": W, "own earned income": own, "gap (payer view)": gap, "frozen gap (item 15)": W - E - O,
           **{f"paid by {p}": v for p, v in paid.items()},
           "of federal: Pell": ex["Pell"], "of federal: appropriations": appro["federal"],
           "memo: undergraduate federal loans": loan,
           "memo: default estimate (lower bound)": (cdr * loan) if (cdr is not None and loan is not None) else None,
           "memo: depreciation": ex["depreciation"], "flags": flags}
    if sec == "public":
        cap = ex["capital appropriations"] + ex["capital grants and gifts"]
        dep = ex["depreciation"] or 0.0
        out |= {"full cost: spending with depreciation": W + dep,
                "full cost: capital appropriations": ex["capital appropriations"],
                "full cost: capital grants and gifts": ex["capital grants and gifts"],
                "full cost: uncovered": paid["uncovered"] + dep - cap}
    return out


NUMS = ("W", "own earned income", "gap (payer view)", "frozen gap (item 15)") + tuple(f"paid by {p}" for p in PAYERS) + (
    "of federal: Pell", "of federal: appropriations", "memo: undergraduate federal loans",
    "memo: default estimate (lower bound)", "memo: depreciation", "full cost: spending with depreciation",
    "full cost: capital appropriations", "full cost: capital grants and gifts", "full cost: uncovered")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    heca_fy, heca_log = ss.heca()
    defl = ss.deflators(heca_fy)
    defl = {"CPI-U": defl["CPI-U"], "HECA": defl["HECA"]}        # CPI-U the headline here, HECA the check
    s1.table = hooked_table(s1.table)

    hd, hd_used, hd_missing = et.headers()
    log: dict = {}
    fin = et.finance(log)
    ef = et.enrollment(log)
    loan, loan_log = loans()
    cdr, cdr_log = default_rates()
    first_cdr = cdr_log["first fiscal year used (three-year rates exist)"]

    present = defaultdict(dict)
    for y, t in hd.items():
        for u, r in t.items():
            present[u][y] = r
    frame = {u: rows for u, rows in present.items() if any(oc.in_frame(r) for r in rows.values())}

    def sector_of(rows):
        for y in sorted(rows, reverse=True):
            s = rows[y].get("CONTROL", "")
            if s in et.SECTOR:
                return et.SECTOR[s]
        return None

    classes = {}
    if CLASSES.exists():
        with open(CLASSES, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                classes[row["unitid"]] = row["class"]

    rows_out, per = [], {}
    for u, rows in frame.items():
        sec = sector_of(rows)
        if sec is None:
            continue
        ser = {}
        for fy in range(FIRST_FY, LAST_FY + 1):
            rec = et.year_record(u, fy, fin, ef, sec)
            ex = EXTRA.get(u, {}).get(fy)
            if not rec or not rec["valid"] or ex is None:
                continue
            c = cdr.get(u, {}).get(fy) if (first_cdr and fy >= first_cdr) else None
            ser[fy] = payer_record(rec, ex, sec, loan.get(u, {}).get(fy), c)
        if not ser:
            continue
        hosp = any((EXTRA[u][fy]["hospital spending"] or 0) > 0 for fy in ser)
        per[u] = {"name": rows[max(rows)].get("INSTNM", ""), "sector": sec, "class": classes.get(u, "not classified"),
                  "hospital college": hosp, "series": ser}

    agg = defaultdict(lambda: defaultdict(float))
    for u, c in per.items():
        for fy, v in c["series"].items():
            for scope in ("all colleges", "without hospital colleges"):
                if scope == "without hospital colleges" and c["hospital college"]:
                    continue
                for cls in ("all classes", c["class"]):
                    for dname, d in defl.items():
                        k = (c["sector"], scope, cls, fy, dname)
                        agg[k]["colleges"] += 1
                        for key in NUMS:
                            if v.get(key) is not None:
                                agg[k][key] += v[key] * d[fy]
                                agg[k][key + " | n"] += 1
                        if v["gap (payer view)"] > 0:
                            agg[k]["colleges with a payer-view gap"] += 1
                        if v["paid by uncovered"] > 0:
                            agg[k]["uncovered shortfall (colleges short only)"] += v["paid by uncovered"] * d[fy]

    with open(OUT / "college_payers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["unitid", "name", "sector", "class (item 15c)", "hospital college", "fiscal year"]
                   + [f"{k} (nominal $)" for k in NUMS] + ["flags"])
        for u, c in sorted(per.items(), key=lambda kv: (kv[1]["sector"], kv[1]["name"])):
            for fy, v in sorted(c["series"].items()):
                w.writerow([u, c["name"], c["sector"], c["class"], c["hospital college"], fy]
                           + [("" if v.get(k) is None else round(v[k], 2)) for k in NUMS] + ["; ".join(sorted(set(v["flags"])))])

    cols = ["colleges", "colleges with a payer-view gap"] + list(NUMS) + ["uncovered shortfall (colleges short only)"]
    with open(OUT / "sector_payers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sector", "scope", "class (item 15c)", "fiscal year", "deflator (fiscal 2024 dollars)"] + cols
                   + [f"share of the payer-view gap: {p}" for p in PAYERS])
        for (sec, scope, cls, fy, dname), a in sorted(agg.items()):
            gap = a["gap (payer view)"]
            w.writerow([sec, scope, cls, fy, dname] + [round(a[c_]) for c_ in cols]
                       + [(round(a[f"paid by {p}"] / gap, 4) if gap > 0 else "") for p in PAYERS])

    head = {}
    for (sec, scope, cls, fy, dname), a in agg.items():
        if dname != "CPI-U" or fy not in HEADLINE_YEARS:
            continue
        gap = a["gap (payer view)"]
        head.setdefault(sec, {}).setdefault(scope, {}).setdefault(cls, {})[fy] = {
            "colleges": int(a["colleges"]), "spending (W)": round(a["W"]), "own earned income": round(a["own earned income"]),
            "gap (payer view)": round(gap), "frozen gap (item 15)": round(a["frozen gap (item 15)"]),
            "paid by": {p: round(a[f"paid by {p}"]) for p in PAYERS},
            "share of the payer-view gap": {p: (round(a[f"paid by {p}"] / gap, 4) if gap > 0 else None) for p in PAYERS},
            "uncovered shortfall (colleges short only)": round(a["uncovered shortfall (colleges short only)"]),
            "of federal: Pell": round(a["of federal: Pell"]),
            "memo: undergraduate federal loans": round(a["memo: undergraduate federal loans"]),
            "memo: default estimate (lower bound)": round(a["memo: default estimate (lower bound)"]),
            "full cost (public only): uncovered": round(a["full cost: uncovered"]) if sec == "public" else None,
        }
    flags = Counter(fl for c in per.values() for v in c["series"].values() for fl in set(v["flags"]))
    results = {
        "note": ("Item 23k, descriptive. Fiscal 2024 dollars (CPI-U headline; HECA rows in sector_payers.csv as the "
                 "check). The payer-view gap is spending less the college's own earned income, with student grants "
                 "moved to the government that paid them; item 15's frozen gap is kept alongside. Gifts are donors and "
                 "alumni together. Local property-tax exemption is unmeasured (no national or per-college source)."),
        "for-profit note": (
            "For-profit colleges use the same federal channels as the other sectors (appropriations and student "
            "grants, plus the default estimate as a memo). Tuition paid with federal loans stays in their own earned "
            "income, so their federal share reads lower than the Department's 90/10 revenue share, which counts loans."),
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "headline (CPI-U, fiscal 2005, 2019 and 2024)": head,
        "student aid fields resolved, by fiscal year": loan_log,
        "default rates": cdr_log,
        "flags (college-years)": dict(flags),
        "colleges": dict(Counter(c["sector"] for c in per.values())),
        "deflators": {"HECA": heca_log, "CPI-U": ss.CPI_FY},
        "header files used": hd_used, "header files not served": hd_missing, "finance and enrollment files": log,
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({s: {sc: d.get("all classes") for sc, d in v.items()} for s, v in head.items()}, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
