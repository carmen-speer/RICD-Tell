"""
Cores=1 replication check for Clemson University (UNITID 217882) and
West Virginia University (UNITID 238032) -- confirming their existing
"resolved/stable" live scores hold up under cores=1 (sequential,
single-process), the setting production is switching to (2026-09-23)
after the Thomas Aquinas College investigation found cores=2 (real
multiprocessing) can give a whole batch of otherwise-identical runs a
different answer from another whole batch, while cores=1 has given the
same answer seven times in a row, including direct chain-to-chain
agreement within each run.

Clemson and West Virginia were already confirmed reproducible via 5x
replication at production settings -- but that replication ran at
cores=2, the same setting now known to be capable of flipping between
whole batches. This re-checks both at cores=1 specifically, before the
README and dashboard are updated with numbers that assume the
production default has changed.

Requires score_institution.py's compute_features_for_institution to
already have the cores parameter (2026-09-23) -- commit that file
first, or this will fail with a TypeError.
"""

from __future__ import annotations
from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

N_REPLICATES = 5

INSTITUTIONS = [
    dict(unitid="217882", name="Clemson University", sector="public", start_year=2013),
    dict(unitid="238032", name="West Virginia University", sector="public", start_year=2013),
]


def replicate_one(clf, unitid, name, sector, start_year):
    entropy_vals, prob_vals = [], []
    for i in range(1, N_REPLICATES + 1):
        print(f"--- {name}: replicate {i}/{N_REPLICATES} ---")
        features = compute_features_for_institution(
            unitid, name, sector=sector, start_year=start_year, cores=1,
        )
        if features is None:
            print(f"INSUFFICIENT DATA for {name} -- unexpected; stopping this institution.")
            return None
        result = clf.classify(features)
        entropy_vals.append(features.frac_high_entropy)
        prob_vals.append(result.probability)
        print(f"frac_high_entropy = {features.frac_high_entropy:.4f}")
        print(f"classification = {'high_risk' if result.prediction == 1 else 'stable'} "
              f"({result.probability:.4%} probability high_risk)")
    return entropy_vals, prob_vals


def summarize(name, vals):
    entropy_vals, prob_vals = vals
    print(f"=== {name} SUMMARY (cores=1) ===")
    print(f"frac_high_entropy across {N_REPLICATES} replicates: {entropy_vals}")
    print(f"probability across {N_REPLICATES} replicates: {[f'{p:.4f}' for p in prob_vals]}")
    spread = max(entropy_vals) - min(entropy_vals)
    print(f"frac_high_entropy spread: {spread:.4f}")


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print(f"CORES=1 REPLICATION CHECK: {N_REPLICATES} independent calls each, "
          f"production settings (300 draws/300 tune/2 chains/target_accept=0.9), cores=1")
    print("=" * 70)

    for inst in INSTITUTIONS:
        vals = replicate_one(clf, **inst)
        if vals is not None:
            summarize(inst["name"], vals)


if __name__ == "__main__":
    main()
