"""
v4 item 12: coverage count for the value dimension's candidate columns
(channel selection protocol, Amendments 8 and 10).

The item 12 field check found that the 2026 College Scorecard files no
longer carry the old three-year repayment rates (RPY_*); repayment is now
reported as borrower-based (BBRR) and dollar-based (DBRR) rates, and the
columns appear in every yearly file whether or not they hold values. Before
the primary repayment measure is fixed, this counts, for each yearly MERGED
file in the release asset, how many institutions have a non-missing entry
(not empty, NULL or PrivacySuppressed) in each candidate column: the
undergraduate federal borrower-based rates (making progress, paid in full,
borrower count) one to four years into repayment, the undergraduate federal
dollar-based rates, the two- and three-year cohort default rates, and the
median earnings columns. Only presence is counted: no value is used,
summarized or joined to anything, and no outcome is read.

Output: data/v4 channels/item 12 coverage count.json.

Usage (GitHub Actions only, via v4_item12_coverage_count.yml):
    cd src
    python "v4 item 12 coverage count.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import io
import json
import re
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "v4 channels" / "item 12 coverage count.json"
_spec = importlib.util.spec_from_file_location("fc12", HERE / "v4 item 12 field check.py")
fc12 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc12)

CANDIDATE = re.compile(r"^(BBRR\d_FED_UG_(MAKEPROG|PAIDINFULL|N)|DBRR\d+_FED_UG_RT|CDR[23]|"
                       r"MD_EARN_WNE_(P\d+|\d+YR))$")
MISSING = {"", "NULL", "PRIVACYSUPPRESSED", "NA"}


def main() -> None:
    zpath, url = fc12.download_asset()
    by_year = {}
    with zipfile.ZipFile(zpath) as zf:
        for n in sorted(zf.namelist()):
            m = fc12.bsc.NAME_RE.search(n)
            if not m or n.startswith("__MACOSX") or "/._" in n or n.startswith("._"):
                continue
            with zf.open(n) as raw:
                reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"))
                header = [h.strip().lstrip("﻿").upper() for h in next(reader)]
                idx = {c: i for i, c in enumerate(header) if CANDIDATE.match(c)}
                counts, rows = {c: 0 for c in idx}, 0
                for row in reader:
                    rows += 1
                    for c, i in idx.items():
                        if i < len(row) and row[i].strip().upper() not in MISSING:
                            counts[c] += 1
            by_year[m.group(1)] = {"file": n, "institutions (rows)": rows, "non-missing by column": counts}
            print(n, rows, sum(1 for v in counts.values() if v), "columns with any value", flush=True)
    zpath.unlink()
    if not by_year:
        raise SystemExit("No yearly MERGED file found. Nothing recorded.")
    cols = sorted({c for d in by_year.values() for c in d["non-missing by column"]})
    first_with_values = {c: next((y for y, d in sorted(by_year.items()) if d["non-missing by column"].get(c, 0) > 0), None)
                         for c in cols}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "Coverage count for item 12's value columns: presence only; no value used, no outcome read.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "downloaded from": url, "sha256": fc12.bsc.EXPECTED_SHA256,
        "first file year with any value, by column": first_with_values,
        "non-missing in the files for scoring years 2014 and 2019 (file years 2013 and 2018)": {
            c: {y: by_year.get(y, {}).get("non-missing by column", {}).get(c) for y in ("2013", "2018")} for c in cols},
        "by file year": by_year}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(first_with_values, indent=1))


if __name__ == "__main__":
    main()
