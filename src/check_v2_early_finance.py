"""
Early-finance check for "sampling protocol v2.md" (before phase 2).

The training window reaches back to fiscal year 2004, earlier than any year
the live finance pipeline has parsed so far. This check confirms, before
any training institution is scored, that every finance file the window
needs is served by NCES and is read correctly.

It does two things.

1. For every finance form (private F2, public F1A, for-profit F3) and every
   fiscal year from 2004 through 2014, it downloads the file and records
   its table name, its number of rows, whether every column the pipeline
   reads is present, and the share of rows in which each of those columns
   holds a number.
2. For the first 20 institutions of the committed training draw, in slot
   order, it reads each institution's rows for those years exactly as the
   scoring pipeline does (fetch_live_data.parse_live_finance, plus the
   total-liabilities column the debt series uses) and checks each parsed
   year for plausibility: revenue and total expenses positive, and
   instruction and institutional support each no larger than total
   expenses.

Passing: every file is served, every column the pipeline reads is present
in every file, and no parsed year of any of the 20 institutions fails a
plausibility check. Whatever fails is listed, so that it can be handled
before training scoring begins, as the protocol requires.

Nothing here looks up any outcome. The result is written to
data/v2/early finance check.json.

Usage (GitHub Actions only, via check_v2_early_finance.yml):
    cd src
    python check_v2_early_finance.py --finance ../work/finance
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
from pathlib import Path

import fetch_live_data as fld
import v2_common as v2

OUT_PATH = v2.V2_DIR / "early finance check.json"
DRAW_PATH = v2.V2_DIR / "training draw.json"
N_INSTITUTIONS = 20
FIELDS = {"private": fld.PRIVATE_FINANCE_FIELDS, "public": fld.PUBLIC_FINANCE_FIELDS,
          "forprofit": fld.FORPROFIT_FINANCE_FIELDS}
PARSED = ("revenue", "expenses", "institutional_support", "instruction", "total_liabilities")


def number(v) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--finance", required=True)
    args = ap.parse_args()
    if not DRAW_PATH.exists():
        raise SystemExit("The training draw (data/v2/training draw.json) has to be committed first.")

    win = v2.WINDOWS["training"]
    manifest, missing = v2.prefetch_finance(args.finance, win["start_year"], win["end_year"], required=False)

    files, all_columns_present = [], True
    for sector in v2.SECTORS:
        for year in range(win["start_year"], win["end_year"]):
            form = {"private": "F2", "public": "F1A", "forprofit": "F3"}[sector]
            rec = {"form": sector, "fiscal year": year + 1,
                   "table": f"F{str(year)[2:]}{str(year + 1)[2:]}_{form}"}
            csvs = sorted((Path(args.finance) / sector / str(year)).glob("*.csv"))
            if not csvs:
                rec["served"] = False
                all_columns_present = False
                files.append(rec)
                continue
            with open(csvs[0], encoding="latin-1") as fh:
                reader = csv.DictReader(fh)
                cols = [c.strip() for c in (reader.fieldnames or [])]
                rows = list(reader)
            rec.update({"served": True, "file": csvs[0].name, "rows": len(rows), "columns": {}})
            for name, code in FIELDS[sector].items():
                present = code in cols
                share = (sum(number(r.get(code)) is not None for r in rows) / len(rows)) if (present and rows) else 0.0
                rec["columns"][name] = {"code": code, "present": present, "share numeric": round(share, 4)}
                if name in PARSED and not present:
                    all_columns_present = False
            files.append(rec)

    draw = json.loads(DRAW_PATH.read_text())["institutions"][:N_INSTITUTIONS]
    window_years = [f"{y}-{y + 1}" for y in range(win["start_year"], win["end_year"])]
    institutions, implausible = [], []
    for inst in draw:
        u = inst["unitid"]
        sector = v2.finance_sector(u, inst["sector"], args.finance, win["end_year"])
        E, M, Wi, Wt, mask, scale = fld.parse_live_finance(u, window_years, Path(args.finance) / sector, sector=sector)
        years = []
        for i, y in enumerate(window_years):
            fy = int(y[:4]) + 1
            if not mask[i]:
                years.append({"fiscal year": fy, "row found": False})
                continue
            rev, exp_, sup, ins = E[i] * scale, Wt[i] * scale, M[i] * scale, Wi[i] * scale
            liab = None
            for f in (Path(args.finance) / sector / y[:4]).glob("*.csv"):
                with open(f, encoding="latin-1") as fh:
                    for row in csv.DictReader(fh):
                        if row.get("UNITID") == u:
                            liab = number(row.get(FIELDS[sector]["total_liabilities"]))
                            break
            problems = []
            if not rev > 0:
                problems.append("revenue not positive")
            if not exp_ > 0:
                problems.append("total expenses not positive")
            if ins > exp_:
                problems.append("instruction exceeds total expenses")
            if sup > exp_:
                problems.append("institutional support exceeds total expenses")
            if liab is None:
                problems.append("total liabilities missing or not a number")
            years.append({"fiscal year": fy, "row found": True, "revenue": rev, "total expenses": exp_,
                          "instruction": ins, "institutional support": sup, "total liabilities": liab,
                          "problems": problems})
            if problems:
                implausible.append({"unitid": u, "name": inst["name"], "fiscal year": fy, "problems": problems})
        institutions.append({"slot": inst["slot"], "unitid": u, "name": inst["name"],
                             "sector (header file)": inst["sector"], "finance form used": sector,
                             "years with a row": int(sum(mask)), "years": years})

    passed = not missing and all_columns_present and not implausible
    v2.write_json(OUT_PATH, {
        "protocol": "sampling protocol v2.md, early-finance check (before phase 2)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "passed": passed,
        "files NCES did not serve": missing,
        "every column the pipeline reads is present in every file": all_columns_present,
        "implausible parsed years": implausible,
        "files": files,
        "file hashes (sha256)": manifest,
        "institutions": institutions,
        "machine": v2.machine(),
    })
    print(f"Passed: {passed}. Missing files: {len(missing)}. Implausible years: {len(implausible)}. Wrote {OUT_PATH}.")


if __name__ == "__main__":
    main()
