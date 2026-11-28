"""
Item 23f: where the strain comes from inside a college. Which spending
lines (instruction, administration, debt service, auxiliaries and the
others) drive the growth in the gap between what a college spends and what
it earns on its own, per college and sector, fiscal 2005 to 2024
(for-profit colleges from fiscal 2014, when their spending lines become
comparable). Descriptive; no model is fitted and no outcome is predicted.

The gap is the frozen item-15 gap, imported unchanged from
src/ending types.py: total expenses less depreciation (W), less exchange
income (net tuition and fees plus auxiliary sales, E), less other operating
income (O). Its change between an early and a late window is split exactly
into the change in each spending line and the change in each income part:

    change in gap = sum over spending lines (change in line)
                    - change in E - change in O

Data decisions (approved November 27, 2026, before anything was built):

  field check    done from the dictionaries already committed with item 15
                 (data/ending types/field check.json); every code read here
                 is named there, form by form and year by year
  lines          instruction, research, public service, academic support,
                 student services, institutional support, auxiliaries,
                 student aid paid out (public scholarships and fellowships;
                 private and for-profit net grant aid), hospitals,
                 independent operations, other, interest (debt service:
                 IPEDS reports no principal); depreciation is reported as
                 its own line but is not in the gap (decision 7)
  administration institutional support alone as the headline; the
                 administrative layer (institutional plus academic support)
                 as a second figure (decision 5)
  plant upkeep   operation and maintenance of plant is its own line through
                 fiscal 2015 and allocated into the functions from fiscal
                 2016; before 2016 the remaining plant line is spread back
                 across the functions using the college's own per-function
                 plant columns where it reported them, and its spending
                 shares where it did not (decision 6)
  depreciation,  taken out of the functions as each college reported them by
  interest       function through fiscal 2015 (with the plant line's own
                 share spread with it); from fiscal 2016, when only totals
                 are reported, by the college's own mean shares from its
                 last three reported years, so each college's lines stay
                 continuous across 2016; with no reported shares, by each
                 function's size (approved November 27, after the first run
                 showed the size rule gave auxiliaries too little
                 depreciation); the earlier size rule's fiscal 2015 check
                 is kept as a diagnostic
  discounting    tuition and auxiliary discounts are already netted out of
                 income, so they are not spending; the part funded by the
                 college's own grants (estimated pro rata from the grant
                 sources) is reported as forgone revenue, an income-side
                 driver, alongside the gap (decision 9)
  hospitals      their own line, never merged; every sector result is shown
                 for all colleges and without the colleges that run a
                 hospital (decision 10)
  people/plant   a second cut by natural class: people (salaries and
                 benefits), plant upkeep, interest, and all other
                 (decision 11), compared within fiscal 2016-2018 against
                 2022-2024 only, since plant upkeep is reported as its own
                 natural class only from fiscal 2016 (approved November 27,
                 after the first run showed the break)
  dollars        SHEEO's Higher Education Cost Adjustment (HECA) and dollars
                 per full-time-equivalent student as the headline; CPI-U
                 (approximately fiscal-year averages) as the check
                 (decision 8); all in fiscal 2024 dollars
  for-profits    included from fiscal 2014; their own earned income in IPEDS
                 includes tuition paid with federal aid, so their gap is
                 not directly comparable to the other sectors' (decision 1;
                 see the note in results.json)

Windows: early 2005-2007 (for-profits 2014-2016) against late 2022-2024,
and against 2017-2019 (before the federal pandemic relief of 2020-2023,
which entered other operating income). Window values are three-year means.
Sector decompositions use the same colleges in both windows (those with data
in each), so closures and openings do not masquerade as drivers; the
year-by-year sector series use every college with data in that year.

Writes data/strain_sources/:
  college_lines.csv      per college and fiscal year: nominal dollars for
                         every line, the income parts, the gap, depreciation,
                         discounts, the natural-class cut, flags
  sector_lines.csv       per sector, scope (all colleges / without hospital
                         colleges), fiscal year, deflator and measure (total
                         or per FTE): every line, the income parts and the gap
  college_drivers.csv    per college: early and late gap per FTE and the
                         change in every line and income part (HECA, per FTE),
                         and the largest driver of a growing gap
  results.json           the decompositions by sector, overleverage class
                         (item 15c) and scope; driver counts; diagnostics;
                         the deflators used; files read

Usage (GitHub Actions only, via strain_sources.yml):
    cd src
    python strain_sources.py
"""
from __future__ import annotations

import csv
import datetime
import importlib.util
import io
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "data" / "strain_sources"
CLASSES = ROOT / "data" / "anchor efficiency" / "college classes.csv"

_e = importlib.util.spec_from_file_location("et", HERE / "ending types.py")
et = importlib.util.module_from_spec(_e)
_e.loader.exec_module(et)
oc, s1, num = et.oc, et.s1, et.num

FIRST_FY, LAST_FY = et.FIRST_FY, et.LAST_FY          # 2005, 2024
FOR_PROFIT_FROM = 2014                               # F1314: for-profit lines comparable from here
PLANT_ALLOCATED_FROM = 2016                          # F1516: plant spread into the functions
BASE_FY = 2024                                       # constant dollars of fiscal 2024
EARLY, EARLY_FP = (2005, 2006, 2007), (2014, 2015, 2016)
LATE = {"late (2022-2024)": (2022, 2023, 2024), "before pandemic relief (2017-2019)": (2017, 2018, 2019)}
# people against plant: plant upkeep is reported as its own natural class only from fiscal 2016 (publics
# from 2011, but the private and for-profit forms from 2016), so that cut compares within 2016-2024 only
NATURAL_EARLY, NATURAL_LATE = (2016, 2017, 2018), (2022, 2023, 2024)
MIN_WINDOW_YEARS = 2                                 # years with data needed in each window

