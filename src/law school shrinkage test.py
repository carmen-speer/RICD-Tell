"""
Item 12, larger law-school test ("channel selection protocol.md",
Amendment 14): do schools in the bottom decile on first-time bar passage
or employment suffer severe enrollment collapse within three years more
often than other schools?

Reads the committed ABA compilations through the reader of
"law school record.py". Units are school-years (509 reporting years 2012 to
2022, first-year class of 25 or more). Flagged: bottom decile on bar
passage (graduate year y-1) or employment (class of y-1). Outcome: the
first-year class in y+3 over the class in y, relative to the same ratio for
all schools reporting both years, is 0.6 or lower, or the school is one of
the closed schools of Amendment 12 ending in (y, y+3]. Schools missing in
y+3 for any other reason are left out of that year. Development years
2012-2016 are reported only; the verdict rests on 2017-2022.

Output: data/v4 channels/law schools/law school shrinkage test.json

Usage:
    cd src
    python "law school shrinkage test.py"
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lr", HERE / "law school record.py")
lr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lr)
OUT = lr.DIR / "law school shrinkage test.json"
SEED, BOOT, MIN_CLASS, CUT = 20261128, 2000, 25, 0.6
DEV, TEST = range(2012, 2017), range(2017, 2023)

# New-style names (2023 on) whose normalized key does not match the old one: renamed schools, by name only.
RENAMED = {
    "Arkansas at Little Rock, University of": "ARKANSAS, LITTLE ROCK, UNIVERSITY OF",
    "Arkansas, University of": "ARKANSAS, FAYETTEVILLE, UNIVERSITY OF",
    "Buffalo, University at": "UNIVERSITY OF BUFFALO-SUNY",
    "California-San Francisco, University of": "UNIVERSITY OF CALIFORNIA COLLEGE OF THE LAW, SAN FRANCISCO",
    "Capital University Law School": "CAPITAL UNIVERSITY",
    "Cardozo, Yeshiva University": "CARDOZO SCHOOL OF LAW",
    "Chicago-Kent, Illinois Institute of Technology": "CHICAGO-KENT COLLEGE OF LAW-IIT",
    "City University of New York, University of": "CITY UNIVERSITY OF NEW YORK",
    "District of Columbia, University of": "DISTRICT OF COLUMBIA",
    "Illinois-Chicago, University of": "UNIVERSITY OF ILLINOIS CHICAGO SCHOOL OF LAW",
    "Jacksonville University": "JACKSONVILLE UNIVERSITY, COLLEGE OF LAW",
    "Lewis & Clark Law School": "LEWIS AND CLARK COLLEGE",
    "Lincoln Memorial University": "LINCOLN MEMORIAL",
    "Mississippi Christian University": "MISSISSIPPI COLLEGE",
    "Mitchell/Hamline School of Law": "MITCHELL|HAMLINE",
    "New Hampshire, University of": "NEW HAMPSHIRE UNIVERSITY OF",
    "North Texas at Dallas, University of": "UNT DALLAS COLLEGE OF LAW",
    "Pacific, University of the": "MCGEORGE SCHOOL OF LAW",
    "Penn State Dickinson Law": "PENNSYLVANIA STATE - DICKINSON LAW",
    "Penn State University": "PENNSYLVANIA STATE - PENN STATE LAW",
    "Pontifical Catholic University of Puerto Rico": "PONTIFICAL CATHOLIC UNIVERSITY OF P.R.",
    "Southern Illinois University": "SOUTHERN ILLINOIS UNIVERSITY-CARBONDALE",
    "St. Thomas University (Miami)": "ST. THOMAS UNIVERSITY (FLORIDA)",
    "St. Thomas, (Minneapolis) University of": "ST. THOMAS, UNIVERSITY OF (MINNESOTA)",
    "Texas, University of": "TEXAS AT AUSTIN, UNIVERSITY OF",
    "Washington University (St. Louis)": "WASHINGTON UNIVERSITY",
    "Western State, Westcliff University": "WESTERN STATE COLLEGE OF LAW",
    "Widener University Commonwealth Law School": "WIDENER-COMMONWEALTH",
    "Widener University Delaware Law School": "WIDENER UNIVERSITY-DELAWARE",
    "William & Mary": "WILLIAM AND MARY LAW SCHOOL",
    "Cooley Law School": "THOMAS M. COOLEY LAW SCHOOL",
}
# Old-style names that changed within the old style (same school).
OLD_ALIASES = {"WESTERN MICHIGAN UNIVERSITY": "THOMAS M. COOLEY LAW SCHOOL",
               "ATLANTA'S JOHN MARSHALL LAW SCHOOL - SAVANNAH": "ATLANTA'S JOHN MARSHALL LAW SCHOOL"}


def key(n: str) -> str:
    s = n.lower().replace("&", " and ")
    s = re.sub(r",\s*the\s+", ", ", s)
    m = re.match(r"^(.*?),\s*(university of|university at|college of)\s*(.*)$", s)
    if m:
        s = f"{m.group(2)} {m.group(1)} {m.group(3)}"
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\bthe\b", " ", s)
    return " ".join(s.split())


def canonical(data) -> tuple[dict, list]:
    names = {n for by in data.values() for v in by.values() for n in v if not n.startswith("*")}
    old = {n for n in names if n == n.upper()}
    by_key = {key(n): n for n in old}
    out, unmatched = {}, []
    for n in names:
        if n in old:
            out[n] = OLD_ALIASES.get(n, n)
        elif n in RENAMED:
            out[n] = OLD_ALIASES.get(RENAMED[n], RENAMED[n])
        elif key(n) in by_key:
            out[n] = OLD_ALIASES.get(by_key[key(n)], by_key[key(n)])
        else:
            out[n] = n          # a school that first appears in the new style
            unmatched.append(n)
    return out, sorted(unmatched)


def main() -> None:
    data, _ = lr.build()
    data.pop("_wind")
    canon, new_only = canonical(data)
    # re-key every measure by canonical name; zero enrollment kept as 0 (a year with no first-year class)
    raw_enr = defaultdict(dict)
    for y in range(2011, 2026):
        for title, head, rows in lr.sheet(lr.RAW / f"509 {y} enrollment.xlsx"):
            sc = lr.col(head, "School Name", "School List", "SchoolName")
            ec = lr.col(head, "#Total FY", "Total 1L Total", "TotalJD1Total")
            for r in rows:
                n = str(r[sc]).strip()
                v = lr.num(r[ec])
                if v is not None and not n.startswith("*"):
                    raw_enr[y][canon.get(n, n)] = v
    meas = {m: {y: {canon.get(n, n): v for n, v in by.items() if not n.startswith("*")} for y, by in data[m].items()}
            for m in ("first-time bar passage", "employment")}
    pct = {m: {y: {n: lr.percentile(v, n) for n in v} for y, v in by.items()} for m, by in meas.items()}
    closed = {}
    for label, (rx, end) in lr.CLOSED.items():
        for n in set(raw_enr[min(raw_enr)]) | {x for y in raw_enr for x in raw_enr[y]}:
            if re.search(rx, n, re.I):
                closed[n] = end
    rows = []
    for y in list(DEV) + list(TEST):
        a, b = raw_enr.get(y, {}), raw_enr.get(y + 3, {})
        both = [n for n in a if n in b and a[n] > 0]
        nat = sum(b[n] for n in both) / sum(a[n] for n in both)
        for n, c0 in a.items():
            if c0 < MIN_CLASS:
                continue
            end = closed.get(n)
            if end is not None and y < end <= y + 3:
                shrink = True
            elif n in b:
                shrink = (b[n] / c0) / nat <= CUT
            else:
                continue      # missing for another reason: left out
            pb = pct["first-time bar passage"].get(y - 1, {}).get(n)
            pe = pct["employment"].get(y - 1, {}).get(n)
            if pb is None and pe is None:
                continue
            low = min(p for p in (pb, pe) if p is not None)
            rows.append({"school": n, "year": y, "class": c0, "flagged": low <= 10, "score": 100 - low,
                         "shrink": shrink, "closed in window": end is not None and y < end <= y + 3})
    rng = np.random.default_rng(SEED)

    def summary(sel):
        f = [r for r in sel if r["flagged"]]
        o = [r for r in sel if not r["flagged"]]
        res = {"school-years": len(sel), "schools": len({r["school"] for r in sel}),
               "flagged school-years": len(f), "flagged that shrank": sum(r["shrink"] for r in f),
               "other school-years": len(o), "others that shrank": sum(r["shrink"] for r in o)}
        if not f or not o or not any(r["shrink"] for r in o):
            return res | {"note": "a group is empty or has no shrinkage; ratio not computed"}
        rf, ro = res["flagged that shrank"] / len(f), res["others that shrank"] / len(o)
        schools = sorted({r["school"] for r in sel})
        idx = defaultdict(list)
        for i, r in enumerate(sel):
            idx[r["school"]].append(i)
        y = np.array([r["shrink"] for r in sel], int)
        s = np.array([r["score"] for r in sel], float)
        fl = np.array([r["flagged"] for r in sel], bool)
        rr, aucs = [], []
        for _ in range(BOOT):
            ii = np.concatenate([idx[k] for k in rng.choice(schools, len(schools))])
            yf, yo = y[ii][fl[ii]], y[ii][~fl[ii]]
            if len(yf) and len(yo) and yo.mean() > 0:
                rr.append(yf.mean() / yo.mean())
            if 0 < y[ii].sum() < len(ii):
                aucs.append(roc_auc_score(y[ii], s[ii]))
        auc = roc_auc_score(y, s) if 0 < y.sum() < len(y) else None
        return res | {"shrinkage rate, flagged": rf, "shrinkage rate, others": ro, "rate ratio": rf / ro,
                      "rate ratio 95% interval (schools resampled)": [float(np.percentile(rr, 2.5)), float(np.percentile(rr, 97.5))],
                      "AUC of the continuous score": auc,
                      "AUC 95% interval": [float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))] if aucs else None}

    dev = [r for r in rows if r["year"] in DEV]
    test = [r for r in rows if r["year"] in TEST]
    out = {"development (2012-2016; reported only)": summary(dev), "test (2017-2022)": summary(test)}
    cuts = np.percentile([r["class"] for r in test], [100 / 3, 200 / 3])
    out["test, by first-year class size tercile"] = {
        name: summary([r for r in test if lo <= r["class"] < hi])
        for name, lo, hi in (("smallest third", 0, cuts[0]), ("middle third", cuts[0], cuts[1]), ("largest third", cuts[1], 1e9))}
    out["test, without the closed schools' ending windows (check)"] = summary([r for r in test if not r["closed in window"]])
    out["test-period collapses, by school and year"] = [
        {"school": r["school"], "year": r["year"], "flagged": r["flagged"], "closure": r["closed in window"]}
        for r in sorted(test, key=lambda r: (r["school"], r["year"])) if r["shrink"]]
    t = out["test (2017-2022)"]
    ci = t.get("rate ratio 95% interval (schools resampled)")
    verdict = ("supported" if ci and ci[0] > 1 else "in the predicted direction" if t.get("rate ratio", 0) > 1
               else "not supported")
    OUT.write_text(json.dumps({
        "test": "Item 12, larger law-school test (Amendment 14): bottom-decile outcomes and severe enrollment collapse",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict (test period)": verdict, **out,
        "closures counted as shrinkage": sorted({r["school"] for r in rows if r["closed in window"]}),
        "new-style names with no old match (schools first appearing from 2023)": new_only,
        "settings": {"minimum first-year class": MIN_CLASS, "relative shrink cut": CUT, "bootstrap": BOOT, "seed": SEED},
        "limitations": ["Missing years in the source (Amendment 13) are left out, which drops some of the last years "
                        "before an ending.", "School-years of one school are not independent; intervals resample schools."]},
        indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "test": t, "development": out["development (2012-2016; reported only)"]}, indent=1))


if __name__ == "__main__":
    main()
