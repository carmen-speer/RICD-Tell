"""
v4 channel inputs: check every IPEDS field against each year's data
dictionary before anything is built (RICD 17.7, Spine §15.2.1, Definitions
15.2.4 to 15.2.13: "the field for each reporting form is verified against
each year's data dictionary before building").

What it does. For every IPEDS table the three claim gaps of item 10 need,
and every year from --first to --last, it downloads the data dictionary
only (never the data, never an outcome), reads every row of every sheet,
and records each row that matches one of the input concepts below, with
the table, year and dictionary URL. A table or year that NCES does not
serve is recorded as missing; a dictionary in an older format that cannot
be read (.xls) is recorded as unread, not guessed.

The concepts (what the gaps need):
  price      published tuition and fees (IC_AY), students paying in-state
             and out-of-state rates (EF C, residence of first-time
             students), net tuition revenue (Finance F1A, F2, F3), and
             full-time-equivalent enrollment (EFIA)
  need       first-time, full-time federal-aid recipients by family-income
             band, and the Pell share (SFA)
  outcome    completion within 100% and 150% of normal time, and transfer-
             outs (GR); award and "enrolled at another institution" rates
             at four, six and eight years (OM); retention (EF D)
  mission    the mission statement (IC MISSION), for transfer-mission
             coding
Output: data/v4 channels/field check.json. Nothing is fitted or scored,
and no closure outcome is read.

Usage (GitHub Actions only, via v4_field_check.yml):
    cd src
    python "v4 field check.py" --first 2008 --last 2024
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import zipfile
import io
from pathlib import Path

import meta_channel as mc

OUT = Path(__file__).resolve().parent.parent / "data" / "v4 channels" / "field check.json"
CAP = 80   # matched rows kept per concept per table-year

CONCEPTS = {
    "published tuition and fees": r"tuition|required fees|\bfees\b",
    "in-state / out-of-state": r"in-state|out-of-state|in-district|residence|state of residence",
    "net tuition revenue": r"net of|after deducting|discounts and allowances|scholarship allowances|net tuition",
    "full-time equivalent": r"full-time equivalent|\bfte\b",
    "income bands (federal-aid first-time, full-time)": r"income|\$0|30,000|48,000|75,000|110,000",
    "Pell": r"\bpell\b",
    "completion 100% / 150%": r"100 percent|150 percent|100%|150%|normal time",
    "transfer-out": r"transfer",
    "Outcome Measures award / enrolled elsewhere": r"award|enrolled at another|another institution|8 years|6 years|4 years|eight years|six years|four years",
    "retention": r"retention",
    "mission": r"mission",
}


def tables(y: int) -> dict[str, str]:
    a, b = y % 100, (y + 1) % 100
    return {
        "IC_AY": f"IC{y}_AY", "IC_MISSION": f"IC{y}_MISSION",
        "EF_C": f"EF{y}C", "EF_D": f"EF{y}D", "EFIA": f"EFIA{y}",
        "F_F1A": f"F{a:02d}{b:02d}_F1A", "F_F2": f"F{a:02d}{b:02d}_F2", "F_F3": f"F{a:02d}{b:02d}_F3",
        "SFA": f"SFA{a:02d}{b:02d}", "GR": f"GR{y}", "GR200": f"GR200_{a:02d}", "OM": f"OM{y}",
    }


def dictionary_rows(content: bytes) -> tuple[list[list[str]], str]:
    names = zipfile.ZipFile(io.BytesIO(content)).namelist()
    if any(n.lower().endswith(".xlsx") for n in names):
        return mc.xlsx_rows(content), "xlsx"
    return [], "unread (" + ", ".join(sorted({Path(n).suffix.lower() or n for n in names})) + ")"


def check(name: str) -> dict:
    got = mc.fetch(f"{name}_Dict.zip", False)
    if got is None:
        return {"status": "not served"}
    content, url = got
    rows, fmt = dictionary_rows(content)
    out = {"status": "read" if rows else "dictionary " + fmt, "dictionary url": url, "rows read": len(rows),
           "matches": {}}
    for concept, pat in CONCEPTS.items():
        rx = re.compile(pat, re.I)
        hits = []
        for r in rows:
            text = " | ".join(c for c in r if c)
            if rx.search(text):
                hits.append(text[:300])
                if len(hits) >= CAP:
                    break
        if hits:
            out["matches"][concept] = hits
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2008)
    ap.add_argument("--last", type=int, default=2024)
    a = ap.parse_args()
    result = {}
    for y in range(a.first, a.last + 1):
        for key, name in tables(y).items():
            result.setdefault(key, {})[str(y)] = {"file": name, **check(name)}
            print(y, key, name, result[key][str(y)]["status"], flush=True)
    summary = {key: {s: [y for y, v in years.items() if v["status"] == s]
                     for s in sorted({v["status"] for v in years.values()})}
               for key, years in result.items()}
    if not any(v["status"] == "read" for years in result.values() for v in years.values()):
        raise SystemExit("No dictionary could be read at all; the download or the reader failed. Nothing recorded.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "Field check for the v4 channel inputs (item 10): data dictionaries only; no data, no outcome.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "concepts and patterns": CONCEPTS,
        "summary (table: status: years)": summary,
        "by table and year": result,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
