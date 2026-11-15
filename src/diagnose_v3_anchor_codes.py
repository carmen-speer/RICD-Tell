"""
Anchor field-code diagnostic for "sampling protocol v3.md", before the
anchor sensor reads any value.

The anchor sensor (RICD §10.5b.13b) reads, for each institution, its state
and local appropriations, its private gifts, grants and contracts, and its
net assets from its own finance form, and its system membership, religious
affiliation and federal designations from the directory files. The v2
diagnostic found that a code can mean something other than what the
pipeline assumed (F3E061 is "Other expenses", not institutional support),
so before any code is used, this diagnostic records what NCES itself calls
each one. For every finance form (public F1A, private F2, for-profit F3)
and the fiscal years the anchor sensor reads (2012-2014 for the 2014
development set, 2017-2019 for the 2019 development set and the v3 test),
it:

1. downloads the finance ZIP and, for every CSV inside it, lists every
   revenue column (section B of the public form, section D of the private
   and for-profit forms), every balance-sheet and net-asset column
   (section A) and every endowment column (section H), with the share of
   rows holding a number and the number of rows holding a nonzero number;
2. downloads the table's NCES dictionary and records the title NCES gives
   each of those columns.

For the directory and institutional-characteristics files of 2014 and 2019
(HD and IC), it records whether each anchor-related column exists and the
counts of its values: system membership (F1SYSTYP, F1SYSCOD, F1SYSNAM),
HBCU, TRIBAL, LANDGRNT, CONTROL and religious affiliation (RELAFFIL).

Nothing is changed, and no institution's outcome is read. The result is
written to data/v3/anchor codes diagnostic.json.

Usage (GitHub Actions only, via diagnose_v3_anchor_codes.yml):
    cd src
    python diagnose_v3_anchor_codes.py
"""

from __future__ import annotations

import collections
import csv
import datetime
import io
import re
import time
import zipfile

import v2_common as v2
import v3_common as v3
import diagnose_v2_finance_codes as d2

OUT_PATH = v3.V3_DIR / "anchor codes diagnostic.json"
FORMS = {"public": "F1A", "private": "F2", "forprofit": "F3"}
FISCAL_YEARS = (2012, 2013, 2014, 2017, 2018, 2019)
COLUMN = re.compile(r"^F(1|2|3)[A-Z]?(A|B|D|H)\d")
DIRECTORY_COLUMNS = {"HD": ("F1SYSTYP", "F1SYSCOD", "F1SYSNAM", "HBCU", "TRIBAL", "LANDGRNT", "CONTROL"),
                     "IC": ("RELAFFIL",)}
d2.COLUMN = COLUMN          # the v2 dictionary readers match column codes with this pattern


def finance_table(sector: str, fy: int) -> dict:
    form = FORMS[sector]
    table = f"F{str(fy - 1)[2:]}{str(fy)[2:]}_{form}"
    rec = {"form": sector, "fiscal year": fy, "table": table}
    data, src = d2.fetch(table + ".zip")
    rec["source"], rec["served"] = src, data is not None
    if data is None:
        return rec
    z = zipfile.ZipFile(io.BytesIO(data))
    rec["files in ZIP"] = z.namelist()
    rec["csvs"] = []
    for name in z.namelist():
        if not name.lower().endswith(".csv"):
            continue
        reader = csv.DictReader(io.StringIO(z.read(name).decode("latin-1")))
        rows = list(reader)
        cols = {}
        for h_orig in reader.fieldnames or []:
            h = h_orig.strip().lstrip("\ufeff").lstrip("\u00ef\u00bb\u00bf").strip().upper()
            if COLUMN.match(h):
                num = [v for v in (d2.number(r.get(h_orig, "")) for r in rows) if v is not None]
                cols[h] = {"share numeric": round(len(num) / max(len(rows), 1), 4),
                           "nonzero rows": sum(1 for v in num if v != 0)}
        rec["csvs"].append({"file": name, "rows": len(rows), "revenue, net-asset and endowment columns": cols})
    ddata, dsrc = d2.fetch(table + "_Dict.zip")
    rec["dictionary"] = {"source": dsrc, "served": ddata is not None}
    if ddata is not None:
        dz = zipfile.ZipFile(io.BytesIO(ddata))
        titles = {}
        for name in dz.namelist():
            low = name.lower()
            try:
                if low.endswith(".xlsx"):
                    titles.update(d2.read_xlsx_titles(dz.read(name)))
                elif low.endswith((".html", ".htm")):
                    titles.update(d2.read_html_titles(dz.read(name).decode("latin-1")))
            except Exception as e:
                rec["dictionary"].setdefault("unread", []).append(f"{name}: {e}")
        rec["dictionary"]["titles"] = dict(sorted(titles.items()))
    return rec


def directory_table(prefix: str, year: int) -> dict:
    table = f"{prefix}{year}"
    rec = {"table": table}
    data, src = d2.fetch(table + ".zip")
    rec["source"], rec["served"] = src, data is not None
    if data is None:
        return rec
    z = zipfile.ZipFile(io.BytesIO(data))
    names = sorted((n for n in z.namelist() if n.lower().endswith(".csv")), key=lambda n: ("_rv" in n.lower(), len(n)))
    rec["file"] = names[0]
    reader = csv.DictReader(io.StringIO(z.read(names[0]).decode("latin-1")))
    fields = {f: f.strip().lstrip("\ufeff").lstrip("\u00ef\u00bb\u00bf").strip().upper() for f in reader.fieldnames or []}
    rows = list(reader)
    rec["rows"] = len(rows)
    rec["columns"] = {}
    for col in DIRECTORY_COLUMNS[prefix]:
        orig = [k for k, v in fields.items() if v == col]
        if not orig:
            rec["columns"][col] = {"present": False}
            continue
        counts = collections.Counter((r.get(orig[0]) or "").strip() for r in rows)
        rec["columns"][col] = {"present": True, "distinct values": len(counts),
                               "most common values": counts.most_common(15)}
    return rec


def main() -> None:
    finance = []
    for sector in FORMS:
        for fy in FISCAL_YEARS:
            finance.append(finance_table(sector, fy))
            time.sleep(2)
    directory = [directory_table(p, y) for p in DIRECTORY_COLUMNS for y in (2014, 2019)]
    v2.write_json(OUT_PATH, {
        "protocol": "sampling protocol v3.md, anchor field-code diagnostic (before the anchor sensor reads any value)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "finance tables": finance, "directory tables": directory, "machine": v2.machine()})
    print(f"Wrote {OUT_PATH}: {len(finance)} finance tables, {len(directory)} directory tables.")


if __name__ == "__main__":
    main()
