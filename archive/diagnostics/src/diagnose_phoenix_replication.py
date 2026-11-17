"""
Reproducibility replication check for University of Phoenix-Arizona
(484613) -- the same check diagnose_thomas_aquinas_replication.py ran
for Thomas Aquinas College, applied here because Phoenix is the only
other institution in the entire live batch whose production-settings
sampling log shows a real MCMC divergence count (20 divergences,
2026-09-22 batch run) -- the same symptom (divergences present) that
tracked exactly with Thomas Aquinas College's instability (153
divergences in every run that landed on frac_high_entropy=1.0000,
zero divergences in the one run that landed on 0.0000). Every other
institution in the batch showed no divergence warnings at all.

Phoenix's live score is already effectively at the ceiling (99.996%
probability high_risk), so even real instability here is less likely
to change its classification -- but the README and dashboard
currently state a specific number ("effectively 100% (99.997%)"), and
if that number isn't actually reproducible, it should say so rather
than imply a false precision.
"""

from __future__ import annotations

from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

UNITID = "484613"
NAME = "University of Phoenix-Arizona"
SECTOR = "forprofit"
START_YEAR = 2014
N_REPLICATES = 5
PRODUCTION_SETTINGS = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9)


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print(f"REPLICATION CHECK: {N_REPLICATES} independent calls at IDENTICAL "
          f"nominal settings {PRODUCTION_SETTINGS}")
    print("=" * 70)

    replicate_results = []
    for i in range(1, N_REPLICATES + 1):
        print(f"\n--- Replicate {i}/{N_REPLICATES} ---")
        features = compute_features_for_institution(
            UNITID, NAME, sector=SECTOR, start_year=START_YEAR, **PRODUCTION_SETTINGS)
        if features is None:
            print(f"REAL FAILURE on replicate {i}: no features returned. Recording as a gap.")
            replicate_results.append(None)
            continue
        result = clf.classify(features)
        print(f"frac_high_entropy = {features.frac_high_entropy:.4f}")
        print(f"debt_spike        = {features.debt_spike:.6f}")
        print(f"classification    = {'high_risk' if result.prediction == 1 else 'stable'} "
              f"({result.probability:.6%} probability high_risk)")
        replicate_results.append((features.frac_high_entropy, features.debt_spike, result.probability))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    valid = [r for r in replicate_results if r is not None]
    if len(valid) < 2:
        print("Fewer than 2 valid replicates -- cannot assess reproducibility.")
        return

    entropies = [r[0] for r in valid]
    probs = [r[2] for r in valid]
    entropy_spread = max(entropies) - min(entropies)
    prob_spread = max(probs) - min(probs)
    print(f"frac_high_entropy across {len(valid)} replicates: {entropies}")
    print(f"probability across {len(valid)} replicates:       {[f'{p:.6f}' for p in probs]}")
    print(f"frac_high_entropy spread: {entropy_spread:.4f}")
    print(f"probability spread:       {prob_spread:.6f}")

    if entropy_spread == 0.0:
        print("\nPhoenix reproduced cleanly across all replicates -- its existing "
              "live score is confirmed, not just assumed.")
    else:
        print("\nREAL INSTABILITY FOUND for Phoenix -- its exact reported "
              "probability should be caveated the same way this diagnostic is "
              "prompting for Thomas Aquinas College, even though its "
              "classification (high_risk) is unlikely to change given how far "
              "from the decision boundary it sits.")


if __name__ == "__main__":
    main()
