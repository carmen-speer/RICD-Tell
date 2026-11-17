"""
Reproducibility replication check for Clemson University (217882) and
West Virginia University (238032) -- the same check
diagnose_thomas_aquinas_replication.py ran, applied here because it
needs to be, not because either institution is suspected of the same
problem.

Why this is needed even though neither showed the symptom that
explained Thomas Aquinas College's instability: both institutions'
"resolved" status in the README and dashboard rests on
diagnose_clemson_wvu.py's Step 1, which compared production settings
against high-precision settings WITHIN one script execution and found
them to agree -- exactly the kind of check that turned out NOT to
prove real reproducibility for Thomas Aquinas College, whose one
anomalous run was internally self-consistent (matching itself at both
settings) while still being the outlier against six other independent
runs. Neither diagnose_clemson_wvu.py's Clemson nor West Virginia
sections showed any MCMC divergence warnings (the specific symptom
that tracked exactly with Thomas Aquinas College's instability), which
is real evidence AGAINST the same failure mode applying here -- but it
is not the same as having actually tested it, and this check is cheap
enough (~7-20 seconds per replicate at production settings) that there
is no real reason to leave it untested.

Reading the result: if both institutions reproduce cleanly across all
5 replicates, their existing "resolved" status in the README stands
confirmed, not just assumed. If either one varies, its resolution
needs to be revisited the same way Thomas Aquinas College's did.
"""

from __future__ import annotations

from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

INSTITUTIONS = [
    ("217882", "Clemson University", "public", 2013),
    ("238032", "West Virginia University", "public", 2013),
]
N_REPLICATES = 5
PRODUCTION_SETTINGS = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9)


def replicate_one(unitid, name, sector, start_year, clf):
    print(f"\n{'#' * 70}\n{name} ({unitid})\n{'#' * 70}")
    replicate_results = []
    for i in range(1, N_REPLICATES + 1):
        print(f"\n--- {name}, replicate {i}/{N_REPLICATES} ---")
        features = compute_features_for_institution(
            unitid, name, sector=sector, start_year=start_year, **PRODUCTION_SETTINGS)
        if features is None:
            print(f"REAL FAILURE on replicate {i}: no features returned. Recording as a gap.")
            replicate_results.append(None)
            continue
        result = clf.classify(features)
        print(f"frac_high_entropy = {features.frac_high_entropy:.4f}")
        print(f"debt_spike        = {features.debt_spike:.6f}")
        print(f"classification    = {'high_risk' if result.prediction == 1 else 'stable'} "
              f"({result.probability:.4%} probability high_risk)")
        replicate_results.append((features.frac_high_entropy, features.debt_spike, result.probability))
    return replicate_results


def summarize(name, replicate_results):
    valid = [r for r in replicate_results if r is not None]
    print(f"\n--- {name}: SUMMARY ---")
    if len(valid) < 2:
        print("Fewer than 2 valid replicates -- cannot assess reproducibility.")
        return
    entropies = [r[0] for r in valid]
    probs = [r[2] for r in valid]
    entropy_spread = max(entropies) - min(entropies)
    print(f"frac_high_entropy across {len(valid)} replicates: {entropies}")
    print(f"probability across {len(valid)} replicates:       {[f'{p:.4f}' for p in probs]}")
    print(f"frac_high_entropy spread: {entropy_spread:.4f}")
    if entropy_spread == 0.0:
        print(f"{name} reproduced cleanly across all replicates -- its existing "
              f"'resolved' status is confirmed, not just internally self-consistent.")
    else:
        print(f"REAL INSTABILITY FOUND for {name} -- its existing 'resolved' status "
              f"needs to be revisited, the same way Thomas Aquinas College's did.")


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    all_results = {}
    for unitid, name, sector, start_year in INSTITUTIONS:
        all_results[name] = replicate_one(unitid, name, sector, start_year, clf)

    print("\n" + "=" * 70)
    print("FINAL SUMMARY -- ALL INSTITUTIONS")
    print("=" * 70)
    for name, results in all_results.items():
        summarize(name, results)


if __name__ == "__main__":
    main()
