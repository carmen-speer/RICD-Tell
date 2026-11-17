"""
Per-parameter rhat diagnostic for Thomas Aquinas College (UNITID 124292)
-- item 6 of this investigation's own stated plan: "identifying which
specific model parameters are driving the persistent rhat failure...
the real next step toward a reparameterization fix, if one exists" (see
the README's Known Gaps section).

Every diagnostic run in this entire investigation (highprecision,
extreme_precision, pinned_env, conda_blas, numba, varied_seed) has
reported only ONE number for convergence: the single worst rhat across
the whole model (CONVERGENCE's own rhat_max line). That number has never
dropped below PyMC's 1.01 threshold under any condition tested -- but it
can't say which of this model's roughly 20 free parameters is actually
responsible. This matters concretely: this project has already fixed
exactly this kind of problem once before, for a different parameter --
z_raw/xi_scale's centered-parameterization funnel (see model.py's own
docstring on that fix) -- by identifying the specific offending
parameter and reparameterizing it, not by adjusting sampler settings
around the whole model. Whether a comparable fix exists here depends on
first knowing which parameter(s) this run's rhat failure actually lives
on, which requires debug_param_rhat=True (2026-09-23, added to
score_institution.py specifically for this).

Same settings as the high-precision check (4 chains, 800 tune/800
draws, target_accept=0.95, cores=1) under the Numba backend now used in
production, at this project's usual fixed seed -- not a
reproducibility test (that question is already answered, see the
README), a single-question diagnostic: within one run, which parameter's
own posterior rhat is the worst, consistently across repeats. 2
independent runs, not 1 or 20 -- enough to see whether the same
parameter tops the list both times (a real, specific target) or a
different one each time (evidence the problem isn't localized to a
single parameter at all, itself a real and useful answer).
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
    compile_mode="NUMBA", debug_param_rhat=True,
)


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print(f"PER-PARAMETER RHAT DIAGNOSTIC: {N_RUNS} independent runs at {SETTINGS}")
    print("=" * 70)
    print("Goal: identify which specific free parameter(s) carry the worst "
          "rhat, consistently across repeats -- the real target for a "
          "reparameterization fix, not just confirmation that *some* "
          "parameter is unconverged (already known).")

    for i in range(1, N_RUNS + 1):
        print(f"--- Run {i}/{N_RUNS} ---")
        features = compute_features_for_institution(
            UNITID, NAME, sector=SECTOR, start_year=START_YEAR, **SETTINGS,
        )
        if features is None:
            print("INSUFFICIENT DATA -- unexpected at this stage; stopping.")
            return
        result = clf.classify(features)
        print(f"frac_high_entropy = {features.frac_high_entropy:.4f}, "
              f"classification = {'high_risk' if result.prediction == 1 else 'stable'} "
              f"({result.probability:.4%} probability high_risk)")

    print("=" * 70)
    print("Compare each run's PER-PARAMETER RHAT BREAKDOWN above. If the same "
          "starred (*) free parameter tops both runs' lists, that's a real, "
          "specific reparameterization target -- check whether it shares "
          "z_raw/xi_scale's original failure shape (a centered random walk "
          "whose own scale is simultaneously being fit -- see model.py's "
          "docstring on that fix) or a different geometry problem entirely. "
          "If the worst parameter differs between the two runs, the "
          "instability isn't localized to one parameter, which is itself a "
          "real, useful, and different answer -- it would mean this model's "
          "difficulty is more diffuse than the xi_scale case was, and a "
          "single targeted reparameterization is unlikely to be the whole "
          "fix.")


if __name__ == "__main__":
    main()
