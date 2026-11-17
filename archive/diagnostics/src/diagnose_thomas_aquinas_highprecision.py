"""
High-precision convergence diagnostic for Thomas Aquinas College (UNITID
124292) -- part of the ongoing MCMC-reproducibility investigation
(Sept 2026). Two independent replication rounds at production settings
(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9) produced a
roughly even split between two internally-consistent-but-mutually-
contradictory outcomes (frac_high_entropy=1.0000 / 95.5081% high_risk
vs. 0.0000 / 66.8029% high_risk), and a cores=1 isolation test did not
resolve which one is real -- it just added a third batch that also
happened to land on 0.0000. Every single run so far, regardless of
outcome, has carried PyMC's own convergence warnings (rhat > 1.01,
effective sample size too low, and fewer than the recommended 4
chains), so before treating either regime as "the real answer," this
tests the more basic possibility first: that production settings are
simply under-resolved for this institution's data, not that cores or
multiprocessing is the deciding factor.

Runs the real, live pipeline against Thomas Aquinas College's real data
at:
  n_chains=4      (PyMC's own stated recommendation, vs. production's 2)
  n_tune=800       (vs. production's 300)
  n_draws=800      (vs. production's 300)
  target_accept=0.95  (vs. production's 0.9 -- smaller, more careful
                        steps, the standard first remedy for divergences)
  cores=1          (sequential -- deliberately keeping the one variable
                     from the cores=1 isolation test that gave clean,
                     reproducible results, so this test isolates
                     "does more precision fix it" without reintroducing
                     the cores=1-vs-cores=2 question on top of it)

Requires score_institution.py's compute_features_for_institution to
already have the cores parameter (2026-09-23) and the CONVERGENCE
printout (2026-09-22) -- commit that file first, or this will fail
with a TypeError on the cores= keyword.

3 replicates, not 5: at this much higher draw/tune/chain count, run
sequentially (cores=1), each replicate takes substantially longer than
the ~30-45 seconds production settings took. 3 independent replicates
is still enough to tell a real, converged, stable result (identical
outcome, ~0 divergences, rhat close to 1.0, all three times) apart from
continued instability.
"""

from __future__ import annotations
from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
SECTOR = "private"
START_YEAR = 2013
N_REPLICATES = 3

HIGH_PRECISION_SETTINGS = dict(
    n_draws=800, n_tune=800, n_chains=4, target_accept=0.95, cores=1,
)


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print(f"HIGH-PRECISION CONVERGENCE CHECK: {N_REPLICATES} independent calls at "
          f"{HIGH_PRECISION_SETTINGS}")
    print("=" * 70)
    print("Testing whether production settings (300/300/2 chains) are simply "
          "under-resolved, rather than continuing to compare cores=1 vs cores=2.")

    entropy_vals = []
    debt_vals = []
    prob_vals = []

    for i in range(1, N_REPLICATES + 1):
        print(f"--- Replicate {i}/{N_REPLICATES} ---")
        features = compute_features_for_institution(
            UNITID, NAME, sector=SECTOR, start_year=START_YEAR,
            **HIGH_PRECISION_SETTINGS,
        )
        if features is None:
            print("INSUFFICIENT DATA -- unexpected at this stage; stopping.")
            return
        result = clf.classify(features)
        entropy_vals.append(features.frac_high_entropy)
        debt_vals.append(features.debt_spike)
        prob_vals.append(result.probability)
        print(f"frac_high_entropy = {features.frac_high_entropy:.4f}")
        print(f"debt_spike = {features.debt_spike}")
        print(f"classification = {'high_risk' if result.prediction == 1 else 'stable'} "
              f"({result.probability:.4%} probability high_risk)")

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"frac_high_entropy across {N_REPLICATES} replicates: {entropy_vals}")
    print(f"debt_spike across {N_REPLICATES} replicates: {debt_vals}")
    print(f"probability across {N_REPLICATES} replicates: "
          f"{[f'{p:.4f}' for p in prob_vals]}")
    entropy_spread = max(entropy_vals) - min(entropy_vals)
    print(f"frac_high_entropy spread: {entropy_spread:.4f}")
    if entropy_spread == 0.0:
        print(
            "All replicates agreed at high precision. Check the CONVERGENCE lines "
            "printed above (from score_institution.py) for each replicate's "
            "divergence count and max rhat -- if divergences are at or near 0 and "
            "rhat is close to 1.0 across all three, this is a real, properly-"
            "converged result and should replace both of the unstable production-"
            "settings values in the write-up. If divergences are still nonzero "
            "even here, under-resolution is ruled out as the explanation and the "
            "instability runs deeper than sampling precision."
        )
    else:
        print(
            "Replicates still disagree even at 4 chains / 800+800 / target_accept="
            "0.95. Under-resolution is not the explanation -- whatever is driving "
            "this is not fixed by more precision alone."
        )


if __name__ == "__main__":
    main()
