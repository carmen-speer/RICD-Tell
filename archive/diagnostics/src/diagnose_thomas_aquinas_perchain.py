"""
Per-chain diagnostic for Thomas Aquinas College (UNITID 124292) -- the
direct-observation follow-up to the high-precision convergence check
(diagnose_thomas_aquinas_highprecision.py), which came back with 0
divergences but a badly-failing max rhat (1.1062, PyMC's own threshold
is 1.01) plus a degenerate-chain warning. That's circumstantial
evidence for chains landing in genuinely different places and getting
averaged together into one misleading number -- this makes it directly
visible instead of inferred.

Requires score_institution.py's compute_features_for_institution to
already have the debug_per_chain parameter (2026-09-23) -- commit that
file first, or this will fail with a TypeError.

Same settings as the high-precision check (4 chains, 800 tune/800
draws, target_accept=0.95, cores=1), but only 2 independent calls, not
3 -- the point here isn't another replicate count, it's looking inside
each run's own 4 chains to see whether they split into two groups.
"""

from __future__ import annotations
from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
SECTOR = "private"
START_YEAR = 2013
N_RUNS = 2

SETTINGS = dict(
    n_draws=800, n_tune=800, n_chains=4, target_accept=0.95, cores=1,
    debug_per_chain=True,
)


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print(f"PER-CHAIN DIAGNOSTIC: {N_RUNS} independent calls at {SETTINGS}")
    print("=" * 70)
    print("Looking for whether individual chains split into two groups "
          "(some landing near frac_high_entropy=0.0, some near 1.0) rather "
          "than all four chains genuinely agreeing.")

    for i in range(1, N_RUNS + 1):
        print(f"--- Run {i}/{N_RUNS} ---")
        features = compute_features_for_institution(
            UNITID, NAME, sector=SECTOR, start_year=START_YEAR, **SETTINGS,
        )
        if features is None:
            print("INSUFFICIENT DATA -- unexpected at this stage; stopping.")
            return
        result = clf.classify(features)
        print(f"CROSS-CHAIN MEAN RESULT: frac_high_entropy = {features.frac_high_entropy:.4f}, "
              f"classification = {'high_risk' if result.prediction == 1 else 'stable'} "
              f"({result.probability:.4%} probability high_risk)")

    print("=" * 70)
    print("Compare each run's 'chain N:' lines above against its own "
          "CROSS-CHAIN MEAN RESULT line. If the chains within a run show "
          "different frac_high_entropy values from each other, that's direct "
          "confirmation of a split, not just an inference from rhat.")


if __name__ == "__main__":
    main()
