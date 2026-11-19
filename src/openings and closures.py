"""
Openings against closures, from the IPEDS header files (Paper 1; descriptive).

The question. In an anchored sector, Tell found that closure concentrates
in small, unanchored institutions. This check asks what happens to those
segments over time: whether closures in a segment are replaced by new
institutions (churn, sustained by demand) or not (the segment shrinks).
The expectation, written down before any count was seen: the small
for-profit segment refills, with new for-profit institutions opening
roughly as fast as others close, while small private nonprofits, and
liberal arts colleges especially, close with few or no new institutions
replacing them. This is descriptive: the outcomes are public, nothing is
fitted, and no verdict is drawn; the counts are reported as they come out.

What is counted, year by year, from HD{first} to the latest header file
NCES serves:

  frame          degree-granting institutions (DEGGRANT 1) in sectors 1 to
                 6: public, private nonprofit and for-profit, four-year and
                 two-year. Four-year institutions (sectors 1 to 3) are the
                 tracker's own frame; two-year institutions are reported
                 beside them.
  opening        an institution in the frame in HD{y} whose unit ID appears
                 in no earlier header file read here, in any sector. The
                 first file read has no earlier file, so openings are
                 counted from the second file on.
  successor      a new unit ID that some other institution's record names
                 as its successor (NEWID): a merger or reorganization, not
                 a new institution. Counted separately, never as an
                 opening.
  closure        an institution in the frame whose record shows, in some
                 header file, a closure date (CLOSEDAT), a year of deletion
                 (DEATHYR) or ACT = D, or that is present in one file and
                 absent from every later one with no such record; an event
                 is voided if the institution appears again as active
                 (ACT = A or R) in a later file, as in the tracker's own
                 outcome coding (sampling protocol v2.md). Year: the first
                 header file recording a standing event, or for an
                 unrecorded disappearance, the first file it is missing
                 from.
  merger         as closure, but the standing record names a successor
                 (NEWID other than itself). Counted separately from
                 closures, so replacement can be read with and without
                 mergers.
  stock          institutions in the frame in each header file.

Groups: control (public, private nonprofit, for-profit) by level (four-year,
two-year), each split by size band from INSTSIZE (under 1,000; 1,000 to
4,999; 5,000 or more; unknown). An opening takes the first size band its
own records report, a closure the last band reported before or at its
closure year, and the stock each year's band. Liberal arts colleges are
read from the Carnegie basic classification in the header files (value 21,
baccalaureate arts and sciences, in CCBASIC, C15BASIC, C18BASIC and
C21BASIC; the newest of these present in a record is used) and reported as
an extra group within private nonprofit four-year institutions. A new
institution usually has no Carnegie classification in its first year (the
classification is revised only every few years), so an opening is read as
liberal arts from the first record of its own that carries a
classification, as its size is; a closure from the last record carrying
one at or before its closure year. The liberal arts stock is read from
each year's records, and colleges entering or leaving the group because
Carnegie reclassified them are counted separately ("reclassified in",
"reclassified out"), so that a reclassification is never read as an
opening or a closure. HD2004 carries no classification, so the group's
stock starts in HD2005.

For every group and the whole span: openings, successors, closures,
mergers, and the replacement ratio (openings divided by closures, and
divided by closures plus mergers). Checks: institutions read per file
(every file must yield at least 3,000 or the run stops and records
nothing), which columns each file has, how many openings the file itself
marks new (ACT = N), events voided by reappearance, and unrecorded
disappearances in the last file (which cannot yet be told apart from a
late return, so they are listed separately).

Output: data/openings and closures/results.json.

Usage (GitHub Actions only, via openings_closures.yml):
    cd src
    python "openings and closures.py" --first 2004
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import v2_training_outcomes as coding

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "openings and closures"
OUT_PATH = OUT_DIR / "results.json"
MIN_ROWS = 3_000
LAST_TRIED = 2026

KEEP = ("UNITID", "INSTNM", "SECTOR", "CONTROL", "DEGGRANT", "INSTSIZE", "ACT", "CLOSEDAT", "DEATHYR", "NEWID",
        "CCBASIC", "C15BASIC", "C18BASIC", "C21BASIC")
CARNEGIE = ("C21BASIC", "C18BASIC", "C15BASIC", "CCBASIC")   # newest first
LIBERAL_ARTS = 21
CONTROL = {"1": "public", "2": "private nonprofit", "3": "for-profit"}
LEVEL = {"1": "four-year", "2": "four-year", "3": "four-year", "4": "two-year", "5": "two-year", "6": "two-year"}
SIZE = {1: "under 1,000", 2: "1,000 to 4,999", 3: "5,000 or more", 4: "5,000 or more", 5: "5,000 or more"}
BANDS = ("under 1,000", "1,000 to 4,999", "5,000 or more", "unknown")


def number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_table(text: str) -> tuple[dict, list]:
    import csv
    import io
    reader = csv.DictReader(io.StringIO(text))
    fields = {f: f.strip().lstrip("﻿").lstrip("ï»¿").strip().upper()
              for f in (reader.fieldnames or [])}
    out = {}
    for r in reader:
        row = {fields[k]: (v or "").strip() for k, v in r.items() if k in fields}
        u = row.get("UNITID", "")
        if u:
            out[u] = {k: row.get(k, "") for k in KEEP if k != "UNITID"}
    return out, sorted(set(fields.values()))


def in_frame(r: dict) -> bool:
    return r.get("DEGGRANT", "") == "1" and r.get("SECTOR", "") in LEVEL and r.get("CONTROL", "") in CONTROL


def group(r: dict) -> str:
    return f"{CONTROL[r['CONTROL']]} {LEVEL[r['SECTOR']]}"


def band(r: dict | None) -> str | None:
    if r is None:
        return None
    n = number(r.get("INSTSIZE", ""))
    return SIZE.get(int(n)) if n is not None and n == int(n) else None


def liberal_arts(r: dict) -> bool | None:
    for c in CARNEGIE:
        n = number(r.get(c, ""))
        if n is not None and n > 0:
            return int(n) == LIBERAL_ARTS
    return None


def has_closure_date(v: str) -> bool:
    v = (v or "").strip()
    n = number(v)
    if not v or (n is not None and n < 0):
        return False
    return bool(re.search(r"\d{4}", v))


def exit_of(unitid: str, rows: dict, years: list) -> dict | None:
    """rows: {year: row} for the years present. Returns the standing exit, or None."""
    events = []
    for y in sorted(rows):
        r = rows[y]
        if has_closure_date(r.get("CLOSEDAT", "")):
            events.append(("a", y))
        dy = number(r.get("DEATHYR", ""))
        if (dy is not None and dy > 0) or r.get("ACT", "").upper() == "D":
            events.append(("b", y))
        nid = r.get("NEWID", "").strip()
        if number(nid) is not None and number(nid) > 0 and nid != unitid:
            events.append(("c", y))
    voided, standing = 0, []
    for g, y in events:
        if any(z > y and rows[z].get("ACT", "").upper() in ("A", "R") for z in rows):
            voided += 1
        else:
            standing.append((g, y))
    if standing:
        y = min(e[1] for e in standing)
        grounds = sorted({g for g, z in standing})
        return {"year": y, "merger": "c" in grounds, "grounds": grounds, "voided": voided, "unrecorded": False}
    last = max(rows)
    if last < years[-1]:
        return {"year": years[years.index(last) + 1], "merger": False, "grounds": ["d"], "voided": voided,
                "unrecorded": True}
    return {"voided": voided} if voided else None


def tally() -> dict:
    return {"openings": 0, "successors": 0, "closures": 0, "mergers": 0, "reclassified in": 0,
            "reclassified out": 0}


def ratios(t: dict) -> dict:
    out = dict(t)
    out["replacement (openings per closure)"] = round(t["openings"] / t["closures"], 3) if t["closures"] else None
    m = t["closures"] + t["mergers"]
    out["replacement (openings per closure or merger)"] = round(t["openings"] / m, 3) if m else None
    return out


def analyse(tables: dict) -> dict:
    years = sorted(tables)
    first_seen, history = {}, defaultdict(dict)
    successors = set()
    for y in years:
        for u, r in tables[y].items():
            first_seen.setdefault(u, y)
            history[u][y] = r
            nid = r.get("NEWID", "").strip()
            if number(nid) is not None and number(nid) > 0 and nid != u:
                successors.add(str(int(number(nid))))

    def key_sets(r, b, la=None):
        g = group(r)
        keys = [(g, "all sizes"), (g, b or "unknown")]
        if la is None:
            la = liberal_arts(r)
        if g == "private nonprofit four-year" and la:
            keys += [("private nonprofit four-year, liberal arts", "all sizes"),
                     ("private nonprofit four-year, liberal arts", b or "unknown")]
        return keys

    by_year = defaultdict(lambda: defaultdict(lambda: defaultdict(tally)))
    stock = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    act_n = {y: {"marked new (ACT = N) in frame": 0, "of them counted as openings": 0} for y in years}
    checks = {"events voided by reappearance as active": 0, "unrecorded disappearances": 0,
              "unrecorded disappearances first missing from the latest file": 0,
              "openings whose size is never reported": 0, "closures whose size is never reported": 0,
              "liberal arts reclassifications": 0}
    listed = {"openings": [], "closures": [], "mergers": []}

    for y in years:
        for u, r in tables[y].items():
            if not in_frame(r):
                continue
            for k in key_sets(r, band(r)):
                stock[y][k[0]][k[1]] += 1
            if r.get("ACT", "").upper() == "N":
                act_n[y]["marked new (ACT = N) in frame"] += 1

    la_group = "private nonprofit four-year, liberal arts"
    for i in range(1, len(years)):
        y0, y1 = years[i - 1], years[i]
        for u, r1 in tables[y1].items():
            r0 = tables[y0].get(u)
            if r0 is None or not (in_frame(r0) and in_frame(r1)):
                continue
            if group(r0) != "private nonprofit four-year" or group(r1) != "private nonprofit four-year":
                continue
            a, c = liberal_arts(r0), liberal_arts(r1)
            if a is None or c is None or a == c:
                continue
            kind = "reclassified in" if c else "reclassified out"
            b = band(r1) or "unknown"
            by_year[y1][la_group]["all sizes"][kind] += 1
            by_year[y1][la_group][b][kind] += 1
            checks["liberal arts reclassifications"] += 1

    for u, rows in history.items():
        fy = first_seen[u]
        if fy != years[0] and in_frame(rows[fy]):
            r = rows[fy]
            b = next((band(rows[z]) for z in sorted(rows) if band(rows[z])), None)
            if b is None:
                checks["openings whose size is never reported"] += 1
            la = next((liberal_arts(rows[z]) for z in sorted(rows) if liberal_arts(rows[z]) is not None), None)
            kind = "successors" if u in successors else "openings"
            for k in key_sets(r, b, la):
                by_year[fy][k[0]][k[1]][kind] += 1
            if kind == "openings":
                if r.get("ACT", "").upper() == "N":
                    act_n[fy]["of them counted as openings"] += 1
                listed["openings"].append({"unitid": u, "name": r.get("INSTNM", ""), "year": fy,
                                           "group": group(r), "size": b or "unknown"})
        e = exit_of(u, rows, years)
        if not e:
            continue
        checks["events voided by reappearance as active"] += e["voided"]
        if "year" not in e:
            continue
        before = [z for z in sorted(rows) if z <= e["year"]] or sorted(rows)
        r = rows[before[-1]]
        if not in_frame(r):
            framed = [z for z in before if in_frame(rows[z])]
            if not framed:
                continue
            r = rows[framed[-1]]
        b = next((band(rows[z]) for z in reversed(before) if band(rows[z])), None)
        if b is None:
            checks["closures whose size is never reported"] += 1
        la = next((liberal_arts(rows[z]) for z in reversed(before) if liberal_arts(rows[z]) is not None), None)
        if e["unrecorded"]:
            checks["unrecorded disappearances"] += 1
            if e["year"] == years[-1]:
                checks["unrecorded disappearances first missing from the latest file"] += 1
        kind = "mergers" if e["merger"] else "closures"
        for k in key_sets(r, b, la):
            by_year[e["year"]][k[0]][k[1]][kind] += 1
        listed[kind].append({"unitid": u, "name": r.get("INSTNM", ""), "year": e["year"], "group": group(r),
                             "size": b or "unknown", "grounds": e["grounds"]})

    groups = sorted({g for y in stock for g in stock[y]} | {g for y in by_year for g in by_year[y]})
    yearly, totals = {}, {}
    for g in groups:
        yearly[g], totals[g] = {}, {}
        for s in ("all sizes",) + BANDS:
            rows_out, tot = [], tally()
            for y in years:
                t = by_year[y][g][s]
                rows_out.append({"year": y, "stock": stock[y][g][s], **t})
                if y != years[0]:
                    for k in tot:
                        tot[k] += t[k]
            if any(r["stock"] or r["openings"] or r["closures"] or r["mergers"] or r["successors"] for r in rows_out):
                yearly[g][s] = rows_out
                totals[g][s] = ratios(tot)
    for k in listed:
        listed[k].sort(key=lambda d: (d["year"], d["group"], d["unitid"]))
    return {"totals over the span (openings counted from the second file)": totals, "by year": yearly,
            "checks": {**checks, "openings the file itself marks new": act_n}, "institutions": listed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2004)
    a = ap.parse_args()
    files, not_served = {}, []
    for y in range(a.first, LAST_TRIED + 1):
        try:
            files[y] = coding.download_hd(y)
        except SystemExit as e:
            if y < 2025:
                raise SystemExit(f"HD{y} could not be downloaded ({e}); a gap in the middle of the span would "
                                 "make openings and closures wrong. Nothing recorded.")
            not_served.append(f"HD{y}")
    tables, columns = {}, {}
    for y, f in files.items():
        tables[y], cols = read_table(f["csv"])
        columns[f"HD{y}"] = {c: c in cols for c in KEEP}
        if len(tables[y]) < MIN_ROWS:
            raise SystemExit(f"HD{y} yielded {len(tables[y])} institutions (fewer than {MIN_ROWS}); it was not read "
                             "correctly. Nothing recorded.")
        for c in ("SECTOR", "CONTROL", "DEGGRANT"):
            if c not in cols:
                raise SystemExit(f"HD{y} has no {c} column; the frame cannot be read. Nothing recorded.")
    res = analyse(tables)
    out = {
        "note": "Descriptive (Paper 1): openings against closures by sector and size, year by year, from the "
                "IPEDS header files. Outcomes are public; nothing is fitted and no verdict is drawn.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "header files used": {f"HD{y}": {"url": f["url"], "file": f["file"], "zip sha256": f["zip sha256"],
                                         "institutions read": len(tables[y])} for y, f in files.items()},
        "header files not served": not_served,
        "columns found": columns,
        **res,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    t = res["totals over the span (openings counted from the second file)"]
    for g in sorted(t):
        print(g, json.dumps(t[g].get("all sizes")))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
