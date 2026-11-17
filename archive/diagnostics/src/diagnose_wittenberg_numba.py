"""
High-precision, Numba-backend convergence diagnostic for Wittenberg
University (UNITID 206525) -- the deferred follow-up named in the
README's Known Gaps section: "re-run Wittenberg specifically at
high-precision settings, the same convergence-isolation check already
used for Thomas Aquinas, Clemson, and West Virginia, once the
higher-priority investigation above frees up to take it on."

That higher-priority investigation (Thomas Aquinas's reproducibility
instability) is the reason this is a combined check rather than a
plain repeat of diagnose_thomas_aquinas_highprecision.py's pattern:
production has since switched to compile_mode="NUMBA" for real (see
score_institution.py and score_batch.py, 2026-09-22), on the strength
of that investigation's 20/20 stable result for Thomas Aquinas. So the
question worth asking for Wittenberg is no longer "does more precision
fix this under the old default C-compiled path" -- that path isn't
what production runs anymore -- it's "does more precision, under the
backend production actually uses now, resolve the elevated rhat." A
default-path-only high-precision test would answer a question about a
backend this project has already moved away from.

What prompted this: Wittenberg's most recent real production batch run
(production settings: 300/300/2 chains, target_accept=0.9, cores=1,
default compile path at the time) landed at 95.34% high_risk alongside
max rhat=1.7710 -- well past PyMC's own 1.01 warning threshold, the
single highest rhat value observed anywhere in this project's history
across any institution. Deferred rather than investigated immediately,
specifically because Thomas Aquinas's reproducibility investigation was
judged the higher-priority open question at the time (it touches
confidence in the live pipeline broadly, not one institution). Now that
that investigation has a real, evidence-backed adopted fix (Numba,
20/20 stable), this picks the Wittenberg thread back up.

Substantively, a high score is plausible on independent grounds
regardless of what this diagnostic finds: Wittenberg is under a real,
confirmed Higher Learning Commission financial-distress probation --
see the README's Known Gaps section for why that kept it scored by the
statistical classifier rather than added to GOVERNANCE_OVERRIDE_UNITIDS.
This diagnostic is about whether the *rhat=1.7710* specifically is a
sampling artifact or a real, trustworthy number, not about whether
Wittenberg's underlying financial distress is real -- those are
separate questions, and only the first one is this script's target.

COMPILE MODE CHECK, then N_REPLICATES independent calls at:
  compile_mode="NUMBA"  (production's real backend as of 2026-09-22)
  n_chains=4       (PyMC's own stated recommendation, vs. production's 2)
  n_tune=800        (vs. production's 300)
  n_draws=800       (vs. production's 300)
  target_accept=0.95   (vs. production's 0.9 -- smaller, more careful
                         steps, the standard first remedy for divergences)
  cores=1           (sequential, matching every other diagnostic and
                      production itself since the Thomas Aquinas
                      cores=1/cores=2 finding)
  random_seed left at its default (7) -- this is a precision-and-backend
  test, not a seed-variation test; see diagnose_thomas_aquinas_varied_seed.py
  for that separate question, not yet asked of Wittenberg.

3 replicates, not 1: at these settings each call takes substantially
longer than production's ~30-45 seconds, but this is specifically
checking whether a real, converged, stable result reproduces across
independent calls in the same job, the same standard
diagnose_thomas_aquinas_highprecision.py used -- one clean-looking
result on its own is not evidence of anything (the same trap this
whole project has already been caught by once, with Thomas Aquinas).
"""

from __future__ import annotations

import pytensor
import pytensor.tensor as pt

from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

UNITID = "206525"
NAME = "Wittenberg University"
SECTOR = "private"
START_YEAR = 2013
COMPILE_MODE = "NUMBA"
N_REPLICATES = 3

HIGH_PRECISION_SETTINGS = dict(
    n_draws=800, n_tune=800, n_chains=4, target_accept=0.95, cores=1,
    compile_mode=COMPILE_MODE,
)

# The real production result this diagnostic is checking, for direct
# comparison in the summary below -- taken from the most recent real
# batch run at the time this script was written (production settings,
# default compile path, before the Numba switch), not re-derived here.
PRODUCTION_REFERENCE_PROBABILITY = 0.9534
PRODUCTION_REFERENCE_RHAT = 1.7710


def _confirm_compile_mode(mode):
    """
    Same direct check used in diagnose_thomas_aquinas_numba.py: compiles
    a trivial function (f(x) = x * 2) with the given mode and prints the
    actual linker class PyTensor produced, rather than inferring
    engagement indirectly from timing or warning text. A linker class
    name containing "Numba" confirms real engagement.
    """
    x = pt.dscalar("x")
    f = pytensor.function([x], x * 2, mode=mode)
    linker = f.maker.linker
    linker_name = f"{type(linker).__module__}.{type(linker).__name__}"
    print(f"COMPILE MODE CHECK: requested mode={mode!r} -> actual linker class={linker_name}")
    if "numba" in linker_name.lower():
        print("COMPILE MODE CHECK: CONFIRMED -- Numba linker really is engaged.")
    else:
        print("COMPILE MODE CHECK: NOT CONFIRMED -- this did not produce a Numba "
              "linker. The mode request may be silently falling back to the "
              "default path; the results below should not be trusted as a real "
              "Numba-backend result until this is resolved.")


def main():
    _confirm_compile_mode(COMPILE_MODE)

    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print(f"WITTENBERG HIGH-PRECISION + NUMBA CHECK: {N_REPLICATES} independent "
          f"calls at {HIGH_PRECISION_SETTINGS}")
    print("=" * 70)
    print(f"Comparing against the real production reference: "
          f"{PRODUCTION_REFERENCE_PROBABILITY:.4%} high_risk, "
          f"max rhat={PRODUCTION_REFERENCE_RHAT:.4f} (default compile path, "
          f"production settings, before the Numba switch).")

    entropy_vals = []
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
        prob_vals.append(result.probability)
        print(f"frac_high_entropy = {features.frac_high_entropy:.4f}")
        print(f"classification = {'high_risk' if result.prediction == 1 else 'stable'} "
              f"({result.probability:.4%} probability high_risk)")

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"frac_high_entropy across {N_REPLICATES} replicates: {entropy_vals}")
    print(f"probability across {N_REPLICATES} replicates: "
          f"{[f'{p:.4f}' for p in prob_vals]}")
    entropy_spread = max(entropy_vals) - min(entropy_vals)
    prob_spread = max(prob_vals) - min(prob_vals)
    print(f"frac_high_entropy spread: {entropy_spread:.4f}")
    print(f"probability spread: {prob_spread:.4f}")
    if entropy_spread == 0.0:
        print(
            "All replicates agreed on frac_high_entropy under Numba at high "
            "precision. Check each replicate's own CONVERGENCE line above for "
            "its real rhat -- if rhat is close to 1.0 across all three, this is "
            "a real, properly-converged result and should replace the "
            "production-settings 95.34%/rhat=1.7710 figure in the write-up. If "
            "rhat is still elevated even here, that's the same honest residual "
            "already documented for Thomas Aquinas under Numba: classification "
            "output can be stable even when PyMC's own rhat<1.01 threshold is "
            "never actually met."
        )
    else:
        print(
            "Replicates disagree even at high precision under Numba -- "
            "Wittenberg would then join Thomas Aquinas as a second real "
            "instance of this instability, not an isolated case."
        )


if __name__ == "__main__":
    main()
