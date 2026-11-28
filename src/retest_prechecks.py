"""
Blind-retest prechecks (to-do items 23 and 23d). Reads layouts and labels
only; no staff count, no finance value and no outcome is recorded.

Check 1, the fall 2024 staffing dictionaries (item 23d). On November 20 the
label reader resolved every staffing category in every fall from 2012 to
2023, but none in fall 2024 (EAP2024, S2024_NH), whose files are served
from NCES's newer complete-data-files location. For EAP2023 (the last year
that resolved, as a reference), EAP2024 and S2024_NH this records:
  - the files inside each dictionary zip, and for each sheet of its .xlsx
    the sheet's name, its row count, its first five rows, and every row
    that mentions OCCUPCAT or FACSTAT;
  - the data file's column names and the distinct codes in its OCCUPCAT
    and FACSTAT columns with how many rows carry each (codes only);
  - whether each category resolves by its label (the rule of
    src/adjunct absorption.py) when only whole-number codes are read, and
    again when codes written as "210.0" are read as "210", so the cause
    can be named before anything changes.

Check 2, Penn State York. Whether IPEDS reports its finances separately or
inside Penn State's university-wide filing. From the newest header files
(HD2023 to HD2025, as served), every row whose name contains both "Penn
State" or "Pennsylvania State" and "York": unit ID, name, sector and the
closure fields. From the flags files (FLAGS2022 to FLAGS2024): its
parent/child finance fields (every column whose name begins PRCH or IDX).
From the public finance files for fiscal 2022 to 2024 (F2122_F1A,
F2223_F1A, F2324_F1A): only whether its unit ID has a row.

Output: data/retest/prechecks.json.

Usage (GitHub Actions only, via retest_prechecks.yml):
    cd src
    python retest_prechecks.py
"""

from __future__ import annotations

import datetime
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import meta_channel as mc

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "retest" / "prechecks.json"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

STAFF_TABLES = ("EAP2023", "EAP2024", "S2024_NH")
OCC_LABELS = {"instructional staff total", "instructional staff"}
FAC_LABELS = {
    "all": {"all staff", "all full time new hires"},
    "faculty total": {"with faculty status total"},
    "tenured": {"with faculty status tenured"},
    "track": {"with faculty status on tenure track"},
    "off track": {"with faculty status not on tenure track no tenure system total"},
    "annual": {"with faculty status not on tenure track no tenure system annual contract"},
    "less than annual": {"with faculty status not on tenure track no tenure system less than annual contract"},
    "no faculty status": {"without faculty status"},
}


