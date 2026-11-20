"""
Item 15 (ending types), step 0: check the IPEDS fields before anything is
built or any value is read.

For every table the ending-types measurement needs, and every year from
--first to --last, downloads the data dictionary only (never the data,
never an outcome) and records the table's full variable list (name and
title), so that every field the build uses can be named from the
dictionary itself, year by year, including where the forms changed:

  finance, public (F1A)          net tuition and fees, total expenses,
                                 federal, state and local appropriations,
                                 gifts, endowment (beginning and end)
  finance, private nonprofit (F2) net tuition and fees, total expenses,
                                 appropriations, private gifts and
                                 contributions, endowment (beginning and
                                 end of year, and the spending
                                 distribution, reported from fiscal 2020)
  finance, for-profit (F3)       net tuition and fees, total expenses
                                 (and total revenues, the existing
                                 fallback)
  12-month enrollment (EFIA)     12-month full-time-equivalent enrollment

It also records, for each concept above, which variables in each year's
dictionary have a title matching that concept, so a field renamed or
renumbered between years shows up here rather than as a silent gap.

Output: data/ending types/field check.json. Nothing is fitted or scored,
and no closure outcome is read.

Usage (GitHub Actions only, via ending_types_field_check.yml):
    cd src
    python "ending types field check.py" --first 2004 --last 2024
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
OUT = HERE.parent / "data" / "ending types" / "field check.json"
_spec = importlib.util.spec_from_file_location("fieldcheck", HERE / "v4 field check.py")
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)
VAR = re.compile(r"^[A-Z][A-Z0-9_]{1,15}$")

# Concepts the build needs, matched against each variable's title (case ignored).
CONCEPTS = {
    "F_F1A": {
        "net tuition and fees": r"tuition and fees",
        "total expenses": r"total expenses",
        "appropriations (federal, state, local)": r"appropriations",
        "gifts": r"gift",
        "endowment": r"endowment",
    },
    "F_F2": {
        "net tuition and fees": r"tuition and fees",
        "total expenses": r"total expenses",
        "appropriations (federal, state, local)": r"appropriations",
        "gifts and contributions": r"gift|contribution",
        "endowment": r"endowment",
        "spending distribution": r"spending",
    },
    "F_F3": {
        "net tuition and fees": r"tuition and fees",
        "total expenses": r"total expenses",
        "total revenues": r"total revenues",
        "appropriations (federal, state, local)": r"appropriations",
    },
    "EFIA": {
        "12-month FTE enrollment": r"full-time equivalent|\bFTE\b",
    },
}


def tables(y: int) -> dict[str, str]:
    a, b = y % 100, (y + 1) % 100
    return {"F_F1A": f"F{a:02d}{b:02d}_F1A", "F_F2": f"F{a:02d}{b:02d}_F2", "F_F3": f"F{a:02d}{b:02d}_F3",
            "EFIA": f"EFIA{y}"}


def variables(name: str) -> dict:
    got = mc.fetch(f"{name}_Dict.zip", False)
    if got is None:
        return {"status": "not served"}
    try:
        rows, fmt = fc.dictionary_rows(got[0])
    except Exception as e:  # an unreadable dictionary is recorded, never guessed
        return {"status": "dictionary unreadable", "error": str(e)[:300], "dictionary url": got[1]}
    found = {}
    for r in rows:
        cells = [c.strip() for c in r]
        # variable-list rows: varnumber | VARNAME | type | width | format | imputation var | title
        if len(cells) >= 6 and VAR.match(cells[1]) and cells[2] in ("N", "A") and cells[1] not in found:
            found[cells[1]] = cells[-1][:200]
    return {"status": "read" if found else "dictionary " + fmt, "format": fmt, "dictionary url": got[1],
            "variables": found}


def concept_matches(key: str, entry: dict) -> dict:
    vs = entry.get("variables", {})
    return {c: {v: t for v, t in vs.items() if re.search(p, t, re.I)} for c, p in CONCEPTS[key].items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2004)
    ap.add_argument("--last", type=int, default=2024)
    a = ap.parse_args()
    result, matches = {}, {}
    for y in range(a.first, a.last + 1):
        for key, name in tables(y).items():
            entry = {"file": name} | variables(name)
            result.setdefault(key, {})[str(y)] = entry
            if entry["status"] == "read":
                matches.setdefault(key, {})[str(y)] = concept_matches(key, entry)
            print(y, key, name, entry["status"], len(entry.get("variables", {})), flush=True)
    if not any(v["status"] == "read" for t in result.values() for v in t.values()):
        raise SystemExit("No dictionary could be read; download or reader failed. Nothing recorded.")
    summary = {k: {s: [y for y, v in t.items() if v["status"] == s] for s in sorted({v["status"] for v in t.values()})}
               for k, t in result.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "Field check for item 15 (ending types): data dictionaries only; no data, no outcome.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary (table: status: years)": summary,
        "concept matches (table: year: concept: variable: title)": matches,
        "by table and year": result}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
