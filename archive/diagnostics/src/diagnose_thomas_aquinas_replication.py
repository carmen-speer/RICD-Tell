"""
Replication diagnostic for Thomas Aquinas College (124292): tests
whether the same nominal settings actually reproduce the same result,
rather than testing across different settings the way Step 1 of
diagnose_thomas_aquinas.py did.

Why this exists: diagnose_thomas_aquinas.py's Step 1 compared
production settings (300/300/2/0.9) against high-precision settings
(1000/1000/4/0.95) WITHIN one script run, found frac_high_entropy
identical at both (0.0000), and concluded this wasn't a convergence
artifact. But a real, separate invocation of the SAME nominal
production settings -- the original score_batch.py run on
2026-09-22 -- got frac_high_entropy=1.0000 and a 95.5% probability,
not the 0.0000/66.8% this diagnostic's own production-settings call
got. debt_spike (computed directly from finance data, no MCMC
involved) was bit-identical across all of these runs (0.143652), so
this isn't a data problem -- it's specifically the posterior-derived
features that disagree between separately-run, nominally identical
invocations.

compute_features_for_institution() hardcodes random_seed=7 inside its
own pm.sample() call (score_institution.py) rather than exposing it
as a parameter, so this isn't a question of which seed to try -- the
seed is already fixed and identical across every call. This
diagnostic doesn't attempt to vary it. It simply calls the existing,
unmodified function multiple times in a row, at the same production
settings, and reports whether frac_high_entropy and the resulting
probability actually agree across those calls. If they don't, that
confirms the non-determinism isn't coming from seed choice at all --
most likely multiprocess sampling (cores=n_chains) combined with the
degraded, non-BLAS-linked math PyTensor has been warning about on
every run in this environment (see the "PyTensor could not link to a
BLAS installation" warning printed on every scoring run so far).

This has an implication bigger than Thomas Aquinas College alone, and
it's stated here rather than left implicit: every other "identical
across settings, not a convergence artifact" resolution already
documented in this project (Clemson, West Virginia, Houston) only
ever compared two DIFFERENT settings within a single run -- none of
them tested whether the SAME settings reproduce across independent
runs. If this diagnostic finds real variance here, those earlier
resolutions may need the same scrutiny, not just this one institution.
"""

from __future__ import annotations

from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
SECTOR = "private"
START_YEAR = 2013
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
    print("compute_features_for_institution() is called exactly as score_batch.py "
          "calls it -- no seed override, no code change -- to test whether 'the "
          "same settings' actually means 'the same result.'\n")

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
    spikes = [r[1] for r in valid]
    probs = [r[2] for r in valid]
    print(f"frac_high_entropy across {len(valid)} replicates: {entropies}")
    print(f"debt_spike across {len(valid)} replicates:        {spikes}")
    print(f"probability across {len(valid)} replicates:       {[f'{p:.4f}' for p in probs]}")

    entropy_spread = max(entropies) - min(entropies)
    prob_spread = max(probs) - min(probs)
    spike_spread = max(spikes) - min(spikes)

    print(f"\nfrac_high_entropy spread: {entropy_spread:.4f}")
    print(f"probability spread:       {prob_spread:.4f}")
    print(f"debt_spike spread:        {spike_spread:.8f} (expected ~0.0 -- computed "
          f"directly from finance data, no MCMC involved)")

    if entropy_spread > 0.0:
        print("\nCONFIRMED: frac_high_entropy varies across replicates run at IDENTICAL "
              "nominal settings (including the same hardcoded random_seed=7). This is "
              "real, non-seed-driven non-determinism -- most likely multiprocess "
              "sampling (cores=n_chains) combined with the degraded, non-BLAS-linked "
              "math PyTensor warns about on every run in this environment. This is not "
              "resolvable by re-running at higher precision alone (diagnose_thomas_aquinas.py's "
              "Step 1 already tried that); it needs either single-core sampling "
              "(cores=1) to test whether multiprocessing itself is the cause, or a real "
              "BLAS installation in the CI environment to test whether degraded math is "
              "the cause. Neither has been tried yet -- this print identifies the next "
              "real step, not a fix.")
    else:
        print("\nfrac_high_entropy held constant across all replicates -- the original "
              "1.0000 vs. this diagnostic's 0.0000 was NOT reproducible non-determinism "
              "within this run; something else changed between the 2026-09-22 batch run "
              "and this diagnostic (live data drift is the remaining real candidate, "
              "since debt_spike -- computed from finance data -- has held identical "
              "throughout; enrollment-series data feeding the state-space model has not "
              "been checked for drift and would be the next thing to compare directly).")


if __name__ == "__main__":
    main()
