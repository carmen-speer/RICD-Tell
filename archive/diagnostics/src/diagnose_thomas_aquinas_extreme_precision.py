"""
Diagnostic: can Thomas Aquinas College's model ever actually converge
(real rhat < 1.01, PyMC's own threshold) given enough sampling effort,
or does it fail to converge no matter how hard the settings are pushed?

Every single Thomas Aquinas run across this entire investigation --
pip or conda, cores=1 or cores=2, production or "high" precision -- has
failed PyMC's own convergence threshold. The closest anything got was
an earlier high-precision test (800 draws/800 tune/4 chains/
target_accept=0.95) at rhat=1.1062, still failing but closer than
anything else tried, including the conda/BLAS run (rhat=1.3936, worse
than the best pip-based result seen so far). This script pushes much
harder than any of those: target_accept=0.99 (vs. 0.9 in production,
0.95 in the earlier "high precision" test), far more tuning and draws
(2000/2000 vs. 300/300 or 800/800), and 4 chains (vs. production's 2).

Two possible outcomes, each meaningful on its own:
  - If rhat drops below 1.01 here: this is a "needs better settings"
    problem, not a structural one -- a real, comparatively cheap fix
    (raise the production settings for this institution, or across the
    board).
  - If rhat still fails even at these extreme settings: that's real
    evidence the model's posterior for this institution's specific data
    is genuinely hard to sample (most likely multimodal or
    near-non-identifiable), which needs a different kind of fix
    (reparameterization or a model change), not just more compute.

Deliberately pip-based, not conda -- this isolates ONE variable
(sampling settings) rather than changing settings and the BLAS backend
at the same time, so whatever this shows can't be confounded with the
separate conda/BLAS result already gathered.

N=3 replicates, not 1: if it converges, we also want to know whether a
converged run is actually reproducible run-to-run, not just whether
convergence is possible once.
"""

from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
N_REPLICATES = 3


def main():
    results = []
    for i in range(1, N_REPLICATES + 1):
        print(f"\n=== Extreme-precision replicate {i}/{N_REPLICATES} ===")
        features = compute_features_for_institution(
            UNITID, NAME, cores=1,
            n_draws=2000, n_tune=2000, n_chains=4, target_accept=0.99,
            debug_per_chain=True,
        )
        if features is None:
            print(f"Replicate {i}: returned None (insufficient live data) -- "
                  f"not counted below.")
            continue
        results.append(features.frac_high_entropy)
        print(f"Replicate {i} frac_high_entropy: {features.frac_high_entropy:.4f}")

    print("\n=== SUMMARY ===")
    print(f"Valid replicates: {len(results)}/{N_REPLICATES}")
    print(f"All frac_high_entropy values: {results}")
    print("Check each replicate's own CONVERGENCE line above for its real "
          "rhat -- this summary doesn't repeat it, since whether rhat "
          "actually dropped below 1.01 is the real question this script "
          "is testing, not just frac_high_entropy agreement.")
    if len(set(results)) <= 1 and results:
        print("RESULT: frac_high_entropy agreed across all replicates at "
              "these extreme settings. Check the rhat values above before "
              "treating that as resolved -- agreement without real "
              "convergence (rhat < 1.01) is the same trap this whole "
              "investigation started from.")
    elif results:
        print("RESULT: frac_high_entropy did NOT agree across replicates "
              "even at these extreme settings -- real evidence the "
              "instability survives more sampling effort, not just a "
              "settings problem.")


if __name__ == "__main__":
    main()
