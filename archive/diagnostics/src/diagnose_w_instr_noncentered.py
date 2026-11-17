"""
Item 6, continued: tests the non-centered reparameterization of
W_instr_latent (model_variant_noncentered_w_instr.py) against Thomas
Aquinas College (UNITID 124292), directly comparable to
diagnose_sigma_fin_split.py's own log -- same institution, same
settings, same two-independent-runs structure. That prior run's real
result: sigma_fin_instr=1.0983 (worst parameter in the whole model),
W_instr_latent=1.0605, essentially unchanged from the pre-split value
(1.0639). diagnose_sigma_fin_instr_funnel.py's follow-up found
sigma_fin_instr has the strongest sigma/latent-path-variance correlation
of all four channels (0.587) -- real, if partial, evidence of a funnel
geometry specific to this channel. This script tests the concrete fix
that finding points to: the same non-centered reparameterization
already proven for z_raw/xi_scale elsewhere in this model, applied to
W_instr_latent.

Method: monkey-patches model.build_model_stage2 to
model_variant_noncentered_w_instr.build_model_stage2_noncentered_w_instr
for this process only, exactly as diagnose_sigma_fin_split.py already
did for its own variant. Neither model.py on disk nor the live scoring
pipeline is touched.

What confirms or rejects: if W_instr_latent's rhat (and sigma_fin_instr's)
drops meaningfully toward 1.0 relative to diagnose_sigma_fin_split.py's
1.0605/1.0983, that's real, direct confirmation the funnel geometry was
the actual cause and the fix works -- and the same reparameterization
should then be considered for model.py's real build_model_stage2 (a
production change, to be confirmed with the maintainer first per CLAUDE.md,
same as any other consequential edit). If it doesn't move, or moves only
slightly, report that plainly -- this diagnostic-driven approach has
already surfaced two real, useful negative results in this investigation
(the volatility hypothesis, the posterior-magnitude-alone hypothesis),
and a third one would still be real progress, not a wasted step.
"""

from __future__ import annotations

import model
import model_variant_noncentered_w_instr as variant

model.build_model_stage2 = variant.build_model_stage2_noncentered_w_instr

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
    print(f"W_INSTR_LATENT NON-CENTERED TEST: {N_RUNS} independent runs at {SETTINGS}")
    print("=" * 70)
    print("Baseline to compare against (diagnose_sigma_fin_split.py's own log): "
          "sigma_fin_instr=1.0983 (worst in the model), W_instr_latent=1.0605. "
          "Testing whether non-centering W_instr_latent (same technique already "
          "proven for z_raw/xi_scale) fixes the funnel geometry "
          "diagnose_sigma_fin_instr_funnel.py's correlation check pointed to.")

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
    print("Compare each run's sigma_fin_instr and W_instr_latent rhat above against "
          "1.0983 / 1.0605. CONFIRMED if both drop meaningfully toward 1.0. "
          "REJECTED OR INCOMPLETE if they stay elevated -- report that plainly, per "
          "this project's own documentation standard, not as a partial win.")


if __name__ == "__main__":
    main()
