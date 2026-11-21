"""
Item 15, diagnostic (exploratory; changes no rule): is the public colleges'
apparent shortfall in "ending types.py" (about half of them short beyond
their anchors every year) an accounting effect of depreciation, a non-cash
cost public colleges book in their total expenses?

For fiscal 2005, 2010, 2015, 2020 and 2024, public (F1A) and private
nonprofit (F2) colleges, recomputes gap coverage g = W / (E_exch + A + O)
exactly as "ending types.py" does (protocol Amendments 1 and 2), once with
total expenses W and once with W less depreciation (public F1C194, renamed
F1C19DP from fiscal 2016; private F2E135), and reports the share of
colleges short beyond their anchors (g > 1) and the median g each way.
Sector is read from the form (F1A public, F2 private nonprofit). Pensions
are not tested: IPEDS has no separate pension expense field.

Output: data/ending types/depreciation test.json

Usage (GitHub Actions only, via ending_types_depreciation_test.yml):
    cd src
    python "ending types depreciation test.py"
"""

from __future__ import annotations

import copy
import datetime
import importlib.util
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
_e = importlib.util.spec_from_file_location("et", HERE / "ending types.py")
et = importlib.util.module_from_spec(_e)
_e.loader.exec_module(et)
OUT = HERE.parent / "data" / "ending types" / "depreciation test.json"
YEARS = (2005, 2010, 2015, 2020, 2024)


def main() -> None:
    et.FIRST_FY, et.LAST_FY = min(YEARS), max(YEARS)
    log: dict = {}
    fin = et.finance(log)
    result = {}
    for fy in YEARS:
        a, b = (fy - 1) % 100, fy % 100
        for form, sector, dep_codes in (("F1A", "public", ("F1C194", "F1C19DP")), ("F2", "private nonprofit", ("F2E135",))):
            t = et.s1.table(f"F{a:02d}{b:02d}_{form}") or {}
            g_with, g_without, missing_dep = [], [], 0
            for u, rows in t.items():
                rec = fin.get(u, {}).get(fy)
                if rec is None or rec.get("form") != form:
                    continue
                r1 = et.year_record(u, fy, {u: {fy: rec}}, {}, sector)
                if not r1 or not r1["valid"] or r1["g"] is None:
                    continue
                dep = next((v for c in dep_codes if (v := et.num(rows[0].get(c))) is not None), None)
                if dep is None:
                    missing_dep += 1
                    continue
                rec2 = copy.deepcopy(rec)
                rec2["W"] = rec["W"] - dep
                r2 = et.year_record(u, fy, {u: {fy: rec2}}, {}, sector)
                if not r2 or not r2["valid"] or r2["g"] is None:
                    continue
                g_with.append(r1["g"])
                g_without.append(r2["g"])
            n = len(g_with)
            result.setdefault(sector, {})[str(fy)] = {
                "colleges": n, "depreciation not reported (left out)": missing_dep,
                "share short beyond anchors, with depreciation": sum(g > 1 for g in g_with) / n if n else None,
                "share short beyond anchors, without depreciation": sum(g > 1 for g in g_without) / n if n else None,
                "median g, with depreciation": statistics.median(g_with) if n else None,
                "median g, without depreciation": statistics.median(g_without) if n else None}
            print(fy, sector, json.dumps(result[sector][str(fy)]), flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "Item 15 diagnostic (exploratory; no rule changed): public colleges' apparent shortfall with and "
                "without depreciation in total expenses.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "files read": log, "results": result}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
