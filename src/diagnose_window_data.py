"""
Diagnostic, panel only, run before the confirmatory protocol is amended.
It answers two questions about the data available for an FY2019 scoring
window, and fits no model.

1. WHY DID EVERY PANEL CLOSURE FAIL THE DATA CHECK? The panel
   convergence run (check_panel_convergence.py, 2026-11-12) found all
   20 closures that were not fitted came back "insufficient data" in
   the FY2019 window, although every one of them is in HD2019 and
   several closed well after 2019. The live pipeline takes enrollment,
   completion and tuition from the College Scorecard API
   (fetch_live_data.build_live_series), and fetch_scorecard_fields
   raises "No College Scorecard record found" when the API has no
   record, which build_live_series turns into a data failure. The
   hypothesis is that the College Scorecard no longer returns closed
   institutions. This script asks the API for every panel institution
   and records whether a record comes back at all and, if it does,
   which years have the fields the pipeline requires.

2. HOW FAR BACK CAN THE WINDOW GO? Every panel institution measured at
   the six-year FY2019 window (FY2014-FY2019) was flagged high_risk,
   which points to the window being shorter than the series the
   classifier was trained on. A longer window ending in FY2019 needs
   both College Scorecard years and IPEDS finance files reaching
   further back. This script records each institution's earliest year
   in an unbroken run of complete Scorecard years ending in 2018 (the
   pipeline's year label for FY2019), and checks which IPEDS finance
   bulk files (F2 private, F1A public, F3 for-profit) can be downloaded
   for 2004-2012.

It looks up no outcome beyond the panel's own recorded outcomes, touches
no confirmatory institution, and writes only to reports/window_data/.

Usage (GitHub Actions only; needs COLLEGE_SCORECARD_API_KEY):
    cd src
    python diagnose_window_data.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import fetch_live_data as fld
from classifier import load_panel
from check_panel_convergence import hd2019_sectors

PANEL_PATH = "../data/panel/panel.json"
OUT_DIR = Path("../reports/window_data")
YEARS = list(range(2004, 2024))
LAST_YEAR = 2018  # pipeline year label for FY2019 (finance file F1819)
FINANCE_YEARS = list(range(2004, 2013))


def scorecard_coverage(unitid: str, sector: str) -> dict:
    fields = []
    for y in YEARS:
        fields += [f"{y}.student.size", f"{y}.completion.completion_rate_4yr_150nt",
                   f"{y}.cost.tuition.in_state", f"{y}.admissions.admission_rate.overall"]
    try:
        res = fld.fetch_scorecard_fields(unitid, fields)
    except ValueError as e:  # fetch_scorecard_fields: the API returned no record
        return {"record found": False, "error": str(e)}
    except Exception as e:  # anything else (HTTP or network) is not evidence either way
        return {"record found": None, "error": f"{type(e).__name__}: {e}"}

    complete = {}
    for y in YEARS:
        need = [f"{y}.student.size", f"{y}.completion.completion_rate_4yr_150nt", f"{y}.cost.tuition.in_state"]
        if sector != "forprofit":
            need.append(f"{y}.admissions.admission_rate.overall")
        complete[y] = all(res.get(k) is not None for k in need)

    earliest = None
    y = LAST_YEAR
    while y in complete and complete[y]:
        earliest = y
        y -= 1
    return {"record found": True,
            "complete years": [y for y in YEARS if complete[y]],
            "earliest year of unbroken run ending 2018": earliest}


def finance_file_availability() -> dict:
    out = {}
    tmp = Path("/tmp/window_data_finance")
    for sector in ("private", "public", "forprofit"):
        out[sector] = {}
        for y in FINANCE_YEARS:
            got = fld.download_ipeds_finance_bulk(y, dest_dir=tmp / sector, sector=sector)
            out[sector][y] = got is not None
        shutil.rmtree(tmp / sector, ignore_errors=True)
    return out


def main():
    panel = load_panel(PANEL_PATH)
    sectors = hd2019_sectors()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for inst in panel:
        sector = sectors.get(inst.unitid)
        row = {"unitid": inst.unitid, "name": inst.name, "panel_outcome": inst.outcome,
               "sector (HD2019)": sector}
        row.update(scorecard_coverage(inst.unitid, sector or "private"))
        rows.append(row)
        print(f"{inst.name}: {row.get('record found')} {row.get('earliest year of unbroken run ending 2018')}", flush=True)

    finance = finance_file_availability()
    (OUT_DIR / "window_data.json").write_text(json.dumps({"institutions": rows, "finance files": finance}, indent=2))

    rows.sort(key=lambda r: (r["panel_outcome"] != 1, r["name"]))
    print("\nCOLLEGE SCORECARD COVERAGE FOR THE PANEL")
    print("=" * 96)
    print(f"{'Institution':34s} {'outcome':>7s} {'sector':>9s} {'record?':>8s} {'run from':>9s}  complete years")
    for r in rows:
        outcome = {1: "closed", 0: "stable"}.get(r["panel_outcome"], "?")
        found = {True: "yes", False: "NO", None: "ERROR"}[r.get("record found")]
        start = r.get("earliest year of unbroken run ending 2018")
        yrs = r.get("complete years")
        span = f"{yrs[0]}-{yrs[-1]} ({len(yrs)} yrs)" if yrs else ("-" if r.get("record found") else r.get("error", "")[:60])
        print(f"{r['name'][:34]:34s} {outcome:>7s} {str(r['sector (HD2019)']):>9s} {found:>8s} "
              f"{str(start) if start else '-':>9s}  {span}")
    print("=" * 96)
    for label, outc in (("closed", 1), ("stable", 0)):
        sub = [r for r in rows if r["panel_outcome"] == outc]
        print(f"Panel {label}: {sum(1 for r in sub if r.get('record found') is True)} / {len(sub)} have a College Scorecard record"
              f" ({sum(1 for r in sub if r.get('record found') is None)} could not be checked because of an error)")
    starts = [r["earliest year of unbroken run ending 2018"] for r in rows if r.get("earliest year of unbroken run ending 2018")]
    for s in (2008, 2009, 2010, 2011, 2012, 2013):
        print(f"  Unbroken run ending 2018 reaches back to {s} or earlier: {sum(1 for x in starts if x <= s)} institutions")

    print("\nIPEDS FINANCE BULK FILES DOWNLOADABLE (pipeline year label; 2008 = F0809)")
    for sector, years in finance.items():
        print(f"  {sector:9s}: " + "  ".join(f"{y}:{'yes' if ok else 'NO'}" for y, ok in years.items()))
    print(f"\nWrote {OUT_DIR / 'window_data.json'}")


if __name__ == "__main__":
    main()
