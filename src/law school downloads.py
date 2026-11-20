"""
Item 12, law-school record, step 1 ("channel selection protocol.md",
Amendments 8 and 12): download the ABA national compilation spreadsheets
and record their layout. No 509 value is read.

Requests the same public addresses that the ABA Required Disclosures site's
"Generate Report" buttons use (decided November 20, 2026):

  509 sections      for each reporting year 2011-2025, the section list for
                    that year, then the compilations of the sections whose
                    labels name J.D. enrollment, attrition, and (through
                    2017) bar passage
  bar passage       first-time bar passage compilation, reporting years
                    2018 to the latest offered (the 2018 file holds 2016-2017)
  employment        employment summary compilation, graduating classes 2010
                    to the latest offered

Every file is saved unchanged in data/v4 channels/law schools/raw/, and
data/v4 channels/law schools/downloads.json records each address,
download time, size and SHA-256, and each file's layout: sheet names and
the leading header rows of each sheet, stopping at the first row that holds
three or more numbers (the first data row), so no value is read.

Usage (GitHub Actions only, via law_school_downloads.yml):
    cd src
    python "law school downloads.py"
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import re
import time
from pathlib import Path

import openpyxl
import requests

HERE = Path(__file__).resolve().parent
DIR = HERE.parent / "data" / "v4 channels" / "law schools"
RAW = DIR / "raw"
API = "https://backend.abarequireddisclosures.org/api/"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/126.0 Safari/537.36",
           "Referer": "https://www.abarequireddisclosures.org/", "Origin": "https://www.abarequireddisclosures.org"}
YEARS_509 = range(2011, 2026)
YEARS_BAR = range(2018, 2027)
YEARS_EMP = range(2010, 2026)
WANT_509 = {"enrollment": re.compile(r"enrollment", re.I), "attrition": re.compile(r"attrition", re.I),
            "bar passage": re.compile(r"bar passage", re.I)}


def get(path: str, params: dict, binary: bool):
    last = ""
    for attempt in range(1, 4):
        try:
            r = requests.get(API + path, params=params, headers=HEADERS, timeout=180)
            if r.status_code == 200 and r.content:
                return r
            last = f"HTTP {r.status_code}, {len(r.content)} bytes"
        except requests.RequestException as e:
            last = type(e).__name__
        time.sleep(5 * attempt)
    return last


def layout(content: bytes) -> dict:
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as e:  # not a readable workbook
        return {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    sheets = {}
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True, max_row=40):
            nums = sum(isinstance(c, (int, float)) for c in row)
            if nums >= 3:
                break
            cells = ["" if c is None else str(c).strip()[:120] for c in row]
            while cells and not cells[-1]:
                cells.pop()
            if cells:
                rows.append(cells)
        sheets[ws.title] = {"header rows (before the first data row)": rows}
    return {"sheets": sheets}


def save(name: str, r, url_desc: str, log: list) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_bytes(r.content)
    log.append({"file": name, "request": url_desc, "address": r.url,
                "downloaded at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest(),
                "content type": r.headers.get("content-type", ""), "layout": layout(r.content)})
    print("saved", name, len(r.content), flush=True)


def main() -> None:
    log, failures, sections_by_year = [], [], {}
    for y in YEARS_509:
        r = get("AnnualQuestionnaire/Get509SectionListByYear", {"schoolYear": y}, False)
        if isinstance(r, str):
            failures.append(f"509 section list {y}: {r}")
            continue
        names = [s.get("sectionName", "") for s in r.json().get("std509SectionEntities", [])]
        sections_by_year[str(y)] = names
        for key, rx in WANT_509.items():
            if key == "bar passage" and y > 2017:
                continue
            hits = [n for n in names if rx.search(n)]
            if len(hits) != 1:
                failures.append(f"509 {y} {key}: {len(hits)} matching sections {hits}")
                continue
            f = get("AnnualQuestionnaire/GetAllCompilationData", {"year": y, "scetionName": hits[0]}, True)
            if isinstance(f, str):
                failures.append(f"509 {y} {hits[0]}: {f}")
                continue
            save(f"509 {y} {key}.xlsx", f, f"509 compilation, {y}, section '{hits[0]}'", log)
    for y in YEARS_BAR:
        f = get("BarPassageOutcomes/GenerateBarPassageCompilationReport", {"year": y, "sectionName": "First Time Bar Passage"}, True)
        if isinstance(f, str):
            failures.append(f"bar passage {y}: {f}")
            continue
        save(f"bar passage {y} first time.xlsx", f, f"bar passage compilation, {y}, First Time Bar Passage", log)
    for y in YEARS_EMP:
        f = get("EmploymentOutcomes/GenerateEQCompilationReport", {"year": y}, True)
        if isinstance(f, str):
            failures.append(f"employment {y}: {f}")
            continue
        save(f"employment {y}.xlsx", f, f"employment summary compilation, class of {y}", log)
    if not log:
        raise SystemExit("No file could be downloaded: " + " | ".join(failures[:10]) + ". Nothing recorded.")
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "downloads.json").write_text(json.dumps({
        "step": "Law-school record, step 1 (Amendment 12): downloads and layout only; no 509 value read",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "509 sections offered, by reporting year": sections_by_year,
        "files": log, "not downloaded": failures}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(log)} files saved; {len(failures)} not downloaded")
    for x in failures:
        print("  ", x)


if __name__ == "__main__":
    main()
