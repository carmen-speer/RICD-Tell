"""
Transfer test, step 2a (see "transfer test protocol.md" and its Amendment 1):
download the Texas Higher Education Coordinating Board's transfer reports for
every two-year college, parse them, and assemble the other inputs.

1. Reports (apps.highered.texas.gov, "Transfer Students Success"), PDFs:
   - academic performance by two-year college (form report_type 2), fall
     cohorts 2014-2024: page 1 ("Comparison of Developmental Education vs No
     Developmental Education"), which splits every transfer exactly once;
     for each receiving university: transfers, first-year GPA bands (below
     2.0, ..., unknown) and still enrolled the following fall, for students
     with and without developmental education;
   - graduation by two-year college (report_type 2Grad), fall cohorts
     2014-2021: for each receiving university, transfers and how many
     graduated within four years from a Texas public or independent
     institution.
   Every parsed table is checked (parts add to totals); a table that fails is
   recorded with the reason and left out, never repaired.
2. Crosswalk: a college's FICE code is the first six digits of its IPEDS
   OPEID; every IPEDS unit ID with that OPEID6 in the cohort's fall header
   file is assigned to it (a district reporting as several IPEDS units is
   summed).
3. Pell share: PCTPELL from the College Scorecard raw-data file this
   repository keeps (release "scorecard-raw-data-2026-11-02", SHA-256 fixed
   in src/build_scorecard_compact.py), Texas institutions only.

Output: data/transfer test/reports.json (parsed tables and the download
log) and data/transfer test/inputs.json (crosswalk and Pell shares). The
PDFs themselves are not committed.

Usage (GitHub Actions; needs pdftotext from poppler-utils):
    cd src
    python "transfer data.py" --work ../work
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import re
import subprocess
import time
import zipfile
from pathlib import Path

import requests

import build_scorecard_compact as bsc
import meta_channel as mc

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "transfer test"
PAGE = "https://apps.highered.texas.gov/index.cfm?page=F5C67269E9A51FF66C697725A30167EAAD92F671EEA28FA27DEB32DFB4609513"
PERF_YEARS = range(2014, 2025)
GRAD_YEARS = range(2014, 2022)
STATEWIDE = {"778899", "445566"}
SKIP_ROWS = {"OTHER PUBLIC 4YR INSTITUTION", "INSTITUTION TOTAL"}
PAUSE = 0.4

PERF_ROW = re.compile(r"^\s*(\S.*?\S)\s+((?:\d+\s+){16}\d+)\s*$")
GRAD_ROW = re.compile(r"^\s*(\S.*?\S)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s*$")


def pdf_text(path: Path, first: int | None = None, last: int | None = None) -> str:
    cmd = ["pdftotext", "-layout"] + (["-f", str(first), "-l", str(last)] if first else []) + [str(path), "-"]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def parse_performance(text: str, year: int) -> dict:
    if f"Fall {year}" not in text or "Developmental Education" not in text:
        return {"error": "page 1 is not the developmental-education table for this cohort"}
    rows, total = [], None
    for line in text.splitlines():
        m = PERF_ROW.match(line)
        if not m:
            continue
        name, n = m.group(1).strip(), [int(x) for x in m.group(2).split()]
        rec = {"university": name, "transfers": n[0],
               "dev ed": {"n": n[1], "gpa": n[2:7], "unknown": n[7], "enrolled next fall": n[8]},
               "no dev ed": {"n": n[9], "gpa": n[10:15], "unknown": n[15], "enrolled next fall": n[16]}}
        problems = []
        if rec["dev ed"]["n"] + rec["no dev ed"]["n"] != rec["transfers"]:
            problems.append("dev ed + no dev ed != transfers")
        for k in ("dev ed", "no dev ed"):
            p = rec[k]
            if sum(p["gpa"]) + p["unknown"] != p["n"]:
                problems.append(f"{k}: GPA bands + unknown != n")
            if p["enrolled next fall"] > p["n"]:
                problems.append(f"{k}: enrolled > n")
        if problems:
            rec["problems"] = problems
        if name == "INSTITUTION TOTAL":
            total = rec
        else:
            rows.append(rec)
    if total is None:
        return {"error": "no INSTITUTION TOTAL row", "rows": rows}
    if sum(r["transfers"] for r in rows) != total["transfers"]:
        return {"error": "rows do not add to the institution total", "rows": rows, "total": total}
    return {"rows": rows, "total": total}


def parse_graduation(text: str, year: int) -> dict:
    if f"Fall {year}" not in text:
        return {"error": "not the graduation table for this cohort"}
    window = re.search(r"Graduated FY(\d{4})\s*-\s*FY(\d{4})", text)
    rows, total = [], None
    for line in text.splitlines():
        m = GRAD_ROW.match(line)
        if not m:
            continue
        rec = {"university": m.group(1).strip(), "transfers": int(m.group(2)), "graduated": int(m.group(3)),
               "percent": float(m.group(4))}
        if rec["graduated"] > rec["transfers"]:
            rec["problems"] = ["graduated > transfers"]
        if rec["university"] == "INSTITUTION TOTAL":
            total = rec
        else:
            rows.append(rec)
    if total is None:
        return {"error": "no INSTITUTION TOTAL row", "rows": rows}
    if sum(r["transfers"] for r in rows) != total["transfers"]:
        return {"error": "rows do not add to the institution total", "rows": rows, "total": total}
    return {"window (fiscal years)": [int(window.group(1)), int(window.group(2))] if window else None,
            "rows": rows, "total": total}


def colleges(session: requests.Session) -> list[dict]:
    r = session.get(PAGE, timeout=60)
    r.raise_for_status()
    form = r.text[r.text.index('name="form2"'):]
    form = form[:form.index("</form>")]
    sel = form[form.index('name="inst"'):]
    sel = sel[:sel.index("</select>")]
    return [{"fice": v, "name": " ".join(t.split())} for v, t in
            re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]*)', sel) if v not in STATEWIDE]


def fetch_report(session, kind: str, fice: str, year: int, path: Path) -> str | None:
    if path.exists() and path.stat().st_size > 0:
        return None
    data = {"report_type": kind, "OutPutType": "PDF", "btnSubmit": "View PDF", "inst": fice, "Report_Yr": str(year)}
    for attempt in range(1, 4):
        try:
            r = session.post(PAGE, data=data, timeout=120)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                path.write_bytes(r.content)
                time.sleep(PAUSE)
                return None
            err = f"HTTP {r.status_code}, {r.headers.get('Content-Type', '')}, {len(r.content)} bytes"
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {e}"
        time.sleep(5 * attempt)
    return err


def crosswalk(fices: set[str]) -> dict:
    """OPEID6 -> unit IDs, by fall year, from the IPEDS header files."""
    out = {}
    for y in range(2012, PERF_YEARS[-1] + 1):
        got = mc.fetch(f"HD{y}.zip", False)
        if not got:
            continue
        _, text = mc.first_csv(got[0])
        by = {}
        for r in mc.rows(text):
            op = (r.get("OPEID") or "").strip().zfill(8)[:6]
            if op in fices:
                by.setdefault(op, []).append(r["UNITID"])
        out[str(y)] = by
    return out


def pell(work: Path) -> dict:
    """PCTPELL for Texas institutions, by Scorecard file year (the first year in the file's name)."""
    zpath = work / "scorecard_all_data.zip"
    if not zpath.exists():
        with requests.get(bsc.RELEASE_URL, stream=True, timeout=600, headers=bsc.HEADERS) as r:
            r.raise_for_status()
            with open(zpath, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
    if sha != bsc.EXPECTED_SHA256:
        raise SystemExit(f"Scorecard file SHA-256 {sha} is not the fixed {bsc.EXPECTED_SHA256}.")
    out = {}
    with zipfile.ZipFile(zpath) as zf:
        for name in sorted(zf.namelist()):
            m = bsc.NAME_RE.search(name)
            if not m or name.startswith("__MACOSX") or "/._" in name:
                continue
            year = int(m.group(1))
            if year < 2011:
                continue
            with zf.open(name) as raw:
                rd = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"))
                rd.fieldnames = [h.strip().lstrip("﻿").upper() for h in rd.fieldnames]
                for row in rd:
                    if (row.get("STABBR") or "").strip() != "TX":
                        continue
                    try:
                        v = float(row.get("PCTPELL") or "")
                    except ValueError:
                        continue
                    out.setdefault(row["UNITID"].strip(), {})[str(year)] = v
    return {"sha256": sha, "by unit id": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    work = Path(ap.parse_args().work)
    pdfs = work / "transfer pdfs"
    pdfs.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(bsc.HEADERS)
    cols = colleges(s)
    print(f"{len(cols)} two-year colleges", flush=True)
    log, perf, grad = [], [], []
    for c in cols:
        for kind, years, store, parse in (("2", PERF_YEARS, perf, parse_performance),
                                          ("2Grad", GRAD_YEARS, grad, parse_graduation)):
            for y in years:
                path = pdfs / f"{kind} {c['fice']} {y}.pdf"
                err = fetch_report(s, kind, c["fice"], y, path)
                if err:
                    log.append({"report": kind, "fice": c["fice"], "year": y, "error": err})
                    continue
                try:
                    text = pdf_text(path, 1, 1) if kind == "2" else pdf_text(path)
                    res = parse(text, y)
                except subprocess.CalledProcessError as e:
                    res = {"error": f"pdftotext failed: {e}"}
                store.append({"fice": c["fice"], "college": c["name"], "cohort (fall)": y, **res})
        print(f"  {c['fice']} {c['name']}: done", flush=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reports.json").write_text(json.dumps({
        "protocol": "transfer test protocol.md, step 2a", "written at (UTC)": stamp,
        "source": PAGE, "colleges": cols,
        "parsed": {"performance": sum("rows" in r and "error" not in r for r in perf),
                   "graduation": sum("rows" in r and "error" not in r for r in grad),
                   "failed": [{"report": "performance" if r in perf else "graduation", "fice": r["fice"],
                               "cohort (fall)": r["cohort (fall)"], "error": r["error"]}
                              for r in perf + grad if "error" in r],
                   "download errors": log},
        "performance": perf, "graduation": grad}, indent=1))
    (OUT / "inputs.json").write_text(json.dumps({
        "written at (UTC)": stamp,
        "crosswalk (fall year -> FICE -> IPEDS unit IDs)": crosswalk({c["fice"] for c in cols}),
        "Pell share (PCTPELL)": pell(work)}, indent=1))
    print("Wrote reports.json and inputs.json", flush=True)


if __name__ == "__main__":
    main()
