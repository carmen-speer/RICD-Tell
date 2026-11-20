"""
v4 soundness dimension (Spine §15.2.1, Definitions 15.2.15 and 15.2.16):
check the IPEDS fields before anything is built.

For every table the soundness readings need, and every year from --first
to --last, downloads the data dictionary only (never the data, never an
outcome) and records the table's full variable list (name and title), so
that every field the build uses can be named from the dictionary itself:

  meta (exit)        full-time staff headcount, all occupations, fall t
                     (Human Resources S{y}_OC), full-time new hires
                     (S{y}_NH), and the employees-by-position file (EAP{y})
                     as a cross-check
  operational        total revenues and total expenses by finance form
                     (F1A, F2, F3), for operating coverage B_cov
  wealth bands       endowment assets (F1A, F2) and state appropriations
                     (F1A), for the exit norm's wealth bands

Output: data/v4 channels/soundness field check.json. Nothing is fitted or
scored, and no closure outcome is read.

Usage (GitHub Actions only, via v4_soundness_field_check.yml):
    cd src
    python "v4 soundness field check.py" --first 2011 --last 2024
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
OUT = HERE.parent / "data" / "v4 channels" / "soundness field check.json"
_spec = importlib.util.spec_from_file_location("fieldcheck", HERE / "v4 field check.py")
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)
VAR = re.compile(r"^[A-Z][A-Z0-9_]{1,15}$")


def tables(y: int) -> dict[str, str]:
    a, b = y % 100, (y + 1) % 100
    return {"S_OC": f"S{y}_OC", "S_NH": f"S{y}_NH", "EAP": f"EAP{y}",
            "F_F1A": f"F{a:02d}{b:02d}_F1A", "F_F2": f"F{a:02d}{b:02d}_F2", "F_F3": f"F{a:02d}{b:02d}_F3"}


def variables(name: str) -> dict:
    got = mc.fetch(f"{name}_Dict.zip", False)
    if got is None:
        return {"status": "not served"}
    rows, fmt = fc.dictionary_rows(got[0])
    found, codes = {}, {}
    for r in rows:
        cells = [c.strip() for c in r]
        # variable-list rows: varnumber | VARNAME | type | width | format | imputation var | title
        if len(cells) >= 6 and VAR.match(cells[1]) and cells[2] in ("N", "A") and cells[1] not in found:
            found[cells[1]] = cells[-1][:200]
        # frequency rows: varnumber | VARNAME | code | label | frequency | percent
        elif len(cells) >= 4 and VAR.match(cells[1]) and re.fullmatch(r"-?\d+", cells[2]) and cells[3]:
            codes.setdefault(cells[1], {})[cells[2]] = cells[3][:150]
    return {"status": "read" if found else "dictionary " + fmt, "format": fmt, "dictionary url": got[1],
            "variables": found, "code labels": {k: v for k, v in codes.items() if len(v) <= 60}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2011)
    ap.add_argument("--last", type=int, default=2024)
    a = ap.parse_args()
    result = {}
    for y in range(a.first, a.last + 1):
        for key, name in tables(y).items():
            result.setdefault(key, {})[str(y)] = {"file": name} | variables(name)
            print(y, key, name, result[key][str(y)]["status"], len(result[key][str(y)].get("variables", {})), flush=True)
    if not any(v["status"] == "read" for t in result.values() for v in t.values()):
        raise SystemExit("No dictionary could be read; download or reader failed. Nothing recorded.")
    summary = {k: {s: [y for y, v in t.items() if v["status"] == s] for s in sorted({v["status"] for v in t.values()})}
               for k, t in result.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "Field check for the v4 soundness dimension: data dictionaries only; no data, no outcome.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary (table: status: years)": summary, "by table and year": result}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
