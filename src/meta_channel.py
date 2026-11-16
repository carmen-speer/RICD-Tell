"""
The meta channel P_m, measured: the full-time share of each institution's
instructional staff, from the IPEDS Human Resources "Employees by Assigned
Position" files (EAP), the input the scoring model was built to take
(model.build_model_stage2's pt_share_obs is the part-time share; the model
observes P_m = 1 - pt_share, the full-time share). Until now no run has
supplied it, which is why the model's fallback set P_m to a constant
outside [0, 1] (see "reanalysis protocol.md").

Nothing here is used by any frozen pipeline. This script only downloads,
reads and checks the measurement and commits it, so that it can be
examined before a protocol for the prospective retest decides to use it.
No closure outcome is read.

What is measured. Each EAP file is a snapshot "as of November 1" of fall
year Y and has one row per institution and staff category (EAPCAT), with
full-time (EAPFT), part-time (EAPPT) and total (EAPTOT) headcounts. The
category for all instructional staff is found by its label in that year's
data dictionary, never by an assumed code, because the codes have changed
over time; the run stops if the label does not identify exactly one code.
The full-time share is EAPFT / (EAPFT + EAPPT) for that category. Fall
year Y belongs to academic year Y-(Y+1), whose fiscal year ends in June of
Y+1, so the value is assigned to fiscal year Y+1. The current occupational
categories began with the 2012-13 collection, so files from fall 2012 on
are read.

The checks (data/meta channel/check.json) are about the measurement
itself, not about any outcome: how many institutions each year has a
value; the spread of the share overall and by sector; whether EAPTOT agrees
with EAPFT + EAPPT; how much a college's share moves from one year to the
next, and how many moves are large enough to look like reporting changes
rather than staffing changes; and how many development and v3 test
institutions have values in the years a window would use.

Usage (GitHub Actions only, via meta_channel.yml):
    cd src
    python meta_channel.py --first 2012
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import re
import statistics
import time
import zipfile
import xml.etree.ElementTree as ET

import requests

import v2_common as v2

OUT_DIR = v2.ROOT / "data" / "meta channel"
SHARE_PATH = OUT_DIR / "instructional staff share.json"
CHECK_PATH = OUT_DIR / "check.json"
BASES = ("https://nces.ed.gov/ipeds/datacenter/data/", "https://nces.ed.gov/ipeds/complete-data-files/")
WANTED = {"instructional staff total", "instructional staff", "total instructional staff",
          "all instructional staff"}
MIN_ROWS = 2000          # institutions with a value; fewer means a file was misread
JUMP = 0.30              # a year-to-year move this large is counted as a likely reporting change
SECTOR_NAMES = {"1": "public 4-year", "2": "private nonprofit 4-year", "3": "for-profit 4-year",
                "4": "public 2-year", "5": "private nonprofit 2-year", "6": "for-profit 2-year",
                "7": "public less-than-2-year", "8": "private nonprofit less-than-2-year",
                "9": "for-profit less-than-2-year"}


# ------------------------------------------------------------------ downloads
def fetch(name: str, required: bool) -> tuple[bytes, str] | None:
    last = ""
    for attempt in range(1, 4):
        for base in BASES:
            url = base + name
            try:
                r = requests.get(url, timeout=180)
                if r.status_code == 200 and r.content[:2] == b"PK":
                    return r.content, url
                last = f"HTTP {r.status_code} at {url}"
                if r.status_code == 404:
                    continue
            except requests.RequestException as e:
                last = f"{e} at {url}"
        if not required and last.startswith("HTTP 404"):
            return None
        time.sleep(15 * attempt)
    if required:
        raise SystemExit(f"Could not download {name} ({last}). Nothing recorded; run again later.")
    return None


def first_csv(content: bytes) -> tuple[str, str]:
    z = zipfile.ZipFile(io.BytesIO(content))
    names = sorted((n for n in z.namelist() if n.lower().endswith(".csv")),
                   key=lambda n: ("_rv" not in n.lower(), len(n)))   # prefer a revised (_rv) file
    if not names:
        raise SystemExit("A downloaded file held no CSV.")
    return names[0], z.read(names[0]).decode("latin-1")


def rows(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    fields = {f: f.strip().lstrip("﻿").lstrip("ï»¿").strip().upper()
              for f in (reader.fieldnames or [])}
    return [{fields[k]: (v or "").strip() for k, v in r.items() if k in fields} for r in reader]


# ------------------------------------------------------------------ the data dictionary (an .xlsx)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def xlsx_rows(content: bytes) -> list[list[str]]:
    """Every row of every sheet of the .xlsx inside a dictionary zip, as text cells."""
    outer = zipfile.ZipFile(io.BytesIO(content))
    books = [n for n in outer.namelist() if n.lower().endswith(".xlsx")]
    if not books:
        return []
    z = zipfile.ZipFile(io.BytesIO(outer.read(books[0])))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    out = []
    for n in sorted(x for x in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", x)):
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
                out.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return out


def eapcat_labels(dict_zip: bytes) -> dict[str, str]:
    """The EAPCAT code -> label table from a dictionary's frequencies sheet."""
    labels, header = {}, None
    for r in xlsx_rows(dict_zip):
        low = [c.lower() for c in r]
        if "varname" in low and "codevalue" in low and "valuelabel" in low:
            header = (low.index("varname"), low.index("codevalue"), low.index("valuelabel"))
            continue
        if header and len(r) > max(header) and r[header[0]].upper() == "EAPCAT":
            code = r[header[1]]
            if code.endswith(".0"):
                code = code[:-2]
            labels[code] = r[header[2]]
    return labels


