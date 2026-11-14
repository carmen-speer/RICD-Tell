"""
Finance field-code diagnostic for "sampling protocol v2.md" (before phase 2).

The early-finance check (data/v2/early finance check.json) found that, in
the fiscal years 2004-2014 the training window needs:

- the for-profit (F3) files for 2004-2013 have no column F3E011
  (instruction) or F3E061 (institutional support), the codes the pipeline
  reads; and
- the endowment column the pipeline reads (F1H02 for public, F2H02 for
  private) holds no numbers at all in most public years and in the
  private years 2011-2014.

The protocol requires any year whose field codes differ to be documented
and handled before training scoring begins. This diagnostic documents
them. For every finance form and every fiscal year from 2004 through 2019
(the training window and the test window together) it:

1. downloads the finance ZIP and lists every CSV inside it, with its row
   count, since a ZIP can hold a revised-values file beside the main one
   and the pipeline reads only the first CSV it finds;
2. for every CSV, lists every expense column (code F?E...) and endowment
   column (code F?H...), with the share of rows holding a number and the
   number of rows holding a nonzero number; and
3. downloads the table's NCES dictionary (<table>_Dict.zip) and, where it
   is an .xlsx or .html file, records the title NCES gives each of those
   columns.

Nothing is changed, and no institution or outcome is read. The result is
written to data/v2/finance codes diagnostic.json.

Usage (GitHub Actions only, via diagnose_v2_finance_codes.yml):
    cd src
    python diagnose_v2_finance_codes.py
"""

from __future__ import annotations

import csv
import datetime
import html
import io
import json
import re
import time
import zipfile

import requests

import v2_common as v2

OUT_PATH = v2.V2_DIR / "finance codes diagnostic.json"
FORMS = {"private": "F2", "public": "F1A", "forprofit": "F3"}
BASES = ["https://nces.ed.gov/ipeds/datacenter/data/", "https://nces.ed.gov/ipeds/complete-data-files/"]
COLUMN = re.compile(r"^F(1|2|3)[A-Z]?(E|H)\d")
csv.field_size_limit(10 ** 8)


def fetch(name: str) -> tuple[bytes | None, str]:
    last = ""
    for attempt in range(1, 5):
        for base in BASES:
            url = base + name
            try:
                r = requests.get(url, timeout=120)
                if r.status_code == 200 and r.content[:2] == b"PK":
                    return r.content, url
                last = f"HTTP {r.status_code} at {url}"
            except requests.RequestException as e:
                last = f"{e} at {url}"
        time.sleep(15 * attempt)
    return None, last


def number(v: str) -> float | None:
    try:
        return float(v.strip())
    except (AttributeError, ValueError):
        return None


def read_xlsx_titles(data: bytes) -> dict:
    """varname -> vartitle from an .xlsx dictionary, read from its XML directly."""
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        x = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        for si in re.findall(r"<si>(.*?)</si>", x, re.S):
            shared.append(html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
    titles = {}
    for sheet in sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet")):
        x = z.read(sheet).decode("utf-8", "replace")
        for row in re.findall(r"<row[^>]*>(.*?)</row>", x, re.S):
            cells = []
            for c in re.findall(r"<c ([^>]*)>(.*?)</c>", row, re.S):
                attrs, body = c
                v = re.search(r"<v>(.*?)</v>", body, re.S)
                t = re.search(r"<t[^>]*>(.*?)</t>", body, re.S)
                if 't="s"' in attrs and v:
                    cells.append(shared[int(v.group(1))])
                elif t:
                    cells.append(html.unescape(t.group(1)))
                elif v:
                    cells.append(html.unescape(v.group(1)))
            codes = [i for i, c in enumerate(cells) if COLUMN.match(c.strip().upper())]
            for i in codes:
                rest = [c for c in cells[i + 1:] if c and not re.fullmatch(r"[\d.]+|[A-Z]{1,4}", c.strip())]
                if rest:   # the title is the longest text cell in the row (the others are type, width, format, flag codes)
                    titles.setdefault(cells[i].strip().upper(), max(rest, key=len).strip())
    return titles


def read_html_titles(text: str) -> dict:
    titles = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)]
        for i, c in enumerate(cells):
            if COLUMN.match(c.upper()) and i + 1 < len(cells):
                rest = [x for x in cells[i + 1:] if x and not re.fullmatch(r"[\d.]+|[A-Z]{1,4}", x)]
                if rest:
                    titles.setdefault(c.upper(), max(rest, key=len))
    return titles


def main() -> None:
    tables = []
    for sector, form in FORMS.items():
        for year in range(2003, 2019):          # fiscal years 2004 through 2019
            table = f"F{str(year)[2:]}{str(year + 1)[2:]}_{form}"
            rec = {"form": sector, "fiscal year": year + 1, "table": table}
            data, src = fetch(table + ".zip")
            rec["source"] = src
            if data is None:
                rec["served"] = False
                tables.append(rec)
                continue
            rec["served"] = True
            z = zipfile.ZipFile(io.BytesIO(data))
            rec["files in ZIP"] = z.namelist()
            rec["csvs"] = []
            for name in z.namelist():
                if not name.lower().endswith(".csv"):
                    continue
                text = z.read(name).decode("latin-1")
                reader = csv.DictReader(io.StringIO(text))
                header = [h.strip().upper() for h in (reader.fieldnames or [])]
                rows = list(reader)
                cols = {}
                for h_orig in reader.fieldnames or []:
                    h = h_orig.strip().upper()
                    if COLUMN.match(h):
                        vals = [number(r.get(h_orig, "")) for r in rows]
                        num = [v for v in vals if v is not None]
                        cols[h] = {"share numeric": round(len(num) / max(len(rows), 1), 4),
                                   "nonzero rows": sum(1 for v in num if v != 0)}
                rec["csvs"].append({"file": name, "rows": len(rows), "number of columns": len(header),
                                    "expense and endowment columns": cols})
            ddata, dsrc = fetch(table + "_Dict.zip")
            rec["dictionary"] = {"source": dsrc, "served": ddata is not None}
            if ddata is not None:
                dz = zipfile.ZipFile(io.BytesIO(ddata))
                rec["dictionary"]["files"] = dz.namelist()
                titles = {}
                for name in dz.namelist():
                    low = name.lower()
                    try:
                        if low.endswith(".xlsx"):
                            titles.update(read_xlsx_titles(dz.read(name)))
                        elif low.endswith((".html", ".htm")):
                            titles.update(read_html_titles(dz.read(name).decode("latin-1")))
                    except Exception as e:          # a dictionary we cannot read is recorded, not fatal
                        rec["dictionary"].setdefault("unread", []).append(f"{name}: {e}")
                rec["dictionary"]["titles"] = dict(sorted(titles.items()))
            tables.append(rec)
            time.sleep(2)
    out = {"protocol": "sampling protocol v2.md, finance field-code diagnostic (before phase 2)",
           "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "tables": tables, "machine": v2.machine()}
    v2.write_json(OUT_PATH, out)
    print(f"Wrote {OUT_PATH} ({len(tables)} tables).")


if __name__ == "__main__":
    main()
