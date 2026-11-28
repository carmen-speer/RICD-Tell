"""
Item 23k follow-up: the Department of Education's 90/10 revenue shares as an
outside check on 23k's federal share for for-profit colleges (approved
November 27, 2026). Descriptive; nothing is fitted.

Reads the exact copies committed by the field check (data/ninety_ten/raw/,
award years 2008-09 to 2024-25) in the two layouts that check recorded:

  2014-15 on       per OPEID: Title IV revenue (numerator) and total revenue
                   (denominator) for the institution's fiscal year ending in
                   the award year, and the 90/10 percentage
  2008-09 to 13-14 per OPEID: the 90/10 percentage and Title IV funding
                   received in the award year (no revenue denominator)

and sets them beside 23k's figures (data/grid_strain/college_payers.csv),
matched through each campus's OPEID in the IPEDS header files and summed
over the campuses that share one (the 90/10 report is per OPEID). Award year
t-1 to t is set against IPEDS fiscal year t.

Two of 23k's measures are compared, both over 23k's revenue (spending less
what is left uncovered):
  federal share             federal appropriations and federal student
                            grants (23k's headline channel)
  federal share with loans  the same plus undergraduate federal loans (the
                            90/10 numerator counts loans; IPEDS student aid
                            has no graduate or parent loans, so this still
                            reads low)

Writes data/ninety_ten/:
  ninety_ten.csv     per OPEID and award year, as published
  comparison.csv     per OPEID and fiscal year: the 90/10 share and 23k's
  results.json       dollar-weighted sector shares by year (from 2014-15;
                     the numerator widens from fiscal years beginning in
                     2023, under the American Rescue Plan Act of 2021),
                     median percentages (all years), the match rate, files read

Usage (GitHub Actions only, via ninety_ten.yml):
    cd src
    python ninety_ten.py
"""
from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = ROOT / "data" / "ninety_ten" / "raw"
OUT = ROOT / "data" / "ninety_ten"
PAYERS = ROOT / "data" / "grid_strain" / "college_payers.csv"

_e = importlib.util.spec_from_file_location("et", HERE / "ending types.py")
et = importlib.util.module_from_spec(_e)
_e.loader.exec_module(et)


def text(c) -> str:
    return "" if pd.isna(c) else str(c).strip()


def number(c) -> float | None:
    s = text(c).replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        return None


def opeid(c) -> str | None:
    s = text(c).replace(".0", "")
    s = re.sub(r"\D", "", s)
    return s.zfill(8) if 5 <= len(s) <= 8 else None


def parse(path: Path) -> list[dict]:
    """Rows of one award year's file, by the heading row naming an OPEID."""
    ay = path.stem                                   # e.g. 2016-2017
    fy = int(ay.split("-")[1])                       # award year 2016-17 -> fiscal 2017
    sheets = pd.read_excel(path, sheet_name=None, header=None)
    out = []
    for name, df in sheets.items():
        grid = df.values.tolist()
        head = next((i for i, r in enumerate(grid[:40]) if any(re.search(r"OPE\s*ID", text(c), re.I) for c in r)), None)
        if head is None or len(grid) < 100:
            continue
        hdr = [text(c).lower() for c in grid[head]]
        col = lambda pat: next((j for j, h in enumerate(hdr) if re.search(pat, h)), None)
        j_ope, j_name, j_pct = col(r"ope\s*id"), col(r"school name|institution name"), col(r"percentage")
        j_num, j_den = col(r"title iv revenue|\(numerator\)"), col(r"total revenue|\(denominator\)")
        # older layout: the last column holds Title IV funding received in this award year
        j_fund = len(hdr) - 1 if j_num is None else None
        for r in grid[head + 1:]:
            o = opeid(r[j_ope]) if j_ope is not None else None
            pct = number(r[j_pct]) if j_pct is not None else None
            if not o or pct is None:
                continue
            rec = {"OPEID": o, "award year": ay, "fiscal year": fy, "name": text(r[j_name]) if j_name is not None else "",
                   "90/10 percentage": pct}
            if j_num is not None and j_den is not None:
                rec["Title IV revenue"] = number(r[j_num])
                rec["total revenue"] = number(r[j_den])
            else:
                rec["Title IV funding received"] = number(r[j_fund])
            out.append(rec)
    return out