def norm(label: str) -> str:
    return " ".join(re.sub(r"[^a-z ]", " ", label.lower()).split())


def instructional_code(labels: dict[str, str], year: int) -> tuple[str, str]:
    hits = [(c, l) for c, l in labels.items() if norm(l) in WANTED]
    if len(hits) != 1:
        near = {c: l for c, l in labels.items() if "instruct" in l.lower()}
        raise SystemExit(f"EAP{year}: the dictionary does not identify exactly one all-instructional-staff "
                         f"category (matches: {hits}; labels mentioning instruction: {near}). Nothing recorded.")
    return hits[0]


def number(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ one year
def read_year(year: int, required: bool) -> dict | None:
    got = fetch(f"EAP{year}.zip", required)
    if got is None:
        return None
    data, url = got
    dict_got = fetch(f"EAP{year}_Dict.zip", True)
    labels = eapcat_labels(dict_got[0])
    if not labels:
        raise SystemExit(f"EAP{year}: no EAPCAT codes were read from the data dictionary. Nothing recorded.")
    code, label = instructional_code(labels, year)
    name, text = first_csv(data)
    values, mismatch, no_staff = {}, 0, 0
    for r in rows(text):
        if r.get("EAPCAT") != code or not r.get("UNITID"):
            continue
        ft, pt, tot = number(r.get("EAPFT")), number(r.get("EAPPT")), number(r.get("EAPTOT"))
        if ft is None and pt is None:
            continue
        ft, pt = ft or 0.0, pt or 0.0
        if ft + pt <= 0:
            no_staff += 1
            continue
        if tot is not None and abs(tot - (ft + pt)) > 0.5:
            mismatch += 1
        values[r["UNITID"]] = [int(ft), int(pt)]
    if len(values) < MIN_ROWS:
        raise SystemExit(f"EAP{year} yielded {len(values)} institutions (fewer than {MIN_ROWS}); "
                         "it was not read correctly. Nothing recorded.")
    return {"file": {"table": f"EAP{year}", "url": url, "csv": name,
                     "zip sha256": hashlib.sha256(data).hexdigest(),
                     "dictionary url": dict_got[1],
                     "instructional staff category": {"EAPCAT": code, "label": label}},
            "values": values,
            "counts": {"institutions with a value": len(values),
                       "rows with no instructional staff": no_staff,
                       "rows where EAPTOT differs from EAPFT + EAPPT": mismatch}}


# ------------------------------------------------------------------ checks
def quantiles(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    xs = sorted(xs)
    q = lambda p: round(xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))], 3)
    return {"n": len(xs), "min": round(xs[0], 3), "10%": q(0.1), "25%": q(0.25), "median": q(0.5),
            "75%": q(0.75), "90%": q(0.9), "max": round(xs[-1], 3), "mean": round(statistics.fmean(xs), 3)}


def sectors() -> dict:
    """SECTOR from the most recent institutional header file NCES serves."""
    for y in range(datetime.date.today().year, 2017, -1):
        got = fetch(f"HD{y}.zip", False)
        if got:
            _, text = first_csv(got[0])
            return {"file": f"HD{y}", "sector": {r["UNITID"]: r.get("SECTOR", "") for r in rows(text)}}
    return {"file": None, "sector": {}}


