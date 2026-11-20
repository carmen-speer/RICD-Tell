"""
Item 15 (exploratory): ending types, drift-type against shock-type
approaches to collapse, under "ending types protocol.md" (committed before
any finance, enrollment or closure value was read).

For every degree-granting college in the IPEDS header files from HD2005,
and every fiscal year 2005 onward, reads:

  W       total expenses           F1D02 / F2B02 / F3B02 (F3D09 fallback, flagged)
  E_exch  net tuition and fees     F1B01 / F2D01 / F3D01
  N       12-month FTE enrollment  EFTEUG + EFTEGD (EFIA, IPEDS-estimated)
  A       anchor capacity, by source (federal, state, local appropriations;
          gifts; endowment spending), as section 7 of the protocol fixes:
            public            F1B10, F1B11, F1B12, F1B16 (no endowment)
            private nonprofit F2D02, F2D03, F2D04; F2D08A + F2D09 from fiscal
                              2008, F2D08 + F2D09 before (flagged: includes
                              grants and contracts); F2H03C from fiscal 2020,
                              0.045 x F2H01 before (flagged: estimate)
            for-profit        not observable (missing, never zero)

and computes coverage c = W / E_exch, gap coverage g = W / (E_exch + A),
each college-year's state (self-covering, held up by anchors, short beyond
its anchors), the anchored share A / (W - E_exch) and its split by source
(who carries the strain), and the sectors' totals by source each year.

Then, for Sweet Briar College (window ends fiscal 2015, the closure
announcement), the University of Phoenix (all campuses named "University
of Phoenix" summed; approach to date, no type), and every college with a
documented closure 2005 onward (grounds a or b of the tracker's outcome
coding; combined into another institution, ground c, and disappearances
with no record, ground d, are not closures and are counted separately),
decomposes the change in log g (primary) and log c (check) over the window
into a drift part, a jump part and a gap part, and classifies the approach
as shock-type, drift-type, mixed or too short to classify (protocol
section 5).

Exploratory: the outcomes are known. The rule is frozen for the retest.

Outputs, in data/ending types/:
  results.json                       summary counts, settings, files read
  closures.csv                       one row per documented closure
  named cases.json                   Sweet Briar and Phoenix: series and decompositions
  closures series.csv                every measured college-year (closures and named cases)
  strain by source, sector totals.csv

Usage (GitHub Actions only, via ending_types.yml):
    cd src
    python "ending types.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import v2_training_outcomes as coding

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "data" / "ending types"
FIRST_FY, LAST_FY = 2005, 2024          # finance: F0405 (fiscal 2005) to F2324 (fiscal 2024)
FIRST_HD, LAST_HD = 2005, 2026
MIN_FIN_ROWS, MIN_F1A_ROWS, MIN_HD_ROWS, MIN_EF_ROWS = 1000, 500, 3000, 3000
SWEET_BRIAR = "Sweet Briar College"
SWEET_BRIAR_LAST_FY = 2015
PHOENIX_PREFIX = "University of Phoenix"
DRAW = 0.045                             # pre-2020 endowment draw estimate
GIFTS_ALONE_FROM = 2008                  # F2D08A first reported (F0708)
SPENDING_FROM = 2020                     # F2H03C first reported (F1920)
JUMP_SDS = 3.0
MIN_CHANGES = 5

_s = importlib.util.spec_from_file_location("step1", HERE / "v4 step 1 calibrations.py")
s1 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(s1)
_o = importlib.util.spec_from_file_location("oc", HERE / "openings and closures.py")
oc = importlib.util.module_from_spec(_o)
_o.loader.exec_module(oc)
num = s1.num

SECTOR = {"1": "public", "2": "private nonprofit", "3": "for-profit"}
SOURCES = ("federal appropriations", "state appropriations", "local appropriations", "gifts", "endowment spending")


# ------------------------------------------------------------------ reading
def headers() -> tuple[dict, dict, list]:
    tables, used, missing = {}, {}, []
    for y in range(FIRST_HD, LAST_HD + 1):
        try:
            hd = coding.download_hd(y)
        except SystemExit:
            if y < 2025:
                raise SystemExit(f"HD{y} could not be downloaded; a gap mid-span would misdate closures. Nothing recorded.")
            missing.append(f"HD{y}")
            continue
        t, _ = oc.read_table(hd["csv"])
        if len(t) < MIN_HD_ROWS:
            raise SystemExit(f"HD{y} yielded {len(t)} institutions; misread. Nothing recorded.")
        tables[y] = t
        used[f"HD{y}"] = {"url": hd["url"], "zip sha256": hd["zip sha256"], "institutions read": len(t)}
    return tables, used, missing


def first(row: dict, *codes) -> float | None:
    vals = [num(row.get(c)) for c in codes]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def finance(log: dict) -> dict:
    """{unitid: {fy: record}} from the three forms."""
    out: dict = defaultdict(dict)
    for fy in range(FIRST_FY, LAST_FY + 1):
        a, b = (fy - 1) % 100, fy % 100
        for form in ("F1A", "F2", "F3"):
            name = f"F{a:02d}{b:02d}_{form}"
            t = s1.table(name)
            if t is None:
                log[name] = "not served"
                if fy < LAST_FY:
                    raise SystemExit(f"{name} not served; a gap mid-span. Nothing recorded.")
                continue
            if len(t) < (MIN_FIN_ROWS if form != "F1A" else MIN_F1A_ROWS):
                raise SystemExit(f"{name}: only {len(t)} rows read. Nothing recorded.")
            log[name] = len(t)
            for u, rows in t.items():
                r = rows[0]
                rec = {"form": form, "flags": []}
                if form == "F1A":
                    rec |= {"W": num(r.get("F1D02")), "E": num(r.get("F1B01")),
                            "federal appropriations": num(r.get("F1B10")), "state appropriations": num(r.get("F1B11")),
                            "local appropriations": num(r.get("F1B12")), "gifts": num(r.get("F1B16")),
                            "endowment begin": None, "spending": None}
                elif form == "F2":
                    if fy >= GIFTS_ALONE_FROM:
                        gifts = first(r, "F2D08A", "F2D09")
                    else:
                        gifts = first(r, "F2D08", "F2D09")
                        rec["flags"].append("gifts include grants and contracts")
                    rec |= {"W":
