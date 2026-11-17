"""
Real diagnostic: for institutions already in the validated 54-panel
(data/panel/panel.json), recomputes their feature vector through the
exact same live pipeline (compute_features_for_institution(), the same
function score_institution.py / score_batch.py use for new
institutions) and diffs it against the institution's frozen panel
record.

Built 2026-09-15 to test a specific, real hypothesis about why the
live-scored neutral batch (Houston, Long Beach, Clemson, UCF, FSU,
Buffalo -- all high_risk) diverges so sharply from the panel's five
stable public-flagship references (Michigan, UVA, UNC, Florida,
Wisconsin -- all frac_high_entropy=0.0000): compute_features_for_institution()
defaults end_year to datetime.date.today().year - 2, so a live run
made today reaches a later data window than whatever "today" was when
panel.json was built. If a panel-validated stable institution comes
back with materially different features when recomputed live -- most
importantly a nonzero frac_high_entropy or a meaningfully lower
reserve_adequacy than its frozen panel value -- that is direct
evidence of a live-vs-training window mismatch (or another live-path
discrepancy), not evidence about the six new institutions' real
financial health. If a panel institution reproduces its frozen values
closely, that rules the window-mismatch theory out and points instead
toward the panel's five public-stable comparators being an unusually
narrow, endowment-wealthy reference class.

Does NOT call save_live_score() -- this never touches
docs/data/live_scores.json or the public dashboard. Diagnostic only.

Usage:
    python diagnose_panel_pipeline_consistency.py
    python diagnose_panel_pipeline_consistency.py --only 170976

Requires COLLEGE_SCORECARD_API_KEY set in the environment (same as
score_institution.py / score_batch.py / diagnose_feature_values.py).
"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

from score_institution import compute_features_for_institution

# The five public-flagship panel members already used as the stable
# reference class in diagnose_feature_values.py -- real UNITIDs,
# pulled directly from data/panel/panel.json, not guessed. Kept to
# start_year=2013 to match the convention every other live-scoring
# script in this repo already uses (score_batch.py, diagnose_feature_values.py).
TARGETS = [
    ("170976", "Michigan", "public", 2013),
    ("234076", "UVA", "public", 2013),
    ("199120", "UNC-Chapel Hill", "public", 2013),
    ("134130", "Florida", "public", 2013),
    ("240444", "Wisconsin", "public", 2013),
]

PANEL_PATH = Path(__file__).resolve().parent.parent / "data" / "panel" / "panel.json"

FEATURE_FIELDS = [
    "d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy",
    "debt_spike", "delta_R_trend", "reserve_adequacy", "research_ratio",
]


def fmt(v):
    return f"{v:.4f}" if isinstance(v, (int, float)) else "  n/a "


def load_panel_record(unitid: str) -> dict | None:
    with open(PANEL_PATH) as f:
        panel = json.load(f)
    for rec in panel:
        if rec["unitid"] == unitid:
            return rec
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Score just this one UNITID from TARGETS")
    args = parser.parse_args()

    targets = TARGETS
    if args.only:
        targets = [t for t in TARGETS if t[0] == args.only]
        if not targets:
            raise SystemExit(f"UNITID {args.only} is not in TARGETS -- edit this script to add it.")

    for unitid, name, sector, start_year in targets:
        print(f"\n{'=' * 100}\n{name} ({unitid}) -- panel record vs. live recomputation\n{'=' * 100}")

        panel_rec = load_panel_record(unitid)
        if panel_rec is None:
            print(f"REAL ERROR: {name} ({unitid}) not found in {PANEL_PATH} -- check the UNITID.")
            continue

        print(f"\nFROZEN PANEL RECORD (as used to train/validate the classifier):")
        for field in FEATURE_FIELDS:
            print(f"  {field:20s} = {fmt(panel_rec.get(field))}")
        print(f"  outcome              = {'stable' if panel_rec.get('outcome') == 0 else 'closure'}")

        print(f"\nLIVE RECOMPUTATION (same compute_features_for_institution(), run just now):")
        try:
            live = compute_features_for_institution(unitid, name, sector=sector, start_year=start_year)
            if live is None:
                print(f"  RESULT: insufficient_data live for {name} ({unitid}) -- see the real reason printed above.")
                continue
            live_vec = {
                "d_A_trend": live.d_A_trend, "d_A_final": live.d_A_final,
                "delta_R_final": live.delta_R_final, "frac_high_entropy": live.frac_high_entropy,
                "debt_spike": live.debt_spike, "delta_R_trend": live.delta_R_trend,
                "reserve_adequacy": live.reserve_adequacy, "research_ratio": live.research_ratio,
            }
            for field in FEATURE_FIELDS:
                print(f"  {field:20s} = {fmt(live_vec.get(field))}")

            print(f"\nDELTA (live minus panel -- large deltas on frac_high_entropy or "
                  f"reserve_adequacy specifically are what would confirm a live-vs-training "
                  f"window mismatch):")
            for field in FEATURE_FIELDS:
                p = panel_rec.get(field)
                l = live_vec.get(field)
                if isinstance(p, (int, float)) and isinstance(l, (int, float)):
                    print(f"  {field:20s} delta = {l - p:+.4f}")
        except Exception as e:
            print(f"REAL ERROR computing live features for {name} ({unitid}): {type(e).__name__}: {e}")
            traceback.print_exc()

    print(f"\n{'=' * 100}\nDIAGNOSTIC DONE\n{'=' * 100}")


if __name__ == "__main__":
    main()