def frames() -> dict:
    out = {}
    draw = v2.ROOT / "data" / "v3" / "test draw.json"
    if draw.exists():
        out["v3 test institutions"] = {i["unitid"] for i in json.loads(draw.read_text())["institutions"]}
    dev = set()
    for name in ("training scores", "test scores"):
        for p in sorted((v2.V2_DIR / name).glob("batch_*.json")):
            dev |= {r["unitid"] for r in json.loads(p.read_text())["results"] if r["status"] == "scored"}
    if dev:
        out["v3 development institutions"] = dev
    return out


def checks(years: dict, sec: dict) -> dict:
    fy = sorted(years)
    share = {y: {u: ft / (ft + pt) for u, (ft, pt) in years[y]["values"].items()} for y in fy}
    latest = fy[-1]
    by_sector = {}
    for code, label in SECTOR_NAMES.items():
        xs = [s for u, s in share[latest].items() if sec["sector"].get(u) == code]
        by_sector[label] = quantiles(xs)
    moves, jumps, pairs = [], 0, 0
    jump_examples = []
    for a, b in zip(fy, fy[1:]):
        for u in share[a].keys() & share[b].keys():
            d = abs(share[b][u] - share[a][u])
            moves.append(d)
            pairs += 1
            if d >= JUMP:
                jumps += 1
                if len(jump_examples) < 25:
                    jump_examples.append({"unitid": u, "fall years": [a, b],
                                          "shares": [round(share[a][u], 3), round(share[b][u], 3)],
                                          "headcounts (full-time, part-time)": [years[a]["values"][u],
                                                                               years[b]["values"][u]]})
    coverage = {}
    last11 = fy[-11:]
    for name, ids in frames().items():
        n_years = [sum(u in share[y] for y in last11) for u in ids]
        coverage[name] = {"institutions": len(ids),
                          "with a value in the latest year": sum(u in share[latest] for u in ids),
                          f"with values in all of fall {last11[0]}-{last11[-1]}": sum(n == len(last11) for n in n_years),
                          f"with no value in fall {last11[0]}-{last11[-1]}": sum(n == 0 for n in n_years)}
    return {"years read (fall)": fy,
            "fiscal years they are assigned to": [y + 1 for y in fy],
            "per year": {str(y): {**years[y]["counts"], "share": quantiles(list(share[y].values()))} for y in fy},
            f"by sector, fall {latest} (sector from {sec['file']})": by_sector,
            "year-to-year change in an institution's share": {
                "pairs of consecutive years": pairs, "change": quantiles(moves),
                f"changes of {JUMP} or more": jumps,
                f"share of changes of {JUMP} or more": round(jumps / pairs, 4) if pairs else None,
                "first examples of large changes": jump_examples},
            "coverage of the tracker's institutions": coverage}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2012)
    a = ap.parse_args()
    if a.first < 2012:
        raise SystemExit("Files before fall 2012 use the old staff categories and are not read.")
    years, not_served = {}, []
    y = a.first
    while y <= datetime.date.today().year:
        got = read_year(y, required=(y <= 2023))
        if got is None:
            not_served.append(f"EAP{y}")
        else:
            years[y] = got
        y += 1
    sec = sectors()
    v2.write_json(SHARE_PATH, {
        "measure": "full-time share of all instructional staff, EAPFT / (EAPFT + EAPPT); "
                   "values are [full-time, part-time] headcounts; fall year Y is fiscal year Y+1",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "files": [years[y]["file"] for y in sorted(years)],
        "files not served": not_served,
        "by fall year": {str(y): years[y]["values"] for y in sorted(years)},
    })
    v2.write_json(CHECK_PATH, {
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": "Checks of the measurement only; no closure outcome is read.",
        **checks(years, sec)})
    print(json.dumps(json.loads(CHECK_PATH.read_text())["per year"], indent=1))


def series(share_file: dict, unitid: str, fiscal_years: list[int]):
    """For a scoring window: (pt_share_obs, pt_share_mask) aligned to fiscal_years, as
    model.build_model_stage2 takes them. Years without a value are masked out, never filled."""
    import numpy as np
    obs = np.zeros(len(fiscal_years))
    mask = np.zeros(len(fiscal_years), dtype=bool)
    by_year = share_file["by fall year"]
    for i, fy in enumerate(fiscal_years):
        v = by_year.get(str(fy - 1), {}).get(unitid)
        if v and sum(v) > 0:
            obs[i] = v[1] / (v[0] + v[1])
            mask[i] = True
    return obs, mask


if __name__ == "__main__":
    main()