def main() -> None:
    if not PAYERS.exists():
        raise SystemExit("data/grid_strain/college_payers.csv is not committed yet; run item 23k first. Nothing recorded.")
    rows, files = [], {}
    for p in sorted(RAW.glob("*.xls*")):
        got = parse(p)
        files[p.name] = len(got)
        rows += got
        print(p.name, len(got), flush=True)
    if not rows:
        raise SystemExit("No 90/10 rows parsed. Nothing recorded.")

    hd, hd_used, _ = et.headers()
    unit_to_ope = {}
    for y in sorted(hd):
        for u, r in hd[y].items():
            o = opeid(r.get("OPEID", ""))
            if o:
                unit_to_ope[u] = o                    # latest header file wins

    ours = defaultdict(lambda: defaultdict(float))
    with open(PAYERS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["sector"] != "for-profit":
                continue
            o = unit_to_ope.get(r["unitid"])
            if not o:
                continue
            fy = int(r["fiscal year"])
            g = lambda k: float(r[f"{k} (nominal $)"] or 0)
            k = (o, fy)
            ours[k]["revenue"] += g("W") - g("paid by uncovered")
            ours[k]["federal"] += g("paid by federal")
            ours[k]["loans"] += g("memo: undergraduate federal loans")
            ours[k]["campuses"] += 1

    comp = []
    for r in rows:
        o = ours.get((r["OPEID"], r["fiscal year"]))
        if not o or o["revenue"] <= 0:
            continue
        comp.append({**r, "campuses matched": int(o["campuses"]),
                     "23k revenue": round(o["revenue"]), "23k federal": round(o["federal"]),
                     "23k undergraduate federal loans": round(o["loans"]),
                     "23k federal share": round(o["federal"] / o["revenue"], 4),
                     "23k federal share with loans": round((o["federal"] + o["loans"]) / o["revenue"], 4)})

    with open(OUT / "ninety_ten.csv", "w", newline="", encoding="utf-8") as f:
        keys = ["OPEID", "award year", "fiscal year", "name", "90/10 percentage", "Title IV revenue", "total revenue",
                "Title IV funding received"]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    if comp:
        with open(OUT / "comparison.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(comp[0]))
            w.writeheader()
            w.writerows(comp)

    by_year = {}
    for fy in sorted({r["fiscal year"] for r in rows}):
        pub = [r for r in rows if r["fiscal year"] == fy]
        cm = [c for c in comp if c["fiscal year"] == fy]
        e = {"institutions in the report": len(pub), "matched to 23k": len(cm),
             "median 90/10 percentage, all reported": round(statistics.median(r["90/10 percentage"] for r in pub), 2)}
        if cm:
            e["median 90/10 percentage, matched"] = round(statistics.median(c["90/10 percentage"] for c in cm), 2)
            e["median 23k federal share, matched (%)"] = round(100 * statistics.median(c["23k federal share"] for c in cm), 2)
            e["median 23k federal share with loans, matched (%)"] = round(100 * statistics.median(c["23k federal share with loans"] for c in cm), 2)
        dw = [c for c in cm if c.get("Title IV revenue") and c.get("total revenue")]
        if dw:
            e["dollar-weighted 90/10 share, matched (%)"] = round(100 * sum(c["Title IV revenue"] for c in dw) / sum(c["total revenue"] for c in dw), 2)
            e["dollar-weighted 23k federal share, same institutions (%)"] = round(100 * sum(c["23k federal"] for c in dw) / sum(c["23k revenue"] for c in dw), 2)
            e["dollar-weighted 23k federal share with loans, same institutions (%)"] = round(
                100 * sum(c["23k federal"] + c["23k undergraduate federal loans"] for c in dw) / sum(c["23k revenue"] for c in dw), 2)
        by_year[fy] = e
    (OUT / "results.json").write_text(json.dumps({
        "note": ("Outside check on item 23k's for-profit federal share. The Department's 90/10 share counts all Title IV "
                 "aid, loans included, over the institution's total revenue; 23k's headline federal share counts "
                 "federal appropriations and federal student grants, and the second figure adds undergraduate federal "
                 "loans (graduate and parent loans are not in IPEDS student aid). Award year t-1 to t is set against "
                 "IPEDS fiscal year t; 90/10 reports are per OPEID, so 23k's campuses sharing one are summed. The 90/10 "
                 "numerator widened for institutional fiscal years beginning on or after January 1, 2023 (American "
                 "Rescue Plan Act of 2021: all federal education funds, including veterans' and military benefits, "
                 "count), so award years 2023-24 and 2024-25 are not comparable with earlier years on that line."),
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "by fiscal year": by_year, "rows parsed by file": files, "header files used": hd_used},
        indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps(by_year, indent=1))


if __name__ == "__main__":
    main()
