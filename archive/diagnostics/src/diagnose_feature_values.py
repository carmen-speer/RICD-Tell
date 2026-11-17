"""
Real diagnostic: prints the actual, full 8-feature vector the live
pipeline computes for a given institution, run through the exact same
compute_features_for_institution() used by score_institution.py and
score_batch.py -- not a re-derivation, the real function itself -- so
a "why did this institution come back high_risk" question can be
answered by looking at real numbers instead of guessing.

Built 2026-09-15 specifically to investigate University of Houston
(225511): real news (an S&P upgrade to AA+, a $287M FY2025 operating
surplus, $3.3B in reserves) directly contradicts the live pipeline's
87.3% high_risk call for it, and this script exists to find out
whether that's a genuine model weakness or a fixable pipeline issue --
not to assume either answer in advance.

Extended 2026-09-15, same day, to the second neutral-rule batch --
University of Central Florida (132903), Florida State University
(134097), University at Buffalo (196088) -- after all three also came
back high_risk on the live dashboard. Real bond-ratings check (Florida
Board of Governors filing, 2/27/26) found UCF at Moody's Aa2/Fitch AA
stable and FSU at Moody's Aa1/Fitch AA+ stable, neither with a negative
outlook -- the same shape of real-world contradiction as Houston, not
assumed to have the same cause. Buffalo is a real, different case:
current reporting (UB's own statement, Rep. Kennedy's office) documents
about $47M in real federal research-funding cuts this year -- genuine
strain, but not the debt/reserve/enrollment mechanism this model is
built to detect, so its 80.7% call needs this same feature-level check
before being read as either confirmed or an artifact.

Prints each institution's real feature vector alongside the ALREADY-
VALIDATED feature vectors of five public flagships already in the
54-institution panel (Michigan, UVA, UNC-Chapel Hill, Florida,
Wisconsin -- all real, all outcome=stable, pulled directly from
data/panel/panel.json, not estimated), so the live numbers can be
compared against real, already-proven-correct reference points rather
than judged in a vacuum.

Does NOT call save_live_score() -- this never touches
docs/data/live_scores.json or the public dashboard. Diagnostic only.

Usage:
    python diagnose_feature_values.py
    python diagnose_feature_values.py --only 225511

Requires COLLEGE_SCORECARD_API_KEY set in the environment (same as
score_institution.py / score_batch.py).
"""

from __future__ import annotations

import argparse
import traceback

from score_institution import compute_features_for_institution

# The six institutions in question, plus their real sector and the
# real start_year already in use for them in score_batch.py -- kept
# identical here so this diagnostic reflects exactly what the batch
# run actually does, not a different configuration.
TARGETS = [
    ("225511", "University of Houston", "public", 2013),
    ("110583", "California State University-Long Beach", "public", 2013),
    ("217882", "Clemson University", "public", 2013),
    ("132903", "University of Central Florida", "public", 2013),
    ("134097", "Florida State University", "public", 2013),
    ("196088", "University at Buffalo", "public", 2013),
]

# Real, already-validated feature vectors for five public flagships
# already in the 54-institution panel (data/panel/panel.json),
# transcribed directly from that file, not estimated -- every one of
# these classified correctly as stable in leave-one-out testing. Used
# purely as a real point of comparison for the live numbers above,
# since these are the closest real analogues to the six institutions
# above already in the validated panel (all research-ratio UNKNOWN via
# the same public-sector gap discussed below, all large public research
# universities).
PANEL_PUBLIC_REFERENCE = [
    {"name": "Michigan", "outcome": "stable", "d_A_trend": -0.066, "d_A_final": None,
     "delta_R_final": 1.214, "frac_high_entropy": 0.000, "debt_spike": 0.057,
     "delta_R_trend": None, "reserve_adequacy": 13.157, "research_ratio": 0.0000},
    {"name": "UVA", "outcome": "stable", "d_A_trend": -0.034, "d_A_final": None,
     "delta_R_final": 0.379, "frac_high_entropy": 0.000, "debt_spike": 0.102,
     "delta_R_trend": None, "reserve_adequacy": 13.315, "research_ratio": 0.0000},
    {"name": "UNC-Chapel Hill", "outcome": "stable", "d_A_trend": -0.101, "d_A_final": None,
     "delta_R_final": 0.810, "frac_high_entropy": 0.000, "debt_spike": 0.322,
     "delta_R_trend": None, "reserve_adequacy": 12.466, "research_ratio": 0.0000},
    {"name": "Florida", "outcome": "stable", "d_A_trend": -0.115, "d_A_final": None,
     "delta_R_final": 0.855, "frac_high_entropy": 0.000, "debt_spike": 0.104,
     "delta_R_trend": None, "reserve_adequacy": 11.138, "research_ratio": 0.0000},
    {"name": "Wisconsin", "outcome": "stable", "d_A_trend": -0.122, "d_A_final": None,
     "delta_R_final": 0.603, "frac_high_entropy": 0.000, "debt_spike": 0.066,
     "delta_R_trend": None, "reserve_adequacy": 11.989, "research_ratio": 0.0000},
]