# ------------------------------------------------------------------ deflators
# CPI-U, U.S. city average, all items, annual averages (BLS series CUUR0000SA0).
CPI_ANNUAL = {2004: 188.9, 2005: 195.3, 2006: 201.6, 2007: 207.342, 2008: 215.303, 2009: 214.537,
              2010: 218.056, 2011: 224.939, 2012: 229.594, 2013: 232.957, 2014: 236.736, 2015: 237.017,
              2016: 240.007, 2017: 245.120, 2018: 251.107, 2019: 255.657, 2020: 258.811, 2021: 270.970,
              2022: 292.655, 2023: 304.702, 2024: 313.689}
# Fiscal year t runs July t-1 to June t: approximated by the mean of calendar years t-1 and t.
CPI_FY = {fy: (CPI_ANNUAL[fy - 1] + CPI_ANNUAL[fy]) / 2 for fy in range(FIRST_FY, LAST_FY + 1)}

HECA_URL = "https://shef.sheeo.org/wp-content/uploads/2026/04/SHEEO_SHEF_FY25_Data_Adjustments.xlsx"
# Published U.S. HECA values (SHEF FY 2025 report, Table 2.1; fiscal 2025 = 1.0000), used to check the parse.
HECA_CHECK = {2015: 0.7491, 2020: 0.8303, 2024: 0.9689}
HECA_TOL = 0.0006

# ------------------------------------------------------------------ the lines
FUNCTIONS = ("instruction", "research", "public service", "academic support", "student services",
             "institutional support", "auxiliaries", "student aid paid out", "hospitals",
             "independent operations", "other")
PLANT_USERS = tuple(f for f in FUNCTIONS if f != "student aid paid out")   # aid uses no buildings
LINES = FUNCTIONS + ("interest",)               # spending lines in the gap (W, less depreciation)
INCOME = ("exchange income (E)", "other operating income (O)")
NATURAL = ("people (salaries and benefits)", "plant upkeep", "interest (natural)", "all other (natural)")

# Gross row totals by form. Each value: tuple of codes, the first present is used.
ROWS = {
    "F1A": {"instruction": ("F1C011",), "research": ("F1C021",), "public service": ("F1C031",),
            "academic support": ("F1C051",), "student services": ("F1C061",),
            "institutional support": ("F1C071",), "auxiliaries": ("F1C111",),
            "student aid paid out": ("F1C101",), "hospitals": ("F1C121",),
            "independent operations": ("F1C131",),
            # other: other operating expenses and deductions, plus (to fiscal 2009) other nonoperating ones
            "other": ("F1C141", "F1C171")},
    "F2": {"instruction": ("F2E011",), "research": ("F2E021",), "public service": ("F2E031",),
           "academic support": ("F2E041",), "student services": ("F2E051",),
           "institutional support": ("F2E061",), "auxiliaries": ("F2E071",),
           "student aid paid out": ("F2E081",), "hospitals": ("F2E091",),
           "independent operations": ("F2E101",), "other": ("F2E121",)},
    "F3": {"instruction": ("F3E011",), "research": ("F3E02A1",), "public service": ("F3E02B1",),
           "academic support": ("F3E03A1",), "student services": ("F3E03B1",),
           "institutional support": ("F3E03C1",), "auxiliaries": ("F3E041",),
           "student aid paid out": ("F3E051",), "hospitals": ("F3E101",),
           "independent operations": (), "other": ("F3E061",)},
}
SUM_CODES = {"other"}            # rows whose codes are added, not first-present
PLANT_ROW = {"F1A": "F1C081", "F2": "F2E111", "F3": "F3E111"}
# Per-function plant (O&M) columns, before fiscal 2016: the college's own split of plant costs.
PLANT_COLS = {
    "F1A": {"instruction": "F1C016", "research": "F1C026", "public service": "F1C036",
            "academic support": "F1C056", "student services": "F1C066", "institutional support": "F1C076",
            "auxiliaries": "F1C116", "hospitals": "F1C126", "independent operations": "F1C136", "other": "F1C146"},
    "F2": {"instruction": "F2E014", "research": "F2E024", "public service": "F2E034",
           "academic support": "F2E044", "student services": "F2E054", "institutional support": "F2E064",
           "auxiliaries": "F2E074", "hospitals": "F2E094", "independent operations": "F2E104", "other": "F2E124"},
    "F3": {"instruction": "F3E014", "research": "F3E02A4", "public service": "F3E02B4",
           "academic support": "F3E03A4", "student services": "F3E03B4", "institutional support": "F3E03C4",
           "auxiliaries": "F3E044", "hospitals": "F3E104", "other": "F3E064"},
}
# Per-function depreciation columns, fiscal 2015 only (the diagnostic).
DEP_COLS = {
    "F1A": {"instruction": "F1C014", "research": "F1C024", "public service": "F1C034",
            "academic support": "F1C054", "student services": "F1C064", "institutional support": "F1C074",
            "auxiliaries": "F1C114", "hospitals": "F1C124", "independent operations": "F1C134", "other": "F1C144"},
    "F2": {"instruction": "F2E015", "research": "F2E025", "public service": "F2E035",
           "academic support": "F2E045", "student services": "F2E055", "institutional support": "F2E065",
           "auxiliaries": "F2E075", "hospitals": "F2E095", "independent operations": "F2E105", "other": "F2E125"},
    "F3": {"instruction": "F3E015", "research": "F3E02A5", "public service": "F3E02B5",
           "academic support": "F3E03A5", "student services": "F3E03B5", "institutional support": "F3E03C5",
           "auxiliaries": "F3E045", "hospitals": "F3E105", "other": "F3E065"},
}
DEP_COLS["F1A"]["student aid paid out"] = "F1C104"      # to fiscal 2009
DEP_COLS["F2"]["student aid paid out"] = "F2E085"       # to fiscal 2009
# Per-function interest columns, before fiscal 2016 (public from fiscal 2009).
INT_COLS = {
    "F1A": {"instruction": "F1C017", "research": "F1C027", "public service": "F1C037",
            "academic support": "F1C057", "student services": "F1C067", "institutional support": "F1C077",
            "auxiliaries": "F1C117", "hospitals": "F1C127", "independent operations": "F1C137", "other": "F1C147"},
    "F2": {"instruction": "F2E016", "research": "F2E026", "public service": "F2E036",
           "academic support": "F2E046", "student services": "F2E056", "institutional support": "F2E066",
           "auxiliaries": "F2E076", "student aid paid out": "F2E086", "hospitals": "F2E096",
           "independent operations": "F2E106", "other": "F2E126"},
    "F3": {"instruction": "F3E016", "research": "F3E02A6", "public service": "F3E02B6",
           "academic support": "F3E03A6", "student services": "F3E03B6", "institutional support": "F3E03C6",
           "auxiliaries": "F3E046", "hospitals": "F3E106", "other": "F3E066"},
}
# The plant row's own depreciation and interest, spread with the plant row before fiscal 2016.
PLANT_ROW_DEP = {"F1A": "F1C084", "F2": "F2E115", "F3": "F3E115"}
PLANT_ROW_INT = {"F1A": "F1C087", "F2": "F2E116", "F3": "F3E116"}
SHARE_YEARS = 3                  # a college's own shares: the mean of its last three reported years
OWN_SHARES: dict = {}            # (unitid, "depreciation" | "interest") -> list of share dicts, latest last
SPLIT_LOG: Counter = Counter()