# ------------------------------------------------------------------ dictionary, sheet by sheet
def sheets(dict_zip: bytes) -> tuple[list[str], dict[str, list[list[str]]]]:
    outer = zipfile.ZipFile(io.BytesIO(dict_zip))
    members = outer.namelist()
    books = [n for n in members if n.lower().endswith(".xlsx")]
    if not books:
        return members, {}
    z = zipfile.ZipFile(io.BytesIO(outer.read(books[0])))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    names = {}
    if "xl/workbook.xml" in z.namelist():
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        for i, s in enumerate(wb.iter(f"{{{NS['m']}}}sheet"), start=1):
            names[f"xl/worksheets/sheet{i}.xml"] = s.get("name", f"sheet{i}")
    out = {}
    for n in sorted(x for x in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", x)):
        rows = []
        for row in ET.fromstring(z.read(n)).iter(f"{{{NS['m']}}}row"):
            cells = {}
            for c in row.findall("m:c", NS):
                col = re.match(r"[A-Z]+", c.get("r", "A")).group(0)
                idx = 0
                for ch in col:
                    idx = idx * 26 + ord(ch) - 64
                v = c.find("m:v", NS)
                if c.get("t") == "s" and v is not None:
                    text = shared[int(v.text)]
                elif c.get("t") == "inlineStr":
                    text = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
                else:
                    text = v.text if v is not None else ""
                cells[idx - 1] = (text or "").strip()
            if cells:
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
        out[names.get(n, n)] = rows
    return members, out


def code_labels(all_rows: list[list[str]], loose: bool) -> dict[str, dict[str, str]]:
    """Code -> label for OCCUPCAT and FACSTAT, by the current rule (strict) or with '210.0' read as '210' (loose)."""
    found: dict[str, dict[str, str]] = {}
    for r in all_rows:
        cells = [c.strip() for c in r]
        for i, c in enumerate(cells):
            if c.upper() not in ("OCCUPCAT", "FACSTAT") or i + 2 >= len(cells):
                continue
            code, label = cells[i + 1], cells[i + 2]
            if loose and re.fullmatch(r"-?\d+\.0+", code):
                code = code.split(".")[0]
            if re.fullmatch(r"-?\d+", code) and label:
                found.setdefault(c.upper(), {})[code] = label[:150]
    return found


def resolution(labels: dict[str, dict[str, str]]) -> dict:
    occ = [c for c, l in labels.get("OCCUPCAT", {}).items() if mc.norm(l) in OCC_LABELS]
    res = {"occupation": occ}
    for cat, want in FAC_LABELS.items():
        res[cat] = [c for c, l in labels.get("FACSTAT", {}).items() if mc.norm(l) in want]
    return {"resolved": {k: v[0] for k, v in res.items() if len(v) == 1},
            "unresolved": {k: v for k, v in res.items() if len(v) != 1}}


def staffing(table: str) -> dict:
    out: dict = {"table": table}
    got = mc.fetch(f"{table}_Dict.zip", False)
    if got is None:
        out["dictionary"] = "not served"
    else:
        members, sh = sheets(got[0])
        all_rows = [r for rows in sh.values() for r in rows]
        out["dictionary"] = {
            "url": got[1], "files in zip": members,
            "sheets": {name: {"rows": len(rows), "first rows": [r[:8] for r in rows[:5]],
                              "rows mentioning OCCUPCAT or FACSTAT": [
                                  r[:8] for r in rows if any(c.upper() in ("OCCUPCAT", "FACSTAT") for c in r)][:60]}
                       for name, rows in sh.items()},
            "labels, whole-number codes only": code_labels(all_rows, loose=False),
            "labels, '.0' codes accepted": code_labels(all_rows, loose=True)}
        out["resolution, whole-number codes only"] = resolution(out["dictionary"]["labels, whole-number codes only"])
        out["resolution, '.0' codes accepted"] = resolution(out["dictionary"]["labels, '.0' codes accepted"])
    data = mc.fetch(f"{table}.zip", False)
    if data is None:
        out["data file"] = "not served"
    else:
        name, text = mc.first_csv(data[0])
        rows = mc.rows(text)
        cols = list(rows[0].keys()) if rows else []
        out["data file"] = {"url": data[1], "csv": name, "rows": len(rows), "columns": cols,
                            "codes": {f: dict(sorted(Counter(r.get(f, "") for r in rows).items()))
                                      for f in ("OCCUPCAT", "FACSTAT") if f in cols}}
    return out


# ------------------------------------------------------------------ Penn State York
def is_york(name: str) -> bool:
    n = name.lower()
    return "york" in n and ("penn state" in n or "pennsylvania state" in n)


def penn_state_york() -> dict:
    out: dict = {"header files": {}, "flags files": {}, "public finance files": {}}
    ids: set[str] = set()
    for y in (2023, 2024, 2025):
        got = mc.fetch(f"HD{y}.zip", False)
        if got is None:
            out["header files"][f"HD{y}"] = "not served"
            continue
        rows = mc.rows(mc.first_csv(got[0])[1])
        hits = [{k: r.get(k, "") for k in ("UNITID", "INSTNM", "SECTOR", "CYACTIVE", "CLOSEDAT", "DEATHYR",
                                            "NEWID", "F1SYSNAM", "F1SYSCOD")}
                for r in rows if is_york(r.get("INSTNM", ""))]
        ids |= {h["UNITID"] for h in hits}
        out["header files"][f"HD{y}"] = hits
    for y in (2022, 2023, 2024):
        got = mc.fetch(f"FLAGS{y}.zip", False)
        if got is None:
            out["flags files"][f"FLAGS{y}"] = "not served"
            continue
        rows = mc.rows(mc.first_csv(got[0])[1])
        out["flags files"][f"FLAGS{y}"] = [
            {k: v for k, v in r.items() if k == "UNITID" or k.startswith("PRCH") or k.startswith("IDX")}
            for r in rows if r.get("UNITID") in ids]
    for f in ("F2122_F1A", "F2223_F1A", "F2324_F1A"):
        got = mc.fetch(f"{f}.zip", False)
        if got is None:
            out["public finance files"][f] = "not served"
            continue
        present = {r.get("UNITID") for r in mc.rows(mc.first_csv(got[0])[1])}
        out["public finance files"][f] = {u: (u in present) for u in sorted(ids)}
    out["unit IDs found"] = sorted(ids)
    return out


def main() -> None:
    result = {
        "note": "Blind-retest prechecks: dictionary layouts, category codes and reporting relationships only; "
                "no staff count, finance value or outcome is recorded.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "check 1: fall 2024 staffing dictionaries (item 23d)": [staffing(t) for t in STAFF_TABLES],
        "check 2: Penn State York's finance reporting": penn_state_york(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for s in result["check 1: fall 2024 staffing dictionaries (item 23d)"]:
        print(s["table"], json.dumps(s.get("resolution, whole-number codes only")), json.dumps(s.get("resolution, '.0' codes accepted")))
    print("Penn State York unit IDs:", result["check 2: Penn State York's finance reporting"]["unit IDs found"])


if __name__ == "__main__":
    main()
