"""
Item 17, follow-up (exploratory, descriptive): do heavy adjunct absorbers
show worse on-time completion than other colleges at the same wealth?

Uses only committed files, and reads no closure outcome:
  data/meta channel/adjunct absorption.json      pool share, fall 2014
  data/v4 channels/inputs.csv, soundness inputs.csv, soundness norms.json
                                                  the 2014 frame and its
                                                  control x wealth cells
  data/v4 channels/gap values at scoring years.csv
                                                  r_on (of the cohort's
                                                  bachelor's completers within
                                                  six years, the share who
                                                  finished within four:
                                                  BANC100 / BANC150) and the
                                                  four-year gap D_4yr

Heavy absorbers are assigned exactly as in the crossing-curves test (top
quarter of pool share within control and wealth tercile; for-profits one
pooled cell; colleges without a wealth value their own cell). Compared:
heavy against others on r_on and D_4yr, overall, by control and within
cells (the difference in medians within each cell, averaged with weights
equal to the cell's covered colleges), with 95% bootstrap intervals
(2,000 resamples within cells, fixed seed).

If heavy reliance on part-time instructors lowered teaching quality,
heavy absorbers should show lower on-time completion and a larger
four-year gap at equal wealth. No difference would be consistent either
with no effect or with a measure too blunt to register one.

Output: data/v3 exploratory/adjunct absorption four-year.json

Usage:
    cd src
    python "adjunct absorption four-year.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("aa", HERE / "adjunct absorption.py")
aa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aa)
OUT = HERE.parent / "data" / "v3 exploratory" / "adjunct absorption four-year.json"
SEED, BOOT = 20261126, 2000


def f(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def main() -> None:
    fr = aa.frame_2014()
    pool = json.loads(aa.OUT_MEASURES.read_text())["by fall year"][str(aa.READ_FALL)]
    have = {u: g | {"pool share": pool[u]["pool share"]} for u, g in fr.items()
            if pool.get(u, {}).get("pool share") is not None}
    cells = {}
    for u, g in have.items():
        cells.setdefault(g["cell"], []).append(u)
    for us in cells.values():
        cut = float(np.percentile([have[u]["pool share"] for u in us], 75))
        for u in us:
            have[u]["heavy"] = have[u]["pool share"] > cut
    with open(aa.DIR4 / "gap values at scoring years.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["frame"] == "2014" and r["unitid"] in have:
                have[r["unitid"]]["r_on"] = f(r["r_on"])
                have[r["unitid"]]["D_4yr"] = f(r["D_4yr"])
    rng = np.random.default_rng(SEED)

    def compare(sel, k):
        sel = [g for g in sel if g.get(k) is not None]
        h = [g[k] for g in sel if g["heavy"]]
        o = [g[k] for g in sel if not g["heavy"]]
        if len(h) < 5 or len(o) < 5:
            return {"heavy": len(h), "others": len(o), "note": "too few; not computed"}
        boots = [np.median(rng.choice(h, len(h))) - np.median(rng.choice(o, len(o))) for _ in range(BOOT)]
        return {"heavy": len(h), "others": len(o), "median, heavy": float(np.median(h)),
                "median, others": float(np.median(o)), "difference (heavy - others)": float(np.median(h) - np.median(o)),
                "95% interval": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}

    def within_cells(k):
        parts = []
        for cell, us in cells.items():
            g = [have[u] for u in us if have[u].get(k) is not None]
            h = [x[k] for x in g if x["heavy"]]
            o = [x[k] for x in g if not x["heavy"]]
            if len(h) >= 5 and len(o) >= 5:
                parts.append((h, o, len(g)))
        if not parts:
            return {"note": "no cell with five or more colleges in each group"}
        wsum = sum(p[2] for p in parts)
        est = sum((np.median(h) - np.median(o)) * n for h, o, n in parts) / wsum
        boots = []
        for _ in range(BOOT):
            boots.append(sum((np.median(rng.choice(h, len(h))) - np.median(rng.choice(o, len(o)))) * n
                             for h, o, n in parts) / wsum)
        return {"cells used": len(parts), "colleges in them": wsum,
                "weighted mean of within-cell differences (heavy - others)": float(est),
                "95% interval": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}

    groups = list(have.values())
    res = {}
    for k, label in (("r_on", "on-time share of completers (r_on)"), ("D_4yr", "four-year gap (D_4yr)")):
        res[label] = {"overall": compare(groups, k), "within control and wealth cells": within_cells(k),
                      "by control": {c: compare([g for g in groups if g["control"] == c], k)
                                     for c in ("public", "private nonprofit", "for-profit")}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "test": "Item 17 follow-up (exploratory, descriptive): on-time completion of heavy adjunct absorbers at equal wealth",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inputs": ["data/meta channel/adjunct absorption.json", "data/v4 channels/gap values at scoring years.csv",
                   "data/v4 channels/inputs.csv", "data/v4 channels/soundness inputs.csv",
                   "data/v4 channels/soundness norms.json"],
        "frame": {"2014 frame": len(fr), "with a pool share": len(have),
                  "with r_on": sum(1 for g in groups if g.get("r_on") is not None),
                  "with D_4yr": sum(1 for g in groups if g.get("D_4yr") is not None)},
        "results": res,
        "reading": ("Lower r_on and larger D_4yr at heavy absorbers would fit lower teaching quality; no difference fits "
                    "either no effect or a measure too blunt to register one. No closure outcome is read."),
        "limitations": ["The four-year gap carried no closure information beyond size and sector in channel selection.",
                        "r_on is the share of six-year bachelor's completers who finished within four years, not the share of entrants who completed; two-year and certificate colleges are not covered.",
                        "The program-length check of the four-year gap is not made (Amendment 3)."]},
        indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