TOTAL = {"F1A": ("F1C191",), "F2": ("F2E131",), "F3": ("F3E071",)}
DEP_TOTAL = {"F1A": ("F1C194", "F1C19DP"), "F2": ("F2E135",), "F3": ("F3E075",)}   # same as item 15
DEP_ROW = {"F1A": ("F1C094", "F1C091")}           # public depreciation reported as its own row (to fiscal 2009)
INT_COLUMN = {"F1A": ("F1C197", "F1C19IN"), "F2": ("F2E136",), "F3": ("F3E076",)}
INT_ROW = {"F1A": ("F1C161",)}           # public interest reported as its own row (to fiscal 2009)
SALARIES = {"F1A": ("F1C192",), "F2": ("F2E132",), "F3": ("F3E072",)}
BENEFITS = {"F1A": ("F1C193",), "F2": ("F2E133",), "F3": ("F3E073",)}
PLANT_NATURAL = {"F1A": ("F1C196", "F1C19OM"), "F2": ("F2E134",), "F3": ("F3E074",)}
# Discounts applied to tuition and to auxiliaries; student grants by source (for the pro-rata split).
DISCOUNTS = {"F1A": ("F1E08", "F1E09"), "F2": ("F2C08", "F2C09"), "F3": ("F3C06", "F3C07")}
INST_GRANTS = {"F1A": ("F1E05", "F1E06"), "F2": ("F2C05", "F2C06"), "F3": ("F3C04",)}
ALL_GRANTS = {"F1A": ("F1E07",), "F2": ("F2C07",), "F3": ("F3C05",)}


def total_of(r: dict, codes) -> float | None:
    vals = [num(r.get(c)) for c in codes]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def first_of(r: dict, codes) -> float | None:
    for c in codes:
        v = num(r.get(c))
        if v is not None:
            return v
    return None


def split_amount(total: float, gross: dict, reported: dict | None, key: tuple, fy: int) -> tuple[dict, str]:
    """Spread a depreciation or interest total over the functions.

    Through fiscal 2015: each function's reported amount (any remainder spread by size), and the
    college's shares are kept. From 2016, when only totals are reported: the college's own mean
    shares from its last three reported years; with none, by each function's size."""
    out = {f: 0.0 for f in FUNCTIONS}
    if total <= 0:
        return out, "none"
    base = sum(gross.values())
    if reported and sum(v for v in reported.values() if v > 0) > 0:
        for f, v in reported.items():
            out[f] += max(v, 0.0)
        rem = total - sum(out.values())
        if base > 0:
            for f in FUNCTIONS:
                out[f] += rem * gross[f] / base
        OWN_SHARES.setdefault(key, []).append({f: out[f] / total for f in FUNCTIONS})
        OWN_SHARES[key] = OWN_SHARES[key][-SHARE_YEARS:]
        return out, "reported by function"
    hist = OWN_SHARES.get(key)
    if fy >= PLANT_ALLOCATED_FROM and hist:
        for f in FUNCTIONS:
            out[f] = total * sum(h[f] for h in hist) / len(hist)
        return out, "college's own earlier shares"
    if base > 0:
        for f in FUNCTIONS:
            out[f] = total * gross[f] / base
    return out, "by size"


