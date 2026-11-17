"""
One-off diagnostic: downloads a single real IPEDS F3 (for-profit)
bulk finance file using the same fetch_live_data.download_ipeds_finance_bulk
function the live pipeline already calls, then prints its real column
headers and the actual row for a given institution (University of
Phoenix-Arizona, UNITID 484613, by default) verbatim.

Why this exists: score_institution.py and fetch_live_data.parse_live_finance
currently only branch on sector == "private" vs. everything else, so a
"forprofit" institution's real F3-form data gets parsed using
PUBLIC_FINANCE_FIELDS (the public F1A form's column codes) instead of
its own real F3 codes. Those columns don't exist in an F3 file, so
every year silently fails to parse and the institution comes back
"insufficient_data" -- not because the data is missing, but because
the wrong field codes are being looked up.

The real, current F3 field codes could not be confirmed from published
IPEDS documentation alone: the for-profit finance form has been
revised more than once (a 2013 revision alone added a research/
public-service expense breakout), and the specific current-year
package covering degree-granting for-profit institutions specifically
could not be located through NCES's own published survey materials.
Rather than guess and risk a second, harder-to-spot silent failure,
this script prints the real column names directly from a real,
just-downloaded file, so fetch_live_data.py can be fixed with
confirmed codes instead of guessed ones.

Only runs from GitHub Actions, same as the rest of the live pipeline --
nces.ed.gov is not reachable from the sandboxed environments used to
develop this code.

Usage: python diagnose_f3_fields.py [year] [unitid]
  year   -- fiscal year to check, e.g. 2022 (default: 2022)
  unitid -- UNITID to look up in the file (default: 484613, University
            of Phoenix-Arizona)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import fetch_live_data as fld


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    unitid = sys.argv[2] if len(sys.argv) > 2 else "484613"  # University of Phoenix-Arizona

    dest_dir = f"/tmp/diagnose_f3/{year}"
    print(f"Downloading the real F3 (for-profit) bulk finance file for FY{year}...")
    result = fld.download_ipeds_finance_bulk(year, dest_dir=dest_dir, sector="forprofit")
    if result is None:
        print(
            f"DOWNLOAD FAILED for FY{year} -- this is itself real information: try a "
            f"different year. NCES only keeps the newest year or two at the current "
            f"URL pattern; older years need the fallback pattern already in "
            f"fetch_live_data.py, which this script also exercises."
        )
        sys.exit(1)

    year_dir = Path(dest_dir) / str(year)
    csv_files = list(year_dir.glob("*.csv"))
    if not csv_files:
        print(f"Download reported success but no CSV file was found under {year_dir} -- inspect manually.")
        sys.exit(1)

    csv_path = csv_files[0]
    print(f"\nReal file downloaded to: {csv_path}\n")

    with open(csv_path, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        print(f"REAL COLUMN HEADERS ({len(fieldnames)} total):")
        for name in fieldnames:
            print(f"  {name}")

        print(f"\nSearching for UNITID {unitid}...")
        for row in reader:
            if row.get("UNITID") == unitid:
                print(f"\nREAL ROW FOR UNITID {unitid}:")
                for key, value in row.items():
                    print(f"  {key}: {value}")
                break
        else:
            print(
                f"UNITID {unitid} was not found in this file -- it may not be in the "
                f"for-profit finance universe for FY{year}, or the download returned "
                f"the wrong form. Not fabricating a match."
            )


if __name__ == "__main__":
    main()
