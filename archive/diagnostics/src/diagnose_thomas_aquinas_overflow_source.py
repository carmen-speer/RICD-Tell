"""
Item 7: diagnose_thomas_aquinas_varied_seed.py already established that
all 10 genuinely varied seeds (1-6, 8-11; 7 deliberately excluded as
this project's usual fixed seed) agree on frac_high_entropy=0.0000 under
the Numba backend, rhat ranging 1.03-1.47 -- but 3 of those 10 runs also
threw `RuntimeWarning: overflow encountered in dot` from PyMC's own
sampler code. That was flagged in the README as a real, honest residual,
"not yet investigated" -- the original script only noticed the warning
appear in its own stdout; it never identified WHICH seeds triggered it,
or captured anything about the warning beyond that.

This script re-runs the same 10 seeds, but wraps each one's call to
compute_features_for_institution in Python's own warnings.catch_warnings
(record=True), so every warning actually raised during that seed's run
is captured directly rather than just printed to stdout and lost. For
each seed, prints whether the overflow warning fired, and if so, its
real category/message/filename/lineno -- the actual source location in
PyTensor/PyMC's own code where the overflow happened, not a guess at it.
Also runs with debug_param_rhat=True (already a real, existing parameter
on compute_features_for_institution -- see score_institution.py; not new
here) so each seed's per-parameter rhat breakdown prints too, to check
whether the seeds that overflow also share some other distinguishing
signature (a particular parameter's rhat spiking, say) or look ordinary
apart from the warning itself.

Nothing about the model or the live pipeline is touched -- this only
adds warning capture around the same public function every other
seed-based diagnostic in this investigation already calls.
"""
from __future__ import annotations

import warnings

from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
SEEDS = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11]  # identical to diagnose_thomas_aquinas_varied_seed.py


def main():
    print("=" * 70)
    print(f"OVERFLOW SOURCE CHECK: {NAME} ({UNITID}), {len(SEEDS)} varied seeds")
    print("=" * 70)
    print("Re-running diagnose_thomas_aquinas_varied_seed.py's own 10 seeds, this "
          "time with warnings.catch_warnings(record=True) around each run, so the "
          "overflow warning 3/10 of them threw last time is captured directly -- "
          "which seeds, and its real source -- instead of just noted as having "
          "appeared.")

    overflow_seeds = []
    clean_seeds = []

    for i, seed in enumerate(SEEDS, start=1):
        print(f"\n=== Seed {seed} ({i}/{len(SEEDS)}) ===")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            features = compute_features_for_institution(
                UNITID, NAME, cores=1, compile_mode="NUMBA", random_seed=seed,
                debug_param_rhat=True,
            )

        overflow_here = [w for w in caught if "overflow" in str(w.message).lower()]
        other_warnings = [w for w in caught if w not in overflow_here]

        if features is None:
            print(f"Seed {seed}: returned None (insufficient live data) -- not counted.")
            continue

        print(f"Seed {seed} frac_high_entropy: {features.frac_high_entropy:.4f}")

        if overflow_here:
            overflow_seeds.append(seed)
            print(f"Seed {seed}: OVERFLOW WARNING CAUGHT ({len(overflow_here)}x):")
            for w in overflow_here:
                print(f"    category={w.category.__name__}, "
                      f"file={w.filename}:{w.lineno}")
                print(f"    message: {w.message}")
        else:
            clean_seeds.append(seed)
            print(f"Seed {seed}: no overflow warning this run.")

        if other_warnings:
            print(f"Seed {seed}: {len(other_warnings)} other warning(s) also caught "
                  f"(not overflow-related, listed for completeness):")
            for w in other_warnings:
                print(f"    {w.category.__name__}: {w.message}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Seeds with overflow warning: {overflow_seeds if overflow_seeds else 'none'}")
    print(f"Seeds without: {clean_seeds}")
    print("Compare each overflow seed's own PER-PARAMETER RHAT BREAKDOWN above "
          "(printed by debug_param_rhat=True) against a clean seed's -- if the same "
          "free parameter tops both an overflow seed's and a clean seed's list, the "
          "overflow is likely incidental to normal NUTS exploration reaching an "
          "extreme value briefly, not a structural problem specific to those seeds. "
          "If overflow seeds share a distinct worst parameter that clean seeds don't, "
          "that IS a real, specific reparameterization target. Either way, this is "
          "the actual answer, not an assumption -- report it plainly, including if "
          "the overflow doesn't reproduce at all this run, which is itself real "
          "information about how reliably it triggers.")


if __name__ == "__main__":
    main()
