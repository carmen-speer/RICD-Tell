"""
Item 23k follow-up, step 0: field check for the Department of Education's
proprietary-school 90/10 revenue percentages, the outside check approved on
November 27, 2026 for the for-profit figures in item 23k.

For each award year's spreadsheet listed on Federal Student Aid's data
center (https://studentaid.gov/data-center/school/proprietary, links read
November 27, 2026), downloads the file, keeps an exact copy with its SHA-256,
and records its layout: every sheet's first rows, the row that holds the
column headings (the first row naming an OPEID), and the headings
themselves. Nothing is parsed into figures, matched to IPEDS or compared
with anything; the parse is written from this record.

Award year 2009-2010 has its report only as a PDF; its summary chart (a
spreadsheet) is checked instead. Award year 2007-2008 is PDF only and left
out.

Writes data/ninety_ten/:
  raw/<award year>.<xls|xlsx>   the files as downloaded
  field_check.json              per file: address, HTTP status, size,
                                SHA-256, and the layout record

Usage (GitHub Actions only, via ninety_ten_field_check.yml):
    cd src
    python ninety_ten_field_check.py
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "ninety_ten"
BASE = "https://studentaid.gov/sites/default/files/"
FILES = {
    "2024-2025": "2024-2025-Proprietary-School-Revenue-Percentages-Report.xlsx",
    "2023-2024": "2023-2024-proprietary-school-revenue-percentages-report.xlsx",
    "2022-2023": "2022-2023-proprietary-school-revenue-percentages-report.xlsx",
    "2021-2022": "2021-2022-Proprietary-School-Revenue-Percentages-Report.xlsx",
    "2020-2021": "2020-2021-Proprietary-School-Revenue-Percentages-Report.xlsx",
    "2019-2020": "2019-2020-Proprietary-School-Revenue-Percentages-Report.xlsx",
    "2018-2019": "2018-2019%20Proprietary%20School%20Revenue%20Percentages%20Report.xls",
    "2017-2018": "2017-2018-data.xls",
    "2016-2017": "fsawg/datacenter/library/20162017Data.xls",
    "2015-2016": "fsawg/datacenter/library/AY15-16-90-10.xlsx",
    "2014-2015": "90-10-Attestation-Report-AY15.xls",
    "2013-2014": "9010Report091815.xls",
    "2012-2013": "9010Report20122013.xls",
    "2011-2012": "9010Report20112012.xls",
    "2010-2011": "2010-2011Report.xls",
    "2009-2010 (summary chart)": "110557SummaryPercentagesandTitleIVFunding.xls",
    "2008-2009": "PropSch90-10PercentageswithFYEDatesin2008-2009AY.xls",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/126.0 Safari/537.36"}
FIRST_ROWS = 12


def cell(c) -> str:
    return "" if pd.isna(c) else str(c).strip()[:120]


def layout(content: bytes, ext: str) -> dict:
    engine = "xlrd" if ext == "xls" else "openpyxl"
    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, engine=engine)
    out = {}
    for name, df in sheets.items():
        grid = [[cell(c) for c in row] for row in df.values.tolist()]
        head = next((i for i, row in enumerate(grid) if any("OPEID" in c.upper() for c in row)), None)
        out[name] = {"rows": len(grid), "columns": df.shape[1],
                     "first rows": [[c for c in row if c] for row in grid[:FIRST_ROWS]],
                     "heading row (first naming an OPEID)": head,
                     "headings": [c for c in grid[head] if c] if head is not None else None,
                     "first data rows": ([[c for c in row if c] for row in grid[head + 1:head + 4]]
                                         if head is not None else None)}
    return out


def main() -> None:
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    record, ok = {}, 0
    for year, path in FILES.items():
        url = BASE + path
        ext = "xlsx" if path.lower().endswith(".xlsx") else "xls"
        entry = {"url": url}
        try:
            r = requests.get(url, timeout=180, headers=HEADERS)
            entry["HTTP status"] = r.status_code
            if r.status_code == 200 and len(r.content) > 1000:
                entry["bytes"] = len(r.content)
                entry["sha256"] = hashlib.sha256(r.content).hexdigest()
                name = year.split(" ")[0] + "." + ext
                (OUT / "raw" / name).write_bytes(r.content)
                entry["copy"] = f"data/ninety_ten/raw/{name}"
                try:
                    entry["layout"] = layout(r.content, ext)
                    ok += 1
                except Exception as e:  # an unreadable file is recorded, never guessed
                    entry["layout error"] = f"{type(e).__name__}: {str(e)[:300]}"
        except requests.RequestException as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        record[year] = entry
        print(year, entry.get("HTTP status"), entry.get("bytes"), "read" if "layout" in entry else "not read", flush=True)
    (OUT / "field_check.json").write_text(json.dumps({
        "note": ("Field check for the 90/10 outside check on item 23k: downloads and layouts only; nothing parsed, "
                 "matched or compared."),
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source page": "https://studentaid.gov/data-center/school/proprietary",
        "files read": ok, "files listed": len(FILES), "by award year": record},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if ok == 0:
        raise SystemExit("No file could be downloaded and read; the record says why. Nothing else written.")


if __name__ == "__main__":
    main()