def college_lines(r: dict, form: str, fy: int, u: str = "") -> dict | None:
    """Every line for one college-year, before deflating. None when the expense table is blank."""
    gross_total = first_of(r, TOTAL[form])
    if gross_total is None or gross_total <= 0:
        return None
    flags = []
    gross = {}
    for f in FUNCTIONS:
        codes = ROWS[form][f]
        gross[f] = max((total_of(r, codes) if f in SUM_CODES else first_of(r, codes)) or 0.0, 0.0)

    # interest and depreciation reported as their own rows (public, to fiscal 2009) sit outside the functions
    int_row = first_of(r, INT_ROW.get(form, ())) or 0.0
    int_col = first_of(r, INT_COLUMN[form]) or 0.0
    interest = int_row + int_col
    dep_total = first_of(r, DEP_TOTAL[form])
    dep_row = first_of(r, DEP_ROW.get(form, ())) or 0.0
    if dep_total is None:
        dep_total = 0.0
        flags.append("depreciation not reported")
    dep_inside = max(dep_total - dep_row, 0.0)

    # decision 6: before fiscal 2016, spread the remaining plant line back across the functions
    plant_row = max(num(r.get(PLANT_ROW[form])) or 0.0, 0.0) if fy < PLANT_ALLOCATED_FROM else 0.0
    plant_spread = "none"
    pw = {}
    if plant_row > 0:
        own = {f: max(num(r.get(c)) or 0.0, 0.0) for f, c in PLANT_COLS[form].items()}
        if sum(own.values()) > 0:
            weights, plant_spread = own, "college's own plant columns"
        else:
            weights, plant_spread = {f: gross[f] for f in PLANT_USERS}, "spending shares"
        wsum = sum(weights.values())
        if wsum > 0:
            pw = {f: w / wsum for f, w in weights.items()}
            for f, w in pw.items():
                gross[f] += plant_row * w
        else:
            gross["other"] += plant_row
            plant_spread = "into other (no functions to spread over)"

    # decision 7 and debt service: take depreciation and interest out of the functions (approved
    # November 27: as each college reported them by function through fiscal 2015, and from 2016 by
    # the college's own earlier shares, so no break is created at 2016)
    inside_int = int_col
    base = sum(gross.values())

    def reported_by_function(cols: dict, row_code: str) -> dict | None:
        if fy >= PLANT_ALLOCATED_FROM:
            return None
        rep = {f: (num(r.get(c)) or 0.0) for f, c in cols.get(form, {}).items()}
        prow = max(num(r.get(row_code)) or 0.0, 0.0)
        for f, w in pw.items():
            rep[f] = rep.get(f, 0.0) + prow * w
        return rep if any(v > 0 for v in rep.values()) else None

    dep_split, dep_how = split_amount(dep_inside, gross, reported_by_function(DEP_COLS, PLANT_ROW_DEP[form]),
                                      (u, "depreciation"), fy)
    int_split, int_how = split_amount(inside_int, gross, reported_by_function(INT_COLS, PLANT_ROW_INT[form]),
                                      (u, "interest"), fy)
    SPLIT_LOG[("depreciation", form, fy, dep_how)] += 1
    SPLIT_LOG[("interest", form, fy, int_how)] += 1
    net = {f: gross[f] - dep_split[f] - int_split[f] for f in FUNCTIONS}
    net["interest"] = interest
    # tie the lines to the expense total less depreciation (any remainder goes to other)
    accounted = sum(net.values())
    lines_total = gross_total - dep_total
    resid = lines_total - accounted
    if abs(resid) > 0.01 * max(lines_total, 1.0):
        flags.append("lines differ from the expense total by more than 1%")
    net["other"] += resid

    sal = first_of(r, SALARIES[form])
    ben = first_of(r, BENEFITS[form])
    pn = first_of(r, PLANT_NATURAL[form])
    natural = None
    if sal is not None and ben is not None:
        people = sal + ben
        plant = pn if pn is not None else 0.0
        if pn is None:
            flags.append("plant upkeep not reported as a natural class (counted in all other)")
        natural = {"people (salaries and benefits)": people, "plant upkeep": plant,
                   "interest (natural)": interest,
                   "all other (natural)": lines_total - people - plant - interest}

    disc = total_of(r, DISCOUNTS[form])
    inst = total_of(r, INST_GRANTS[form])
    allg = first_of(r, ALL_GRANTS[form])
    forgone = None
    if disc is not None and inst is not None and allg is not None and allg > 0:
        forgone = disc * min(max(inst / allg, 0.0), 1.0)
    return {"lines": net, "depreciation": dep_total, "natural": natural, "discounts": disc,
            "forgone revenue": forgone, "plant spread": plant_spread, "plant spread dollars": plant_row,
            "flags": flags, "dep check": dep_check(r, form, gross, base, dep_inside, inside_int) if fy == 2015 else None}


