"""
Isolation test for Thomas Aquinas College's (124292) reproducibility
failure: does forcing single-process (cores=1) sampling, instead of
this pipeline's default multiprocessing (cores=n_chains), restore
full reproducibility at production settings?

Why this is the right isolation, not another guess:
diagnose_thomas_aquinas_replication.py already established, from real
data, that six of seven identical-nominal-settings invocations
(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9,
random_seed=7 fixed in every case) landed on frac_high_entropy=1.0000
with 153 sampler divergences, and the seventh landed on 0.0000 with
zero divergences -- real non-determinism despite an identical fixed
seed. The two live suspects, both already visible in this
environment's own logs, are (1) cores=n_chains, meaning production
always runs its chains as separate OS processes, where a single
top-level random_seed is not guaranteed to fully determine each
child process's actual execution, and (2) the degraded,
non-BLAS-linked math PyTensor has warned about on every run in this
project ("PyTensor could not link to a BLAS installation... will be
severely degraded"), which can take different floating-point paths
run to run independent of multiprocessing.

This script tests suspect (1) directly: cores is now a real, separate
parameter on compute_features_for_institution (added 2026-09-23 to
score_institution.py, defaulting to n_chains so no existing caller's
behavior changes). Setting cores=1 here, with n_chains still 2, keeps
the exact same statistical procedure -- 2 chains, 300 tune, 300
draws each, same seed -- but runs them sequentially in a single
process instead of two parallel ones.

Reading the result: if cores=1 reproduces cleanly across all 5
replicates (whichever value it lands on), that confirms
multiprocessing is at least part of the real cause -- the fix would
be running this pipeline's diagnostics (and possibly production
scoring itself) at cores=1 when reproducibility matters more than
wall-clock speed. If cores=1 STILL varies across replicates, that
rules multiprocessing out as the sole cause and points at the
degraded math itself, or something else not yet identified -- not a
conclusion to force either way, just what the data says.
"""

from __future__ import annotations

from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
SECTOR = "private"
START_YEAR = 2013
N_REPLICATES = 5

# Same statistical procedure as production (n_chains=2, 300/300/0.9),
# with cores forced to 1 -- chains run sequentially, in one process,
# instead of production's default cores=n_chains (parallel processes).
CORES1_SETTINGS = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9, cores=1)


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print(f"CORES=1 ISOLATION TEST: {N_REPLICATES} independent calls, "
          f"n_chains=2 but cores=1 (sequential, single process)")
    print(f"Settings: {CORES1_SETTINGS}")
    print("=" * 70)

    replicate_results = []
    for i in range(1, N_REPLICATES + 1):
        print(f"\n--- Replicate {i}/{N_REPLICATES} ---")
        features = compute_features_for_institution(
            UNITID, NAME, sector=SECTOR, start_year=START_YEAR, **CORES1_SETTINGS)
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
    print(f"frac_high_entropy across {len(valid)} replicates: {entropies}")
    print(f"probability across {len(valid)} replicates:       {[f'{p:.4f}' for p in probs]}")
    print(f"frac_high_entropy spread: {entropy_spread:.4f}")

    if entropy_spread == 0.0:
        print("\ncores=1 reproduced cleanly across all replicates. This confirms "
              "multiprocessing (cores=n_chains in production) is at least part of "
              "the real cause of the instability found under cores=2 -- forcing "
              "cores=1 is a real, available fix wherever reproducibility matters "
              "more than wall-clock speed, though it does not by itself tell us "
              "whether the degraded, non-BLAS-linked math is a separate, latent "
              "issue that simply isn't triggered here.")
    else:
        print("\ncores=1 STILL varies across replicates -- multiprocessing is NOT "
              "the sole cause (or not a cause at all). The degraded, "
              "non-BLAS-linked math PyTensor warns about on every run remains the "
              "next real suspect, and would need its own isolation (a real BLAS "
              "installation in the CI environment) to confirm -- not yet tried.")


if __name__ == "__main__":
    main()
