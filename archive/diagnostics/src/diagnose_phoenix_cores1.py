"""
Cores=1 replication check for University of Phoenix-Arizona (UNITID
484613) -- see diagnose_clemson_wvu_cores1.py's module docstring for
the full rationale; this is the same check for the third institution
already confirmed only at cores=2.

Requires score_institution.py's compute_features_for_institution to
already have the cores parameter (2026-09-23) -- commit that file
first, or this will fail with a TypeError.
"""

from __future__ import annotations
from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

UNITID = "484613"
NAME = "University of Phoenix-Arizona"
SECTOR = "forprofit"
START_YEAR = 2014
N_REPLICATES = 5


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print(f"CORES=1 REPLICATION CHECK: {N_REPLICATES} independent calls, "
          f"production settings (300 draws/300 tune/2 chains/target_accept=0.9), cores=1")
    print("=" * 70)

    entropy_vals, prob_vals = [], []
    for i in range(1, N_REPLICATES + 1):
        print(f"--- Replicate {i}/{N_REPLICATES} ---")
        features = compute_features_for_institution(
            UNITID, NAME, sector=SECTOR, start_year=START_YEAR, cores=1,
        )
        if features is None:
            print("INSUFFICIENT DATA -- unexpected at this stage; stopping.")
            return
        result = clf.classify(features)
        entropy_vals.append(features.frac_high_entropy)
        prob_vals.append(result.probability)
        print(f"frac_high_entropy = {features.frac_high_entropy:.4f}")
        print(f"classification = {'high_risk' if result.prediction == 1 else 'stable'} "
              f"({result.probability:.4%} probability high_risk)")

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"frac_high_entropy across {N_REPLICATES} replicates: {entropy_vals}")
    print(f"probability across {N_REPLICATES} replicates: {[f'{p:.4f}' for p in prob_vals]}")
    spread = max(entropy_vals) - min(entropy_vals)
    print(f"frac_high_entropy spread: {spread:.4f}")


if __name__ == "__main__":
    main()
