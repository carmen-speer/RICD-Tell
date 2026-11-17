"""
Executes the "Next step for West Virginia, not yet run" diagnostic
exactly as scoped in README Known Gaps (the paragraph directly
following diagnose_clemson_wvu.py's Step 1/Step 2 results): a
feature-by-feature comparison of West Virginia University's real, live
feature vector against its two closest real panel neighbors already
identified by RICDClassifier.peer_density() in that earlier diagnostic
-- Wisconsin (stable, distance 0.86, its single nearest neighbor) and
Trinity Christian (a real confirmed closure, distance 1.10, its
second-nearest) -- checking each of the other seven features
individually, not just the aggregate distance peer_density() already
reported.

BACKGROUND: after the 2026-09-20 directional-entropy fix,
frac_high_entropy no longer distinguishes West Virginia from either
reference point -- it sits at 0.0000 for West Virginia (confirmed
twice, at both production and high-precision MCMC settings, in
diagnose_clemson_wvu.py's Step 1) AND for both Wisconsin and Trinity
Christian in the real, frozen panel record (data/panel/panel.json). A
feature that reads identically for a real closure and a real survivor
cannot be the thing that tells them apart, so this diagnostic sets it
aside for the individual comparison (though it is still printed, for
completeness) and checks the real remaining seven: d_A_trend,
d_A_final, delta_R_final, delta_R_trend, debt_spike, reserve_adequacy,
and research_ratio.

METHOD: computes West Virginia's real, live 8-feature vector via the
same compute_features_for_institution() used by score_institution.py
and score_batch.py -- not a re-derivation. Wisconsin's and Trinity
Christian's values are transcribed directly from
data/panel/panel.json (their real, checked-in, already-validated panel
records), not estimated. For each of the seven non-entropy features,
prints West Virginia's live value alongside both reference values and
reports which one it sits numerically closer to -- a real,
single-feature comparison, not a standardized multi-feature distance
(peer_density() already did that aggregate comparison across all 54
panel institutions; this is the individual, two-point breakdown the
README's next step actually calls for). Ends with a plain tally: how
many of the seven lean toward Wisconsin (stable) vs. Trinity Christian
(closure).

Uses production MCMC settings (n_draws=300, n_tune=300, n_chains=2,
target_accept=0.9) by default -- the same settings that produced West
Virginia's currently-reported 44.2% live score -- rather than re-running
the high-precision convergence check diagnose_clemson_wvu.py's Step 1
already did for frac_high_entropy specifically. The other four
posterior-derived features here (d_A_trend, d_A_final, delta_R_final,
delta_R_trend) are posterior means, which converge far more readily
than the regime-classification fraction that motivated that earlier
check; debt_spike, reserve_adequacy, and research_ratio are computed
directly from parsed finance data with no MCMC sampling involved at
all. A --high-precision flag is provided in case this diagnostic's
read is disputed on convergence grounds, re-running everything at
diagnose_clemson_wvu.py's 1000/1000/4/0.95 settings instead.

Does NOT call save_live_score() -- this never touches
docs/data/live_scores.json or the public dashboard. Diagnostic only.

Usage:
    python diagnose_west_virginia_feature_comparison.py
    python diagnose_west_virginia_feature_comparison.py --high-precision

Requires COLLEGE_SCORECARD_API_KEY set in the environment (same as
score_institution.py / score_batch.py / diagnose_clemson_wvu.py). Run
via GitHub Actions -- this project's sandboxed development
environments cannot reach NCES/College Scorecard.
"""

from __future__ import annotations

import argparse

from score_institution import compute_features_for_institution

WEST_VIRGINIA = ("238032", "West Virginia University", "public", 2013)

PRODUCTION_SETTINGS = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9)
HIGH_PRECISION_SETTINGS = dict(n_draws=1000, n_tune=1000, n_chains=4, target_accept=0.95)

# Real, already-validated panel records for West Virginia's two nearest
# real neighbors, exactly as found by diagnose_clemson_wvu.py's Step 2
# (RICDClassifier.peer_density()) -- transcribed directly from
# data/panel/panel.json, not estimated.
WISCONSIN = {
    "name": "Wisconsin", "outcome": "stable", "peer_distance": 0.86,
    "d_A_trend": -0.0920367144090028, "d_A_final": 0.37082652383643777,
    "delta_R_final": 0.8006205222690681, "frac_high_entropy": 0.0,
    "debt_spike": 0.10320297976637982, "delta_R_trend": 0.3678168996300879,
    "reserve_adequacy": 11.76470491345181, "research_ratio": 0.0,
}
TRINITY_CHRISTIAN = {
    "name": "Trinity Christian", "outcome": "closure", "peer_distance": 1.10,
    "d_A_trend": -0.1393743368814217, "d_A_final": 0.2868489982037621,
    "delta_R_final": 0.8167097450815108, "frac_high_entropy": 0.0,
    "debt_spike": 0.08315818104834483, "delta_R_trend": 0.3683771017704647,
    "reserve_adequacy": 9.260938194182891, "research_ratio": 0.0,
}

