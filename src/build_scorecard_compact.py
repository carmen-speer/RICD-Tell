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
# The file name carries its release date and changes with each release; if
# this one is gone, copy the new "All Data Files" link from that page here.
ALL_DATA_URL = "https://ed-public-download.scorecard.network/downloads/College_Scorecard_Raw_Data_11022026.zip"
# The same file under the download site's older host name, tried second.
FALLBACK_URLS = [ALL_DATA_URL.replace("ed-public-download.scorecard.network", "ed-public-download.app.cloud.gov")]
COLUMNS = ["UGDS", "C150_4", "TUITIONFEE_IN", "ADM_RATE"]
NAME_RE = re.compile(r"MERGED(\d{4})_\d{2}_PP\.csv$", re.I)
# The download server refused the first attempt (HTTP 403, 2026-11-12), made
# as a bare HEAD request with Python's default User-Agent; a plain GET with
# a browser-style User-Agent is what a browser sends.
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    zpath = out.parent / "scorecard_all_data.zip"
    url, sha, failures = None, None, []
    for candidate in [ALL_DATA_URL] + FALLBACK_URLS:
        print(f"Downloading {candidate}", flush=True)
        try:
            with requests.get(candidate, stream=True, timeout=600, headers=HEADERS) as r:
                if r.status_code != 200:
                    failures.append(f"{candidate}: HTTP {r.status_code}")
                    continue
                sha = hashlib.sha256()
                with open(zpath, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                        sha.update(chunk)
                url = candidate
                break
        except requests.RequestException as e:
            failures.append(f"{candidate}: {type(e).__name__}: {e}")
    if url is None:
        raise SystemExit("Could not download the College Scorecard file. " + " | ".join(failures)
                         + " | If it has been renamed, copy the current link from https://collegescorecard.ed.gov/data/.")

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
