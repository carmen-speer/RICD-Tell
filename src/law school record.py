"""
Item 12, law-school record, step 2 ("channel selection protocol.md",
Amendments 8, 12 and 13): descriptive, not a test.

Reads the ABA compilation spreadsheets committed in
data/v4 channels/law schools/raw/ and builds, for every ABA school and
year, four measures, with the column mapping fixed in Amendment 13:

  first-time bar passage   school pass rate (and difference from the state
                           rate), by graduate or exam year: 509 "Bar Passage
                           Rates" sections 2011-2016 (composite school pass
                           %, rows of the file's own reporting year), then
                           the first-time bar-passage compilations (the 2018
                           file holds graduate years 2016 and 2017)
  employment               full-time, long-term bar-passage-required jobs /
                           total graduates, by graduating class, 2011 on
                           (2010 has no bar-passage-required column)
  first-year attrition     share of first-year students lost, all reasons
                           as each year reports them, by 509 reporting year
  first-year enrollment    first-year J.D. headcount, by 509 reporting year

Each value is turned into a percentile among all schools reporting it that
year (the share of schools with a lower value, ties counted half), so
definitions that changed between years are compared within each year only.
For each school on the fixed list it records the five years before its
ending and judges the expectation written in Amendment 8: bottom decile
(percentile 10 or below) on first-time bar passage or on employment in at
least two of the three years before the ending.

Output: data/v4 channels/law schools/law school record.json

Usage:
    cd src
    python "law school record.py"
"""

from __future__ import annotations

import datetime
import json
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
DIR = HERE.parent / "data" / "v4 channels" / "law schools"
RAW = DIR / "raw"
OUT = DIR / "law school record.json"

CLOSED = {  # Amendment 12: name pattern, ending year
    "Indiana Tech Law School": (r"^INDIANA TECH", 2017),
    "Charlotte School of Law": (r"^CHARLOTTE SCHOOL OF LAW", 2018),
    "Arizona Summit Law School": (r"^(ARIZONA SUMMIT|PHOENIX SCHOOL OF LAW)", 2020),
    "Concordia University School of Law": (r"^CONCORDIA", 2020),
    "Valparaiso University School of Law": (r"^VALPARAISO", 2020),
    "Whittier Law School": (r"^WHITTIER", 2020),
    "Florida Coastal School of Law": (r"^FLORIDA COASTAL", 2023),
}
WITHDRAWN_OPEN = {
    "University of La Verne College of Law": (r"LA VERNE", 2023),
    "Thomas Jefferson School of Law": (r"^THOMAS JEFFERSON", 2023),
}


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        return None


def sheet(path: Path, title_rx: str | None = None):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        if title_rx and not re.search(title_rx, ws.title):
            continue
        it = ws.iter_rows(values_only=True)
        head = [("" if c is None else str(c).strip()) for c in next(it)]
        out.append((ws.title, head, [dict(zip(head, r)) for r in it if r and r[0]]))
    return out


def col(head, *names):
    for n in names:
        if n in head:
            return n
    raise SystemExit(f"None of {names} in the header {head[:12]}... Nothing recorded.")


def pct_scale(v):
    """Rates stored as 0-1 or as 0-100 are put on 0-100."""
    return None if v is None else (v * 100 if v <= 1.0 else v)


