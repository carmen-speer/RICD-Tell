"""
Two-step diagnostic for Thomas Aquinas College (124292), the one
institution among the third-expansion liberal-arts batch (2026-09-22)
that didn't resolve as a clean stable result or a clean, corroborated
high_risk one. Follows the same pattern diagnose_clemson_wvu.py used
to resolve Clemson and narrow West Virginia: a convergence recheck
first, ruling out MCMC non-convergence as a confound, then a
feature-space peer-density comparison against the full validated
panel.

Why this one specifically needs it, and Wittenberg University (also
high_risk in the same batch) doesn't: Wittenberg's 95.3% is real
distress, independently confirmed by real reporting -- the Higher
Learning Commission placed it on accreditation probation on
2025-11-06, citing a $10.8M projected cash-flow shortfall in its 2026
budget and a line of credit at risk of exhaustion by March 2026.
Nothing to diagnose there.

Thomas Aquinas College's 95.5% has no such corroboration. Real
reporting shows the opposite of a distress narrative: record combined
enrollment (566 students, Fall 2024) across its two campuses, with
its second campus (New England, opened 2019) having nearly
quadrupled its own enrollment since launch. Its production-settings
sampling run (2026-09-22) also threw 153 divergences -- an order of
magnitude worse than any other institution in the same batch (the
next-worst had 20). That divergence count alone is real cause to
check convergence before treating 95.5% as a trustworthy result.

One real, plausible, UNCONFIRMED hypothesis worth stating rather than
leaving unstated: an actively growing second campus plausibly means
real, large, growth-driven capital borrowing showing up in the same
liabilities/debt_spike channel that flags actual distress elsewhere
-- the same shape of problem as the sign-blindness failure mode
already documented in the README's Known Gaps (a large swing reads
as alarming regardless of whether it's growth or decline), except
here in the debt/liability channel rather than frac_high_entropy
specifically, and not yet checked against real data the way that fix
was. This script's Step 3 prints the real debt_spike value so that
hypothesis can be judged against an actual number instead of asserted
-- it does not resolve the question on its own.
"""

from __future__ import annotations

from classifier import RICDClassifier, InstitutionFeatures, load_panel, FEATURE_NAMES
from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
SECTOR = "private"
START_YEAR = 2013

PRODUCTION_SETTINGS = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9)
HIGH_PRECISION_SETTINGS = dict(n_draws=1000, n_tune=1000, n_chains=4, target_accept=0.95)


def print_feature_vector(label: str, features: InstitutionFeatures) -> None:
    print(f"\n{label}:")
    for fname in FEATURE_NAMES:
        print(f"  {fname:20s} = {getattr(features, fname):.4f}")


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print("STEP 1: Convergence recheck -- production vs. 4x sampling precision")
    print("=" * 70)
    print(f"Production settings: {PRODUCTION_SETTINGS}")
    features_production = compute_features_for_institution(
        UNITID, NAME, sector=SECTOR, start_year=START_YEAR, **PRODUCTION_SETTINGS)
    if features_production is None:
        print("REAL FAILURE: production-settings run returned no features. Stopping -- "
              "nothing to diagnose if the pipeline itself can't produce a result.")
        return
    print_feature_vector("Production-settings feature vector", features_production)
    result_production = clf.classify(features_production)
    print(f"Production-settings classification: {result_production.prediction} "
          f"(probability={result_production.probability:.4f})")

    print(f"\nHigh-precision settings: {HIGH_PRECISION_SETTINGS}")
    features_highprec = compute_features_for_institution(
        UNITID, NAME, sector=SECTOR, start_year=START_YEAR, **HIGH_PRECISION_SETTINGS)
    if features_highprec is None:
        print("REAL FAILURE: high-precision run returned no features. Stopping.")
        return
    print_feature_vector("High-precision feature vector", features_highprec)
    result_highprec = clf.classify(features_highprec)
    print(f"High-precision classification: {result_highprec.prediction} "
          f"(probability={result_highprec.probability:.4f})")

    entropy_delta = abs(features_production.frac_high_entropy - features_highprec.frac_high_entropy)
    print(f"\nfrac_high_entropy: production={features_production.frac_high_entropy:.4f}, "
          f"high-precision={features_highprec.frac_high_entropy:.4f}, delta={entropy_delta:.4f}")
    if entropy_delta < 1e-6:
        print("Identical at both settings -- NOT a sampling artifact. The 153 divergences "
              "at production settings did not change this feature's value; proceeding to "
              "Step 2 with the high-precision vector.")
    else:
        print("REAL DIFFERENCE between settings -- this IS at least partly a convergence "
              "artifact. Report both numbers rather than picking one; Step 2 below still "
              "runs on the high-precision vector as the more trustworthy of the two, but "
              "this should be stated plainly, not smoothed over.")

    print("\n" + "=" * 70)
    print("STEP 2: Feature-space peer-density comparison against the validated panel")
    print("=" * 70)
    panel_plus_target = panel + [features_highprec]
    neighbors = clf.peer_density(panel_plus_target, UNITID, n_neighbors=5)
    print(f"\n{NAME}'s 5 nearest real panel neighbors (high-precision feature vector):")
    for name, outcome, dist in neighbors:
        print(f"  {name:35s} {outcome:8s} distance={dist:.3f}")
    closures_among = [n for n in neighbors if n[1] == "closure"]
    print(f"\n{len(closures_among)} of 5 nearest neighbors are real confirmed closures.")

    print("\n" + "=" * 70)
    print("STEP 3 (hypothesis check, not yet a conclusion): growth-driven debt vs. distress-driven debt")
    print("=" * 70)
    print(f"debt_spike (high-precision) = {features_highprec.debt_spike:.6f}")
    print("Thomas Aquinas College opened and has been actively growing a second campus "
          "(New England, opened 2019) -- a real, plausible source of large, growth-driven "
          "capital borrowing that could show up in this same channel without being "
          "distress. This print is not a resolution: a positive, growth-consistent "
          "debt_spike value here is suggestive, not confirmed, and would need the same "
          "kind of real-data-level scrutiny diagnose_feature_values.py already applies to "
          "Houston/UCF/FSU before being treated as an explanation rather than a guess.")

    print("\n" + "=" * 70)
    print("DIAGNOSTIC DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