def dep_check(r: dict, form: str, gross: dict, base: float, dep_inside: float, int_col: float) -> dict | None:
    """Fiscal 2015: each function's depreciation as reported against the proportional rule."""
    rep = {f: num(r.get(c)) for f, c in DEP_COLS[form].items()}
    if not any(v for v in rep.values() if v) or base <= 0 or dep_inside <= 0:
        return None
    return {f: {"reported": rep.get(f) or 0.0, "proportional": dep_inside * gross[f] / base} for f in DEP_COLS[form]}


# ------------------------------------------------------------------ HECA
def heca() -> tuple[dict, dict]:
    """U.S. HECA by fiscal year from SHEEO's Data Adjustments workbook, checked against published values."""
    import pandas as pd
    r = requests.get(HECA_URL, timeout=180)
    if r.status_code != 200 or r.content[:2] != b"PK":
        raise SystemExit(f"HECA workbook not downloaded (HTTP {r.status_code}). Nothing recorded.")
    sheets = pd.read_excel(io.BytesIO(r.content), sheet_name=None, header=None)
    found, seen = {}, {}
    for name, df in sheets.items():
        # every cell as text; blank cells as "" (pandas may keep a blank as a float NaN)
        grid = [["" if pd.isna(c) else str(c) for c in row] for row in df.values.tolist()]
        seen[name] = grid[:6]
        for i, row in enumerate(grid):
            for j, cell in enumerate(row):
                if "HECA" not in cell.upper():
                    continue
                # long layout: a HECA column under a header, years in another column
                cand = {}
                for row2 in grid[i + 1:]:
                    yrs = [c for c in row2 if _year(c)]
                    v = _val(row2[j]) if j < len(row2) else None
                    if yrs and v is not None:
                        cand[_year(yrs[0])] = v
                # where states are listed, keep the U.S. rows only
                us = {}
                for row2 in grid[i + 1:]:
                    if any(c.strip().upper() in ("U.S.", "US", "UNITED STATES", "U.S. AVERAGE", "NATIONAL") for c in row2):
                        yrs = [c for c in row2 if _year(c)]
                        v = _val(row2[j]) if j < len(row2) else None
                        if yrs and v is not None:
                            us[_year(yrs[0])] = v
                if len(us) >= 10:
                    cand = us
                # wide layout: a HECA row, years across a header row above it
                wide = {}
                for k in range(i - 1, -1, -1):
                    hdr = grid[k]
                    if sum(1 for c in hdr if _year(c)) >= 10:
                        for jj, c in enumerate(hdr):
                            if _year(c) and jj < len(row) and _val(row[jj]) is not None:
                                wide[_year(c)] = _val(row[jj])
                        break
                for got in (cand, wide):
                    if len(got) >= 20 and _passes(got):
                        found = got
                        break
                if found:
                    break
            if found:
                break
        if found:
            break
    if not found:
        (OUT / "heca_parse_failure.json").write_text(json.dumps(
            {"note": "No HECA series in the workbook matched the published check values; nothing else written.",
             "url": HECA_URL, "check": HECA_CHECK, "first rows by sheet": seen}, indent=1, default=str) + "\n")
        raise SystemExit("HECA series not found or failed the check against published values. Nothing recorded.")
    base = found[2025] if 2025 in found else 1.0
    series = {y: v / base for y, v in found.items()}
    return series, {"url": HECA_URL, "values (fiscal 2025 = 1)": {y: round(series[y], 4) for y in sorted(series)},
                    "check against SHEF FY 2025 Table 2.1": {y: [HECA_CHECK[y], round(series[y], 4)] for y in HECA_CHECK}}


def _year(c) -> int | None:
    s = str(c).strip().replace("FY", "").replace(".0", "").strip()
    return int(s) if s.isdigit() and 1980 <= int(s) <= 2030 else None


def _val(c) -> float | None:
    try:
        v = float(str(c).strip())
    except ValueError:
        return None
    return v if 0.1 <= v <= 1.6 else None


def _passes(got: dict) -> bool:
    if not all(y in got for y in HECA_CHECK):
        return False
    base = got.get(2025, 1.0)
    return all(abs(got[y] / base - v) <= HECA_TOL for y, v in HECA_CHECK.items())


# ------------------------------------------------------------------ reading
STORE: dict = defaultdict(dict)          # unitid -> fy -> lines
SPREAD_LOG: Counter = Counter()


def hooked_table(orig):
    """Wrap the item-15 table reader so the expense lines are read from the same download."""
    def table(name):
        t = orig(name)
        if t is None or "_" not in name or not name.startswith("F"):
            return t
        stem, form = name.split("_", 1)
        if form not in ROWS or len(stem) != 5:
            return t
        fy = 2000 + int(stem[3:5])
        for u, rows in t.items():
            got = college_lines(rows[0], form, fy, u)
            if got is not None:
                STORE[u][fy] = got
                SPREAD_LOG[(form, fy, got["plant spread"])] += 1
        return t
    return table


def deflators(heca_fy: dict) -> dict:
    missing = [fy for fy in range(FIRST_FY, LAST_FY + 1) if fy not in heca_fy]
    if missing:
        raise SystemExit(f"HECA missing for fiscal {missing}. Nothing recorded.")
    return {"HECA": {fy: heca_fy[BASE_FY] / heca_fy[fy] for fy in range(FIRST_FY, LAST_FY + 1)},
            "CPI-U": {fy: CPI_FY[BASE_FY] / CPI_FY[fy] for fy in range(FIRST_FY, LAST_FY + 1)}}