# Real note on research_ratio: PUBLIC_FINANCE_FIELDS in fetch_live_data.py
# has no "research" key at all (only PRIVATE_FINANCE_FIELDS does), and
# score_institution.py's own research_val/instruction_val extraction is
# gated to `if sector == "private"`. This is NOT unique to the live
# pipeline -- every public institution already in the validated panel
# (Michigan, UVA, UNC, Florida, Wisconsin, all printed above) also has
# research_ratio pinned at exactly 0.0000. So this diagnostic does not
# treat research_ratio as a live-only bug or a likely cause of any of
# these misclassification questions -- it's a real, pre-existing
# convention the classifier was validated under, not a new gap.


def fmt(v):
    return f"{v:.4f}" if isinstance(v, (int, float)) else "  n/a "


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Score just this one UNITID from TARGETS")
    args = parser.parse_args()

    targets = TARGETS
    if args.only:
        targets = [t for t in TARGETS if t[0] == args.only]
        if not targets:
            raise SystemExit(f"UNITID {args.only} is not in TARGETS -- edit this script to add it.")

    print("=" * 100)
    print("REFERENCE: real, validated public-flagship feature vectors already in the panel")
    print("=" * 100)
    for ref in PANEL_PUBLIC_REFERENCE:
        print(f"{ref['name']:20s} outcome={ref['outcome']:7s} "
              f"d_A_trend={fmt(ref['d_A_trend'])} delta_R_final={fmt(ref['delta_R_final'])} "
              f"frac_high_entropy={fmt(ref['frac_high_entropy'])} debt_spike={fmt(ref['debt_spike'])} "
              f"reserve_adequacy={fmt(ref['reserve_adequacy'])} research_ratio={fmt(ref['research_ratio'])}")

    print()
    print("=" * 100)
    print("LIVE: real feature vectors computed just now via the actual live pipeline")
    print("=" * 100)
    for unitid, name, sector, start_year in targets:
        print(f"\n{'-' * 100}\nComputing real live features for {name} ({unitid}, {sector})\n{'-' * 100}")
        try:
            features = compute_features_for_institution(unitid, name, sector=sector, start_year=start_year)
            if features is None:
                print(f"RESULT: insufficient_data for {name} ({unitid}) -- see the real reason printed above.")
                continue
            print(f"\nREAL FEATURE VECTOR for {name} ({unitid}):")
            print(f"  d_A_trend         = {features.d_A_trend:.4f}")
            print(f"  d_A_final         = {features.d_A_final:.4f}")
            print(f"  delta_R_final     = {features.delta_R_final:.4f}")
            print(f"  frac_high_entropy = {features.frac_high_entropy:.4f}")
            print(f"  debt_spike        = {features.debt_spike:.4f}")
            print(f"  delta_R_trend     = {features.delta_R_trend:.4f}")
            print(f"  reserve_adequacy  = {features.reserve_adequacy:.4f}")
            print(f"  research_ratio    = {features.research_ratio:.4f}")
            print(f"\nFor comparison, real panel public flagships have reserve_adequacy "
                  f"in {min(r['reserve_adequacy'] for r in PANEL_PUBLIC_REFERENCE):.2f}-"
                  f"{max(r['reserve_adequacy'] for r in PANEL_PUBLIC_REFERENCE):.2f} and "
                  f"frac_high_entropy = 0.0000, all classified stable.")
        except Exception as e:
            # A real, honest per-institution failure -- print the full
            # traceback (unlike score_batch.py's one-line summary) since
            # this script exists specifically to diagnose problems, not
            # to keep a batch run moving.
            print(f"REAL ERROR computing features for {name} ({unitid}): {type(e).__name__}: {e}")
            traceback.print_exc()

    print(f"\n{'=' * 100}\nDIAGNOSTIC DONE\n{'=' * 100}")


if __name__ == "__main__":
    main()