def build() -> tuple[dict, list]:
    data = defaultdict(lambda: defaultdict(dict))   # measure -> year -> school -> value
    notes = []
    for y in range(2011, 2017):
        f = RAW / f"509 {y} bar passage.xlsx"
        for title, head, rows in sheet(f):
            sc, ry, ey = col(head, "School Name"), col(head, "Reporting Year"), col(head, "Exam Year")
            pc, dc = col(head, "Composite Avg. School Pass %"), col(head, "Composite Avg. Pass Diff. %")
            for r in rows:
                if str(r[ry]).strip() != str(y):
                    continue
                e = int(num(r[ey]))
                name = str(r[sc]).strip()
                data["first-time bar passage"][e].setdefault(name, pct_scale(num(r[pc])))
                data["bar passage difference from state"][e].setdefault(name, num(r[dc]))
    for y in range(2018, 2027):
        f = RAW / f"bar passage {y} first time.xlsx"
        if not f.exists():
            continue
        for title, head, rows in sheet(f, r"FirstTimeBarPassage"):
            sc = col(head, "School Name", "SchoolName")
            gy = next((h for h in head if h in ("Graduate Year", "GraduateYear")), None)
            fixed = None
            if gy is None:   # some years put the graduate year in a column name ("Graduates In 2022")
                m = next((re.search(r"(\d{4})", h) for h in head if re.match(r"(?i)graduates in \d{4}", h)), None)
                t = re.search(r"_(\d{4})$", title)
                fixed = int(m.group(1)) if m else int(t.group(1)) if t else None
                if fixed is None:
                    raise SystemExit(f"{f.name} {title}: no graduate year found. Nothing recorded.")
                notes.append(f"{f.name} {title}: graduate year {fixed} read from the column names or sheet title")
            pc = col(head, "AvgSchoolPassPercent*", "AvgSchoolPassPercent")
            dc = col(head, "TotalDifferencePercent***", "TotalDifferencePercent")
            for r in rows:
                g = num(r[gy]) if gy else fixed
                if g is None:
                    continue
                name = str(r[sc]).strip()
                data["first-time bar passage"][int(g)][name] = pct_scale(num(r[pc]))
                data["bar passage difference from state"][int(g)][name] = num(r[dc])
    for y in range(2011, 2026):
        f = RAW / f"employment {y}.xlsx"
        if not f.exists():
            continue
        for title, head, rows in sheet(f):
            sc = col(head, "SchoolName", "School Name")
            jc = col(head, "Employed_BarPassageRequiredFTLT", "Employed_BarAdmissionRequiredFTLT")
            tc = col(head, "Total_GraduatesNumber", "Total_GraduatesTotal")
            for r in rows:
                j, t = num(r[jc]), num(r[tc])
                if j is not None and t:
                    data["employment"][y][str(r[sc]).strip()] = 100 * j / t
    for y in range(2011, 2026):
        f = RAW / f"509 {y} attrition.xlsx"
        if f.exists():
            for title, head, rows in sheet(f):
                sc = col(head, "School Name", "School List", "SchoolName")
                for r in rows:
                    if y <= 2016:
                        v = num(r[col(head, "%1st Year")])
                    elif y == 2017:
                        v = num(r[col(head, "Total 1L %")])
                    else:
                        a = num(r[col(head, "AcadAttrition_TotalJD1Percentage", "AcademicAttrition_TotalJD1Percentage")])
                        o = num(r[col(head, "OtherAttrition_TotalJD1Percentage")])
                        v = None if a is None and o is None else (a or 0) + (o or 0)
                    if v is not None:
                        data["first-year attrition"][y][str(r[sc]).strip()] = pct_scale(v) if y <= 2017 else v
        f = RAW / f"509 {y} enrollment.xlsx"
        if f.exists():
            for title, head, rows in sheet(f):
                sc = col(head, "School Name", "School List", "SchoolName")
                ec = col(head, "#Total FY", "Total 1L Total", "TotalJD1Total")
                for r in rows:
                    v = num(r[ec])
                    if v is not None:
                        data["first-year enrollment"][y][str(r[sc]).strip()] = v
    wind = defaultdict(list)
    for y, by in data["first-year enrollment"].items():
        for name, v in by.items():
            if v == 0:
                wind[name].append(y)
                data["first-year attrition"][y][name] = None
                by[name] = None
    notes.append("A year with no first-year class (enrollment 0: the school was winding down) has its enrollment and "
                 "attrition set to missing, and is listed under 'years with no entering class'.")
    notes.append("The ABA compilations are generated from the ABA's current records, and they omit some schools from "
                 "some of their last reporting years after the school lost approval (for example, Arizona Summit, "
                 "Valparaiso and Whittier have no employment rows after the class of 2017, and La Verne and Thomas "
                 "Jefferson have few rows after 2019, though all were still approved then). Missing years are a gap "
                 "in the source, concentrated in the years just before an ending.")
    data["_wind"] = wind
    notes.append("Attrition from 2018 is academic plus other attrition (as percentages); 2011-2017 use the file's own "
                 "first-year attrition percentage, which can include transfers; percentiles are within each year.")
    return data, notes


def percentile(values: dict, name: str):
    x = values.get(name)
    if x is None:
        return None
    vs = [v for v in values.values() if v is not None]
    below = sum(v < x for v in vs)
    ties = sum(v == x for v in vs)
    return round(100 * (below + 0.5 * ties) / len(vs), 1)


def main() -> None:
    data, notes = build()
    wind = data.pop("_wind")
    every = {n for m in data.values() for yr in m.values() for n in yr}
    out_closed, out_open, unmatched = {}, {}, []
    for group, target in ((CLOSED, out_closed), (WITHDRAWN_OPEN, out_open)):
        for label, (rx, end) in group.items():
            matched = sorted(n for n in every if re.search(rx, n, re.I))
            if not matched:
                unmatched.append(label)
                continue
            rec = {"names in the ABA files": matched, "ending year": end, "years": {},
                   "years with no entering class": sorted({y for n in matched for y in wind.get(n, [])})}
            for y in range(end - 5, end):
                row = {}
                for m, by_year in data.items():
                    vals = by_year.get(y, {})
                    n = next((nm for nm in matched if nm in vals), None)
                    row[m] = None if n is None else {"value": None if vals[n] is None else round(vals[n], 2),
                                                     "percentile among ABA schools": percentile(vals, n),
                                                     "schools reporting": sum(v is not None for v in vals.values())}
                rec["years"][str(y)] = row
            last3 = [str(y) for y in range(end - 3, end)]
            low, have = 0, 0
            for y in last3:
                r = rec["years"][y]
                if any(r.get(m) and r[m]["value"] is not None for m in ("first-time bar passage", "employment")):
                    have += 1
                if any(r.get(m) and r[m]["percentile among ABA schools"] is not None and r[m]["percentile among ABA schools"] <= 10
                       for m in ("first-time bar passage", "employment")):
                    low += 1
            rec["years in the bottom decile on bar passage or employment, of the three before the ending"] = low
            rec["of those three years, years with a bar passage or employment value"] = have
            rec["expectation met (two or more of three)"] = low >= 2
            target[label] = rec
    met = [k for k, v in out_closed.items() if v["expectation met (two or more of three)"]]
    OUT.write_text(json.dumps({
        "record": "Item 12: ABA 509 law-school record (descriptive, not a test); Amendments 8, 12 and 13",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "expectation (Amendment 8)": ("each closed school sat in the bottom decile on first-time bar passage or on "
                                      "employment in at least two of the three years before it closed"),
        "closed schools meeting it": f"{len(met)} of {len(out_closed)}", "meeting it": met,
        "closed schools": out_closed,
        "approval withdrawn, still open (their own group)": out_open,
        "not found in the ABA files": unmatched,
        "years covered by measure": {m: sorted(by_year) for m, by_year in data.items()},
        "percentile": "share of schools reporting that year with a lower value, ties counted half; higher attrition "
                      "is worse, so a high attrition percentile is the unfavorable end",
        "notes": notes}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"met": f"{len(met)} of {len(out_closed)}", "unmatched": unmatched}, indent=1))


if __name__ == "__main__":
    main()
