"""
Item 22, first step: count the two-year colleges an interim pre-registered
test of tracker v4 would cover, before any protocol is written and without
looking up any outcome.

Reads only the 2019 header file (HD2019): every degree-granting two-year
institution (SECTOR 4, 5 or 6; DEGGRANT 1) active in 2019, by sector and
state, with public two-year colleges in Texas counted separately and left
out of the test frame (the Texas transfer test already used them). No later
header file is read, so nothing about closures is seen.

Output: data/v4 two-year/count.json

Usage (GitHub Actions only, via v4_two_year_count.yml):
    cd src
    python "v4 two-year count.py"
"""

from __future__ import annotations

import datetime
import json
from collections import Counter
from pathlib import Path

import meta_channel as mc
import v2_training_outcomes as coding

OUT = Path(__file__).resolve().parent.parent / "data" / "v4 two-year" / "count.json"
SECTORS = {"4": "public two-year", "5": "private nonprofit two-year", "6": "for-profit two-year"}
FIPS_TX = "48"


def main() -> None:
    hd = coding.download_hd(2019)
    rows = [r for r in mc.rows(hd["csv"]) if r.get("SECTOR") in SECTORS and r.get("DEGGRANT") == "1"]
    if len(rows) < 1000:
        raise SystemExit(f"HD2019 yielded {len(rows)} two-year degree-granting institutions; misread. Nothing recorded.")
    tx_public = [r for r in rows if r.get("SECTOR") == "4" and r.get("FIPS") == FIPS_TX]
    frame = [r for r in rows if not (r.get("SECTOR") == "4" and r.get("FIPS") == FIPS_TX)]
    by_sector = Counter(SECTORS[r["SECTOR"]] for r in frame)
    by_state = Counter((r.get("STABBR") or r.get("FIPS"), SECTORS[r["SECTOR"]]) for r in frame)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "Item 22 first step: two-year degree-granting institutions in HD2019, counted before any protocol "
                "and without reading any later header file (no outcome seen).",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "header file": {k: v for k, v in hd.items() if k != "csv"},
        "two-year degree-granting in HD2019": len(rows),
        "Texas public two-year, left out": len(tx_public),
        "test frame": len(frame),
        "test frame by sector": dict(by_sector),
        "test frame by state and sector": {f"{s} | {sec}": n for (s, sec), n in sorted(by_state.items())},
    }, indent=1) + "\n", encoding="utf-8")
    print(len(rows), len(tx_public), len(frame), dict(by_sector))


if __name__ == "__main__":
    main()
