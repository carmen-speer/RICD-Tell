"""
Builds a compact College Scorecard file from the Department of
Education's "All Data Files" download, for fetch_live_data's optional
bulk source (use_bulk_scorecard). See the comment above
_BULK_SCORECARD in fetch_live_data.py for why: the College Scorecard
API returns nothing for institutions that have since closed, while the
yearly bulk files (MERGEDyyyy_yy_PP.csv) keep every institution that
reported in that year.

Output: one CSV with columns UNITID, YEAR, UGDS, C150_4, TUITIONFEE_IN,
ADM_RATE, one row per institution per year, where YEAR is the first
year in the file's name (MERGED2018_19_PP.csv -> 2018, the same year
label the pipeline uses for FY2019). Values are copied as they appear
in the files, including NULL and PrivacySuppressed, which the pipeline
reads as missing. A JSON note next to the output records the download
URL, its SHA-256 hash and when it was downloaded.

Usage (GitHub Actions; needs network access to the Scorecard download site):
    cd src
    python build_scorecard_compact.py --out ../work/scorecard_compact.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import requests

# Current link from https://collegescorecard.ed.gov/data/ (checked 2026-11-12).
# The file name carries its release date and changes with each release, so
# if this one is gone the script reads the current link off that page.
ALL_DATA_URL = "https://ed-public-download.scorecard.network/downloads/College_Scorecard_Raw_Data_11022026.zip"
DATA_PAGE = "https://collegescorecard.ed.gov/data/"
COLUMNS = ["UGDS", "C150_4", "TUITIONFEE_IN", "ADM_RATE"]
NAME_RE = re.compile(r"MERGED(\d{4})_\d{2}_PP\.csv$", re.I)


def current_url() -> str:
    r = requests.head(ALL_DATA_URL, timeout=60, allow_redirects=True)
    if r.status_code == 200:
        return ALL_DATA_URL
    page = requests.get(DATA_PAGE, timeout=60).text
    links = re.findall(r'https://[^"\']*College_Scorecard_Raw_Data[^"\']*\.zip', page)
    if not links:
        raise SystemExit(f"{ALL_DATA_URL} returned {r.status_code} and no current link was found on {DATA_PAGE}.")
    return links[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    url = current_url()
    print(f"Downloading {url}", flush=True)
    zpath = out.parent / "scorecard_all_data.zip"
    sha = hashlib.sha256()
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                sha.update(chunk)

    n_rows, years = 0, []
    with zipfile.ZipFile(zpath) as zf, open(out, "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["UNITID", "YEAR"] + COLUMNS)
        for name in sorted(zf.namelist()):
            m = NAME_RE.search(name)
            if not m:
                continue
            year = int(m.group(1))
            years.append(year)
            with zf.open(name) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"))
                reader.fieldnames = [h.strip().lstrip("\ufeff").upper() for h in reader.fieldnames]
                for row in reader:
                    w.writerow([row["UNITID"].strip(), year] + [(row.get(c) or "").strip() for c in COLUMNS])
                    n_rows += 1
            print(f"  {name}: done", flush=True)
    zpath.unlink()

    note = {"source url": url, "sha256": sha.hexdigest(),
            "downloaded at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "years": sorted(years), "rows": n_rows, "columns": ["UNITID", "YEAR"] + COLUMNS}
    out.with_suffix(".json").write_text(json.dumps(note, indent=2))
    print(f"Wrote {out}: {n_rows} rows, years {min(years)}-{max(years)}")


if __name__ == "__main__":
    main()