# ------------------------------------------------------------------ decomposition
KEYS = LINES + INCOME + ("gap", "depreciation (not in the gap)", "forgone revenue (memo)") + NATURAL


def year_values(rec: dict, lines: dict) -> dict:
    """Nominal values on one scale for one college-year (W ties to item 15's W)."""
    out = {k: lines["lines"][k] for k in LINES}
    out["exchange income (E)"] = rec["E"]
    out["other operating income (O)"] = rec["O"] or 0.0
    out["gap"] = rec["W"] - rec["E"] - (rec["O"] or 0.0)
    out["depreciation (not in the gap)"] = lines["depreciation"]
    out["forgone revenue (memo)"] = lines["forgone revenue"]
    nat = lines["natural"]
    for k in NATURAL:
        out[k] = nat[k] if nat else None
    # rescale lines so they sum exactly to item 15's W where W and the expense table differ slightly
    s = sum(out[k] for k in LINES)
    if s > 0 and rec["W"] > 0:
        f = rec["W"] / s
        for k in LINES:
            out[k] *= f
    return out


def window_mean(series: dict, years, defl: dict) -> dict | None:
    pts = [(fy, series[fy]) for fy in years if fy in series]
    if len(pts) < MIN_WINDOW_YEARS:
        return None
    out = {}
    for k in KEYS + ("N",):
        vals = [v[k] * (defl[fy] if k != "N" else 1.0) for fy, v in pts if v.get(k) is not None]
        out[k] = sum(vals) / len(vals) if len(vals) == len(pts) else None
    return out


def _per_fte(cs: list[dict], k: str) -> dict | None:
    """Early and late per FTE over the colleges that have the value in both windows."""
    sub = [c for c in cs if c["early"].get(k) is not None and c["late"].get(k) is not None]
    if len(sub) < 5:
        return None
    ne, nl = sum(c["early"]["N"] for c in sub), sum(c["late"]["N"] for c in sub)
    e = sum(c["early"][k] for c in sub) / ne
    l = sum(c["late"][k] for c in sub) / nl
    return {"early per FTE": round(e, 2), "late per FTE": round(l, 2), "change per FTE": round(l - e, 2),
            "colleges": len(sub)}


def decompose(colleges: list[dict]) -> dict | None:
    """Same colleges in both windows: per-FTE change in the gap split into lines and income parts."""
    cs = [c for c in colleges if c["early"] and c["late"] and c["early"]["N"] and c["late"]["N"]]
    if len(cs) < 5:
        return None
    # the gap, the lines and the income parts are present for every college kept, so they add exactly
    per = {k: _per_fte(cs, k) for k in KEYS}
    core = LINES + INCOME + ("gap",)
    if any(per[k] is None or per[k]["colleges"] != len(cs) for k in core):
        return None
    dgap = per["gap"]["change per FTE"]
    contrib = {k: per[k]["change per FTE"] for k in LINES}
    contrib["exchange income (E), falling"] = -per["exchange income (E)"]["change per FTE"]
    contrib["other operating income (O), falling"] = -per["other operating income (O)"]["change per FTE"]
    shares = {k: (round(v / dgap, 4) if dgap else None) for k, v in contrib.items()}
    admin = {"institutional support (headline)": per["institutional support"]["change per FTE"],
             "administrative layer (institutional plus academic support)":
                 round(per["institutional support"]["change per FTE"] + per["academic support"]["change per FTE"], 2)}
    ranked = sorted(contrib.items(), key=lambda kv: -kv[1])
    ne, nl = sum(c["early"]["N"] for c in cs), sum(c["late"]["N"] for c in cs)
    return {"colleges": len(cs), "FTE early": round(ne), "FTE late": round(nl),
            "change in the gap per FTE": dgap,
            "contributions to the change (per FTE; they add to the change in the gap)": contrib,
            "share of the change in the gap": shares,
            "largest three drivers of a growing gap": [k for k, v in ranked[:3] if v > 0] if dgap > 0 else [],
            "administration": admin,
            "memo: depreciation, not in the gap": per["depreciation (not in the gap)"],
            "memo: forgone revenue from the college's own grants": per["forgone revenue (memo)"],
            "levels per FTE": {k: per[k] for k in core}}


def natural_cut(colleges: list[dict]) -> dict | None:
    """People against plant, fiscal 2016-2018 against 2022-2024 (the natural classes are comparable only from 2016)."""
    cs = [c for c in colleges if c["early"] and c["late"] and c["early"]["N"] and c["late"]["N"]]
    if len(cs) < 5:
        return None
    per = {k: _per_fte(cs, k) for k in NATURAL + ("gap",)}
    return {"windows": [NATURAL_EARLY, NATURAL_LATE], "colleges": len(cs),
            "change per FTE": {k: (per[k]["change per FTE"] if per[k] else None) for k in NATURAL + ("gap",)},
            "levels per FTE": per}


def top_driver(c: dict) -> str | None:
    e, l = c["early"], c["late"]
    if not (e and l and e["N"] and l["N"]):
        return None
    d = {k: l[k] / l["N"] - e[k] / e["N"] for k in LINES}
    d["exchange income (E), falling"] = -(l["exchange income (E)"] / l["N"] - e["exchange income (E)"] / e["N"])
    d["other operating income (O), falling"] = -(l["other operating income (O)"] / l["N"] - e["other operating income (O)"] / e["N"])
    gap = l["gap"] / l["N"] - e["gap"] / e["N"]
    return max(d, key=d.get) if gap > 0 else "gap did not grow"


