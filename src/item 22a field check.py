"""
Item 22a (nursing and pharmacy outcome test), step 0: check the IPEDS
completions fields before anything is built or any value is read.

For every year from --first to --last, downloads the data dictionary of
the completions file by program (C{year}_A) only (never the data, so no
outcome is read), and records:

  - the full variable list (name and title), with the variables whose
    titles match what the outcome needs: the program code (CIP), the award
    level, the first or second major, and total completions;
  - every value label in the dictionary for the program codes the test
    would use, so a code change between CIP editions shows up here rather
    than as a silent gap: registered nursing (51.3801 in CIP 2010 and 2020;
    its CIP 2000 predecessor 51.1601), practical nursing (51.3901; CIP 2000
    51.1613), and pharmacy (51.2001, Doctor of Pharmacy; and the rest of
    51.20).

Output: data/item 22a/field check.json. Nothing is fitted or scored.

Usage (GitHub Actions only, via item22a_field_check.yml):
    cd src
    python "item 22a field check.py" --first 2008 --last 2024
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import re
from pathlib import Path

import meta_channel as mc

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "item 22a" / "field check.json"
_spec = importlib.util.spec_from_file_location("fieldcheck", HERE / "v4 field check.py")
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)
VAR = re.compile(r"^[A-Z][A-Z0-9_]{1,15}$")
CONCEPTS = {
    "program code (CIP)": r"\bCIP\b|classification of instructional programs",
    "award level": r"award level",
    "first or second major": r"major",
    "total completions": r"grand total|total awards|total completions",
}
CODES = re.compile(r"\b51\.(38\d\d|1601|1613|39\d\d|20\d\d)\b")


def variables(name: str) -> dict:
    got = mc.fetch(f"{name}_Dict.zip", False)
    if got is None:
        return {"status": "not served"}
    try:
        rows, fmt = fc.dictionary_rows(got[0])
    except Exception as e:  # an unreadable dictionary is recorded, never guessed
        return {"status": "dictionary unreadable", "error": str(e)[:300], "dictionary url": got[1]}
    found, codes = {}, {}
    for r in rows:
        cells = [c.strip() for c in r]
        if len(cells) >= 6 and VAR.match(cells[1]) and cells[2] in ("N", "A") and cells[1] not in found:
            found[cells[1]] = cells[-1][:200]
        line = " | ".join(c for c in cells if c)
        for m in CODES.finditer(line):
            codes.setdefault(m.group(0), line[:240])
    return {"status": "read" if found else "dictionary " + fmt, "format": fmt, "dictionary url": got[1],
            "variables": found, "program codes in the value labels": dict(sorted(codes.items()))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2008)
    ap.add_argument("--last", type=int, default=2024)
    a = ap.parse_args()
    result, matches = {}, {}
    for y in range(a.first, a.last + 1):
        name = f"C{y}_A"
        entry = {"file": name} | variables(name)
        result[str(y)] = entry
        if entry["status"] == "read":
            vs = entry["variables"]
            matches[str(y)] = {c: {v: t for v, t in vs.items() if re.search(p, t, re.I)} for c, p in CONCEPTS.items()}
        print(y, name, entry["status"], len(entry.get("variables", {})),
              len(entry.get("program codes in the value labels", {})), flush=True)
    if not any(v["status"] == "read" for v in result.values()):
        raise SystemExit("No dictionary could be read; download or reader failed. Nothing recorded.")
    summary = {s: [y for y, v in result.items() if v["status"] == s] for s in sorted({v["status"] for v in result.values()})}
    codes_by_year = {y: sorted(v.get("program codes in the value labels", {})) for y, v in result.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "Field check for item 22a: completions data dictionaries only; no data, no outcome.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary (status: years)": summary,
        "program codes found in each year's value labels": codes_by_year,
        "concept matches (year: concept: variable: title)": matches,
        "by year": result}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "codes": codes_by_year}, indent=1))


if __name__ == "__main__":
    main()
