"""
Diagnostic: is Thomas Aquinas College's posterior genuinely multimodal
or near-non-identifiable -- does a real change in random seed (fresh
NUTS jitter initialization, fresh stochastic exploration) find a
different answer -- independent of backend or runner hardware?

Every diagnostic before this one, across the entire investigation --
including the ten Numba-backend runs that just came back 10/10 stable
on frac_high_entropy -- reused the same hardcoded random_seed=7. That
was never deliberate: it's what score_institution.py always used, so
every "N replicates" comparison anywhere in this investigation was
actually testing "does the identical deterministic computation repeat
itself," never "is this model's posterior stable to how the sampler is
initialized." Real seed variation has never actually been tested until
this script.

This matters directly for the question the Numba result raised but
didn't answer: rhat never dropped below PyMC's own 1.01 threshold in
ANY of the ten Numba runs (1.2398 x8, 1.1817 x2), even though the
resulting classification (frac_high_entropy) stayed at 0.0000 all ten
times. If different seeds land on genuinely different frac_high_entropy
values, that's real evidence of multiple distinct modes the sampler can
land in depending on where it starts -- a structural property of the
model and this institution's specific data, fixable only by
reparameterizing, not by any backend or environment change. If
different seeds all agree, the persistent rhat>1.01 is more likely
real-but-benign sampling inefficiency (slow/uneven exploration of one
region) rather than genuine multimodality.

Runs at 10 explicitly different seeds -- deliberately never including
7, the one value every other diagnostic in this investigation has
used -- under the Numba backend (confirmed genuinely engaged and the
most stable backend tested so far), so 10 real evaluations are cheap
enough for a single job (~10s of sampling each, based on the Numba
results already gathered).
"""

from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
SEEDS = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11]  # deliberately varied; 7 excluded on purpose


def main():
    results = []
    for i, seed in enumerate(SEEDS, start=1):
        print(f"\n=== Seed {seed} ({i}/{len(SEEDS)}) ===")
        features = compute_features_for_institution(
            UNITID, NAME, cores=1, compile_mode="NUMBA", random_seed=seed,
        )
        if features is None:
            print(f"Seed {seed}: returned None (insufficient live data) -- not counted below.")
            continue
        results.append((seed, features.frac_high_entropy))
        print(f"Seed {seed} frac_high_entropy: {features.frac_high_entropy:.4f}")

    print("\n=== SUMMARY ===")
    print(f"Valid seeds: {len(results)}/{len(SEEDS)}")
    for seed, val in results:
        print(f"  seed {seed}: frac_high_entropy={val:.4f}")
    distinct_values = sorted(set(round(v, 4) for _, v in results))
    if len(distinct_values) <= 1:
        print("RESULT: every varied seed agreed on frac_high_entropy. Check each "
              "seed's own CONVERGENCE/rhat line above before treating this as fully "
              "resolved -- rhat agreement, not just frac_high_entropy agreement, is "
              "what would actually rule out multimodality.")
    else:
        print(f"RESULT: seeds DISAGREED -- {len(distinct_values)} distinct "
              f"frac_high_entropy values across {len(results)} genuinely different "
              f"seeds: {distinct_values}. This is real evidence of a multimodal or "
              f"near-non-identifiable posterior for this institution's data, "
              f"independent of backend or hardware.")


if __name__ == "__main__":
    main()
