"""
v4 item 12 (channel selection protocol, Amendment 8): check the fields
for the endowment draw and the value dimension before anything is built.

Two parts, neither of which reads a value or an outcome:

  IPEDS     for every private nonprofit finance file (F{a}{b}_F2) for
            fiscal years 2009 to 2024, downloads the data dictionary only
            and records the full variable list (name and title), then lists
            the endowment variables (beginning and end values, new gifts,
            net investment return, spending distribution for current use,
            other changes) by fiscal year, so the endowment draw is built
            only from named fields and the years each is reported are known.
  Scorecard downloads the repository's release asset
            scorecard-raw-data-2026-11-02 (SHA-256 checked against the
            protocol's value), lists every file in it, records whether the
            field-of-study files item 13 needs are there, and for each
            yearly MERGED file reads the header row only and lists the
            repayment, cohort default and earnings columns it holds.

Output: data/v4 channels/item 12 field check.json. Nothing is fitted or
scored, no data row is read, and no closure outcome is read.

Usage (GitHub Actions only, via v4_item12_field_check.yml):
    cd src
    python "v4 item 12 field check.py"
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import io
import json
import re
import zipfile
from pathlib import Path

import requests

import build_scorecard_compact as bsc

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "v4 channels" / "item 12 field check.json"
WORK = HERE.parent / "work"
_spec = importlib.util.spec_from_file_location("sfc", HERE / "v4 soundness field check.py")
sfc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sfc)

FISCAL = range(2009, 2025)          # fiscal year t reads F{t-1}{t}
ENDOW = re.compile(r"endowment|spending distribution|investment return|new gifts|gifts and additions", re.I)
VALUE = re.compile(r"^(RPY_|BBRR|CDR|MD_EARN|MN_EARN|PCT\d+_EARN|GT_25K|COUNT_.*EARN|DBRR|NPV)", re.I)


def ipeds_part() -> dict:
    by_year, endow = {}, {}
    for t in FISCAL:
        a, b = (t - 1) % 100, t % 100
        name = f"F{a:02d}{b:02d}_F2"
        got = sfc.variables(name)
        by_year[str(t)] = {"file": name} | got
        endow[str(t)] = {v: title for v, title in got.get("variables", {}).items() if ENDOW.search(title)}
        print(t, name, got["status"], len(got.get("variables", {})), "endowment variables:", len(endow[str(t)]),
              flush=True)
    names = sorted({v for d in endow.values() for v in d})
    return {"endowment variables by fiscal year (name: title)": endow,
            "fiscal years each endowment variable is reported": {v: [t for t, d in endow.items() if v in d]
                                                                 for v in names},
            "full dictionaries by fiscal year": by_year}


def download_asset() -> tuple[Path, str]:
    WORK.mkdir(parents=True, exist_ok=True)
    zpath = WORK / "scorecard_all_data.zip"
    failures = []
    for url in [bsc.RELEASE_URL, bsc.ORIGINAL_URL]:
        print(f"Downloading {url}", flush=True)
        try:
            with requests.get(url, stream=True, timeout=600, headers=bsc.HEADERS) as r:
                if r.status_code != 200:
                    failures.append(f"{url}: HTTP {r.status_code}")
                    continue
                sha = hashlib.sha256()
                with open(zpath, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                        sha.update(chunk)
        except requests.RequestException as e:
            failures.append(f"{url}: {type(e).__name__}: {e}")
            continue
        if sha.hexdigest() != bsc.EXPECTED_SHA256:
            raise SystemExit(f"SHA-256 {sha.hexdigest()} is not the protocol's {bsc.EXPECTED_SHA256}. Nothing recorded.")
        return zpath, url
    raise SystemExit("Could not download the College Scorecard file. " + " | ".join(failures))


def scorecard_part() -> dict:
    zpath, url = download_asset()
    files, merged, fos = [], {}, []
    with zipfile.ZipFile(zpath) as zf:
        for info in zf.infolist():
            n = info.filename
            if n.startswith("__MACOSX") or "/._" in n or n.startswith("._") or n.endswith("/"):
                continue
            files.append({"name": n, "bytes": info.file_size})
            if re.search(r"field.?of.?study|FieldOfStudy", n, re.I):
                fos.append(n)
            m = bsc.NAME_RE.search(n)
            if m:
                with zf.open(n) as raw:
                    header = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace").readline()
                cols = [c.strip().lstrip("﻿").upper() for c in header.split(",")]
                merged[m.group(1)] = {"file": n, "columns in file": len(cols),
                                      "repayment, default and earnings columns": [c for c in cols if VALUE.match(c)]}
                print(n, len(cols), len(merged[m.group(1)]["repayment, default and earnings columns"]), flush=True)
    zpath.unlink()
    cols = sorted({c for d in merged.values() for c in d["repayment, default and earnings columns"]})
    return {"downloaded from": url, "sha256": bsc.EXPECTED_SHA256, "files in the asset": files,
            "field-of-study files (item 13)": fos,
            "yearly files: matched columns": dict(sorted(merged.items())),
            "years each matched column appears in": {c: [y for y, d in sorted(merged.items())
                                                        if c in d["repayment, default and earnings columns"]]
                                                    for c in cols}}


def main() -> None:
    ipeds = ipeds_part()
    if not any(v["status"] == "read" for v in ipeds["full dictionaries by fiscal year"].values()):
        raise SystemExit("No IPEDS dictionary could be read; download or reader failed. Nothing recorded.")
    sc = scorecard_part()
    if not sc["yearly files: matched columns"]:
        raise SystemExit("No yearly MERGED file found in the Scorecard asset. Nothing recorded.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": ("Field check for item 12 (Amendment 8): IPEDS data dictionaries and Scorecard header rows only; "
                 "no data row, no value, no outcome."),
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "IPEDS private nonprofit finance (F2)": ipeds, "College Scorecard release asset": sc},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"endowment variables": ipeds["fiscal years each endowment variable is reported"],
                      "field-of-study files": sc["field-of-study files (item 13)"],
                      "value columns": list(sc["years each matched column appears in"])}, indent=1))


if __name__ == "__main__":
    main()