ALL_FIELDS = [
    "d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy",
    "debt_spike", "delta_R_trend", "reserve_adequacy", "research_ratio",
]

# The seven non-entropy features actually compared individually below.
# frac_high_entropy is excluded here (though still printed above, for
# completeness) because it reads 0.0000 for West Virginia AND both
# reference points, so it cannot be the thing that tells a real
# closure from a real survivor in this specific comparison. See module
# docstring.
COMPARISON_FIELDS = [
    "d_A_trend", "d_A_final", "delta_R_final",
    "delta_R_trend", "debt_spike", "reserve_adequacy", "research_ratio",
]


def fmt(v):
    return f"{v:.4f}" if isinstance(v, (int, float)) else "  n/a "


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--high-precision", action="store_true",
                         help="Use diagnose_clemson_wvu.py's 1000/1000/4/0.95 "
                              "settings instead of production 300/300/2/0.9.")
    args = parser.parse_args()
    settings = HIGH_PRECISION_SETTINGS if args.high_precision else PRODUCTION_SETTINGS
    label = "HIGH-PRECISION" if args.high_precision else "PRODUCTION"

    print(f"{'=' * 100}\nComputing West Virginia University's real, live feature vector "
          f"at {label} settings\n(n_draws={settings['n_draws']}, n_tune={settings['n_tune']}, "
          f"n_chains={settings['n_chains']}, target_accept={settings['target_accept']})\n{'=' * 100}")

    unitid, name, sector, start_year = WEST_VIRGINIA
    features = compute_features_for_institution(
        unitid, name, sector=sector, start_year=start_year, **settings)
    if features is None:
        raise SystemExit(
            f"RESULT: insufficient_data for {name} -- see the real reason printed "
            f"above. Cannot run the comparison without a real feature vector.")

    wvu = {
        "d_A_trend": features.d_A_trend, "d_A_final": features.d_A_final,
        "delta_R_final": features.delta_R_final, "frac_high_entropy": features.frac_high_entropy,
        "debt_spike": features.debt_spike, "delta_R_trend": features.delta_R_trend,
        "reserve_adequacy": features.reserve_adequacy, "research_ratio": features.research_ratio,
    }

    print(f"\n{'=' * 100}\nFULL 8-FEATURE VECTOR -- West Virginia (live) vs. Wisconsin "
          f"(stable, panel) vs. Trinity Christian (closure, panel)\n{'=' * 100}")
    print(f"{'feature':20s}{'West Virginia':>18s}{'Wisconsin':>18s}{'Trinity Christian':>20s}")
    for field in ALL_FIELDS:
        print(f"{field:20s}{fmt(wvu[field]):>18s}{fmt(WISCONSIN[field]):>18s}"
              f"{fmt(TRINITY_CHRISTIAN[field]):>20s}")

    print(f"\n{'=' * 100}\nINDIVIDUAL FEATURE COMPARISON -- the other seven, frac_high_entropy "
          f"set aside (0.0000 for West Virginia and both reference points -- see module "
          f"docstring)\n{'=' * 100}")
    wisconsin_count = 0
    trinity_count = 0
    for field in COMPARISON_FIELDS:
        v_wvu = wvu[field]
        v_wis = WISCONSIN[field]
        v_tri = TRINITY_CHRISTIAN[field]
        dist_wis = abs(v_wvu - v_wis)
        dist_tri = abs(v_wvu - v_tri)
        if dist_wis < dist_tri:
            verdict = "closer to Wisconsin (stable)"
            wisconsin_count += 1
        elif dist_tri < dist_wis:
            verdict = "closer to Trinity Christian (closure)"
            trinity_count += 1
        else:
            verdict = "exactly equidistant"
        print(f"\n{field}:")
        print(f"  West Virginia (live)         = {fmt(v_wvu)}")
        print(f"  Wisconsin (stable, panel)     = {fmt(v_wis)}  (distance {dist_wis:.4f})")
        print(f"  Trinity Christian (closure)   = {fmt(v_tri)}  (distance {dist_tri:.4f})")
        print(f"  -> {verdict}")

    print(f"\n{'=' * 100}\nTALLY -- of the seven non-entropy features:\n"
          f"  {wisconsin_count} lean toward Wisconsin (stable)\n"
          f"  {trinity_count} lean toward Trinity Christian (closure)\n{'=' * 100}")
    print(
        "\nREADING THIS RESULT: this is a real, single-feature-at-a-time comparison, "
        "not a standardized multi-feature distance -- it can disagree with "
        "peer_density()'s aggregate verdict (Wisconsin nearest overall) if West "
        "Virginia's values split unevenly across features. A lopsided tally toward "
        "Wisconsin here corroborates peer_density()'s aggregate result rather than "
        "resolving the tie a different way; a lopsided tally toward Trinity Christian "
        "would mean the aggregate distance measure and the individual features are "
        "telling different stories, worth flagging rather than picking whichever "
        "result is preferred. A near-even split (e.g. 4-3 or 3-4) means this "
        "diagnostic itself doesn't break the tie either, and West Virginia's status "
        "stays genuinely mixed rather than resolved."
    )


if __name__ == "__main__":
    main()