def split_log() -> dict:
    out = defaultdict(dict)
    for (what, form, fy, how), n in sorted(SPLIT_LOG.items()):
        out[f"{what} | {form} {fy}"][how] = n
    return dict(out)


# ------------------------------------------------------------------ main
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    heca_fy, heca_log = heca()
    defl = deflators(heca_fy)
    s1.table = hooked_table(s1.table)                     # one download serves item 15's reader and this one

    hd, hd_used, hd_missing = et.headers()
    years = sorted(hd)
    log: dict = {}
    fin = et.finance(log)
    ef = et.enrollment(log)
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

    per_college, raw_rows = {}, []
    sector_year = defaultdict(lambda: defaultdict(float))
    for u, rows in frame.items():
        sec = sector_of(rows)
        if sec is None:
            continue
        start = FOR_PROFIT_FROM if sec == "for-profit" else FIRST_FY
        series = {}
        for fy in range(start, LAST_FY + 1):
            rec = et.year_record(u, fy, fin, ef, sec)
            ln = STORE.get(u, {}).get(fy)
            if not rec or not rec["valid"] or ln is None:
                continue
            v = year_values(rec, ln)
            v["N"] = rec["N"]
            series[fy] = v
            raw_rows.append({"unitid": u, "fiscal year": fy, "lines": v, "flags": rec["flags"] + ln["flags"],
                             "plant spread": ln["plant spread"]})
        if not series:
            continue
        hosp = any(v["hospitals"] > 0 for v in series.values())
        name = rows[max(rows)].get("INSTNM", "")
        per_college[u] = {"unitid": u, "name": name, "sector": sec, "class": classes.get(u, "not classified"),
                          "hospital college": hosp, "series": series}
        for fy, v in series.items():
            for scope in ("all colleges", "without hospital colleges"):
                if scope == "without hospital colleges" and hosp:
                    continue
                for dname, d in defl.items():
                    k = (sec, scope, fy, dname)
                    sector_year[k]["colleges"] += 1
                    if v["N"]:
                        sector_year[k]["FTE"] += v["N"]
                    for key in KEYS:
                        if v.get(key) is not None:
                            sector_year[k][key] += v[key] * d[fy]
                            if v["N"]:
                                sector_year[k][key + " | FTE"] += v[key] * d[fy]
                                sector_year[k][key + " | FTE base"] += v["N"]

    # windows per college, for both deflators and both late windows
    decomp, natural = {}, {}
    driver_rows = []
    for dname, d in defl.items():
        for lname, late in LATE.items():
            groups = defaultdict(list)
            for c in per_college.values():
                early = EARLY_FP if c["sector"] == "for-profit" else EARLY
                cc = {"early": window_mean(c["series"], early, d), "late": window_mean(c["series"], late, d)}
                for scope in ("all colleges", "without hospital colleges"):
                    if scope == "without hospital colleges" and c["hospital college"]:
                        continue
                    groups[(c["sector"], scope, "all classes")].append(cc)
                    if c["sector"] != "for-profit":
                        groups[(c["sector"], scope, c["class"])].append(cc)
                if dname == "HECA":
                    drv = top_driver(cc)
                    if drv is not None:
                        c.setdefault("drivers", {})[lname] = (cc, drv)
            for (sec, scope, cls), cs in groups.items():
                res = decompose(cs)
                if res:
                    decomp.setdefault(dname, {}).setdefault(lname, {}).setdefault(sec, {}).setdefault(scope, {})[cls] = res
        ngroups = defaultdict(list)
        for c in per_college.values():
            cc = {"early": window_mean(c["series"], NATURAL_EARLY, d), "late": window_mean(c["series"], NATURAL_LATE, d)}
            for scope in ("all colleges", "without hospital colleges"):
                if scope == "without hospital colleges" and c["hospital college"]:
                    continue
                ngroups[(c["sector"], scope, "all classes")].append(cc)
                if c["sector"] != "for-profit":
                    ngroups[(c["sector"], scope, c["class"])].append(cc)
        for (sec, scope, cls), cs in ngroups.items():
            res = natural_cut(cs)
            if res:
                natural.setdefault(dname, {}).setdefault(sec, {}).setdefault(scope, {})[cls] = res

    driver_counts = defaultdict(lambda: defaultdict(Counter))
    for c in per_college.values():
        for lname, (cc, drv) in c.get("drivers", {}).items():
            e, l = cc["early"], cc["late"]
            row = {"unitid": c["unitid"], "name": c["name"], "sector": c["sector"], "class": c["class"],
                   "hospital college": c["hospital college"], "late window": lname,
                   "gap per FTE, early": round(e["gap"] / e["N"], 2), "gap per FTE, late": round(l["gap"] / l["N"], 2)}
            for k in LINES + INCOME + ("depreciation (not in the gap)",):
                row[f"change per FTE: {k}"] = round(l[k] / l["N"] - e[k] / e["N"], 2)
            row["largest driver of a growing gap"] = drv
            driver_rows.append(row)
            driver_counts[lname][f"{c['sector']} | {c['class']}"][drv] += 1
            driver_counts[lname][f"{c['sector']} | all classes"][drv] += 1

    # ------------------------------------------------ write
    with open(OUT / "college_lines.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["unitid", "name", "sector", "class (item 15c)", "hospital college", "fiscal year", "FTE"]
                   + [f"{k} (nominal $)" for k in KEYS] + ["plant line spread by", "flags"])
        for r in sorted(raw_rows, key=lambda r: (r["unitid"], r["fiscal year"])):
            c = per_college.get(r["unitid"])
            if not c:
                continue
            v = r["lines"]
            w.writerow([r["unitid"], c["name"], c["sector"], c["class"], c["hospital college"], r["fiscal year"], v["N"]]
                       + [("" if v.get(k) is None else round(v[k], 2)) for k in KEYS]
                       + [r["plant spread"], "; ".join(sorted(set(r["flags"])))])
    with open(OUT / "sector_lines.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sector", "scope", "fiscal year", "deflator (fiscal 2024 dollars)", "measure", "colleges", "FTE"] + list(KEYS))
        for (sec, scope, fy, dname), agg in sorted(sector_year.items()):
            w.writerow([sec, scope, fy, dname, "total dollars", int(agg["colleges"]), round(agg["FTE"])]
                       + [round(agg[k]) for k in KEYS])
            w.writerow([sec, scope, fy, dname, "per FTE", int(agg["colleges"]), round(agg["FTE"])]
                       + [(round(agg[k + " | FTE"] / agg[k + " | FTE base"], 2) if agg[k + " | FTE base"] else "") for k in KEYS])
    if driver_rows:
        with open(OUT / "college_drivers.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(driver_rows[0]))
            w.writeheader()
            w.writerows(sorted(driver_rows, key=lambda r: (r["late window"], r["sector"], r["name"])))

    # ------------------------------------------------ diagnostics
    dep = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for u, ys in STORE.items():
        chk = ys.get(2015, {}).get("dep check")
        if not chk:
            continue
        sec = per_college[u]["sector"] if u in per_college else "unknown"
        for f_, v in chk.items():
            dep[sec][f_][0] += v["reported"]
            dep[sec][f_][1] += v["proportional"]
    dep_out = {}
    for sec, d in dep.items():
        tr, tp = sum(v[0] for v in d.values()), sum(v[1] for v in d.values())
        dep_out[sec] = {f_: {"share reported": round(v[0] / tr, 4) if tr else None,
                             "share under the proportional rule": round(v[1] / tp, 4) if tp else None}
                        for f_, v in d.items()}
    spread = defaultdict(Counter)
    for (form, fy, how), n in SPREAD_LOG.items():
        spread[f"{form} {fy}"][how] += n
    flags = Counter()
    for r in raw_rows:
        for fl in set(r["flags"]):
            flags[fl] += 1

    results = {
        "note": ("Item 23f, descriptive. The gap is item 15's frozen gap (total expenses less depreciation, less "
                 "exchange income, less other operating income), imported unchanged. Contributions are per FTE in "
                 "fiscal 2024 dollars and add exactly to the change in the gap; a positive contribution widened the "
                 "gap. Sector decompositions use the same colleges in both windows. HECA is the headline deflator, "
                 "CPI-U the check."),
        "for-profit note": ("For-profit colleges are included from fiscal 2014. Their own earned income in IPEDS includes "
                            "tuition paid with federal student aid (up to 90% of revenue), so their gap reads lower than a "
                            "public or private nonprofit college with the same finances would, and is not directly "
                            "comparable across sectors. They are kept because their spending lines, measured the same way "
                            "on the same forms from fiscal 2014, are directly comparable, and the sector is where the "
                            "federal share of revenue is highest; what is lost is comparability of the gap's level across "
                            "sectors, not of the drivers within the sector. Item 23k moves the federal share out of "
                            "earned income for every sector."),
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "settings": {"early window": EARLY, "early window, for-profits": EARLY_FP, "late windows": LATE,
                     "fewest years with data in each window": MIN_WINDOW_YEARS,
                     "constant dollars of fiscal year": BASE_FY, "plant line spread back before fiscal": PLANT_ALLOCATED_FROM},
        "decompositions": decomp,
        "people against plant (natural classes, fiscal 2016-2018 against 2022-2024)": natural,
        "largest driver of a growing gap, colleges counted (HECA, per FTE)": {k: {g: dict(c) for g, c in v.items()}
                                                                              for k, v in driver_counts.items()},
        "diagnostics": {
            "depreciation by function, fiscal 2015: reported against the proportional rule": dep_out,
            "plant line spread before fiscal 2016 (colleges, by method)": {k: dict(v) for k, v in sorted(spread.items())},
            "flags (college-years)": dict(flags),
            "depreciation and interest taken out of the functions (college-years, by method)": split_log(),
            "colleges with lines": Counter(c["sector"] for c in per_college.values()),
            "hospital colleges": Counter(c["sector"] for c in per_college.values() if c["hospital college"]),
        },
        "deflators": {"HECA": heca_log, "CPI-U": {"series": "BLS CUUR0000SA0, annual averages; fiscal year t = mean of "
                                                            "calendar years t-1 and t", "values": CPI_FY}},
        "header files used": hd_used, "header files not served": hd_missing, "finance and enrollment files": log,
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    head = decomp.get("HECA", {}).get("late (2022-2024)", {})
    print(json.dumps({s: {sc: {k: v.get("share of the change in the gap") for k, v in d.items() if k == "all classes"}
                          for sc, d in sd.items()} for s, sd in head.items()}, indent=1, default=str))


if __name__ == "__main__":
    main()
