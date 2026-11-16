"""
Phase 4 of "sampling protocol v3.md": the critical-slowing-down comparator.

Computed for every scored v3 test institution exactly as in the v2 test
(phase 7 of "sampling protocol v2.md"), by the first test's own function
(analyze_confirmatory.csd_indicators, imported unchanged): operating
margin, (total revenue - total expenses) / total expenses, over fiscal
years 2009-2019; linear detrending; a sliding 6-year window; Kendall's tau
for variance and for lag-1 autocorrelation; flagged when both are
positive; not computable with fewer than 8 of the 11 years.

It runs only once every v3 test institution has a committed result and
before any v3 test outcome exists. No file from after fiscal year 2019 is
opened.

Output: data/v3/comparator flags.json.

Usage (GitHub Actions only, via v3_comparator.yml):
    cd src
    python v3_comparator.py --compact ../work/scorecard_compact.csv --finance ../work/finance
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
from pathlib import Path

import v2_common as v2
import fetch_live_data as fld
from analyze_confirmatory import MIN_YEARS, ROLL, csd_indicators
from score_v2_test import cmd_prefetch
from score_v3_test import OUTCOMES_PATH, SCORES_DIR, V3_DIR, done, institutions
from v2_training_outcomes import committed

OUT_PATH = V3_DIR / "comparator flags.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", required=True)
    ap.add_argument("--finance", required=True)
    a = ap.parse_args()
    if OUTCOMES_PATH.exists():
        raise SystemExit("A v3 test outcome file exists; the comparator must be committed before any test outcome.")
    insts = institutions()
    missing = [i["unitid"] for i in insts if i["unitid"] not in done()]
    if missing:
        raise SystemExit(f"{len(missing)} v3 test institutions have no committed result yet; the comparator waits.")
    scores_commit = committed(SCORES_DIR)
    cmd_prefetch(a.finance)
    fld.use_bulk_scorecard(a.compact)

    results = {}
    for p in sorted(SCORES_DIR.glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            results[r["unitid"]] = r
    win = v2.WINDOWS["test"]
    cal_years = list(range(win["start_year"], win["end_year"]))
    window = [f"{y}-{str(y + 1)[2:]}" for y in cal_years]
    fiscal = [y + 1 for y in cal_years]

    records = []
    for inst in insts:
        r = results[inst["unitid"]]
        if r["status"] != "scored":
            continue
        u, form = r["unitid"], r["finance form sector"]
        E, _, _, Wt, mask, _ = fld.parse_live_finance(u, window, Path(a.finance) / form, sector=form)
        yrs, margin = [], []
        for fy, ok, rev, exp in zip(fiscal, mask, E, Wt):
            if ok and not math.isnan(rev) and not math.isnan(exp) and exp != 0:
                yrs.append(fy)
                margin.append(float((rev - exp) / exp))
        records.append({"slot": r["slot"], "unitid": u, "name": r["name"], "finance form": form,
                        "operating margin": {"fiscal years": yrs, "values": margin, **csd_indicators(yrs, margin)}})
        om = records[-1]["operating margin"]
        print(f"{u} {r['name'][:40]:40s} years={om['years used']:2d} flag={om.get('flag', 'not computable')}")

    out = {
        "protocol": "sampling protocol v3.md, phase 4 (comparator; committed before any test outcome)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "rule": f"operating margin FY2009-FY2019, linear detrending, sliding {ROLL}-year window, Kendall's tau "
                f"for variance and lag-1 autocorrelation, flagged when both are positive; not computable with "
                f"fewer than {MIN_YEARS} of 11 years (analyze_confirmatory.csd_indicators, unchanged)",
        "test scores (commit, time)": scores_commit,
        "scored institutions": len(records),
        "comparator computable": sum(1 for x in records if x["operating margin"]["computable"]),
        "comparator flagged": sum(1 for x in records if x["operating margin"].get("flag")),
        "institutions": records,
        "machine": v2.machine(),
    }
    v2.write_json(OUT_PATH, out)
    print(f"\nComparator: computable for {out['comparator computable']} of {len(records)}; "
          f"flagged {out['comparator flagged']}.")


if __name__ == "__main__":
    main()
