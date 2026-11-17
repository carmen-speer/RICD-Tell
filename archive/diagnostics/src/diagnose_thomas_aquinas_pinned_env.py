"""
Diagnostic: does a byte-identical, version-pinned software environment
(see Dockerfile.thomas_aquinas_pinned) produce the same Thomas Aquinas
College result across genuinely separate GitHub Actions job dispatches?

Every prior diagnostic in this investigation -- including this
project's own production score_batch.py -- has run on GitHub's
`ubuntu-latest` runners with dependencies resolved fresh by pip on each
job. random_seed=7 is fixed in score_institution.py and cannot vary
between runs, so agreement WITHIN a single job has never actually been
informative -- it's guaranteed by the fixed seed, not evidence of real
stability. The open question has always been whether SEPARATE job
dispatches agree, and real production rescore.yml runs today produced
three different values (95.5081%, 95.5081%, 66.80%) despite that fixed
seed -- which can only mean the environment or the hardware itself is
producing different floating-point results run to run.

This script runs ONE evaluation, deliberately, not several replicates,
because replicates inside one job would trivially agree regardless of
what's being tested here. The real comparison happens ACROSS separate
dispatches of the workflow that runs this script: run
diagnose_thomas_aquinas_pinned_env.yml several separate times from the
Actions tab and compare the CONVERGENCE and frac_high_entropy lines
each separate run prints.

  - If every separate dispatch agrees: environment drift was the real
    cause, and this pinned image should replace requirements.txt in
    production.
  - If separate dispatches still disagree despite byte-identical
    software: the cause is at the hardware/numerics level, which
    pinning software can't fix -- pointing toward a differently-seeded
    diagnostic instead, or documenting this as genuinely unresolved on
    GitHub's shared runner infrastructure.

Uses real production settings (cores=1; n_draws/n_tune/n_chains/
target_accept at score_institution.py's own defaults) rather than
extreme-precision settings, because the actual disagreement under
investigation happened at production settings, not extreme ones.
"""

from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"


def main():
    features = compute_features_for_institution(UNITID, NAME, cores=1)
    if features is None:
        print("Diagnostic inconclusive: returned None (insufficient live data).")
        return
    print(f"\nfrac_high_entropy: {features.frac_high_entropy:.4f}")
    print("Compare this run's CONVERGENCE line above and this "
          "frac_high_entropy value against OTHER SEPARATE dispatches "
          "of this same workflow -- agreement or disagreement across "
          "separate runs is the only thing this diagnostic tests.")


if __name__ == "__main__":
    main()
