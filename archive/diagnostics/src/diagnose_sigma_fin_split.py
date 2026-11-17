"""
Tests item 6's finding directly: does splitting the shared sigma_fin
observation-noise scale into four independent per-channel scales fix
Thomas Aquinas College's (UNITID 124292) worst rhat?

diagnose_thomas_aquinas_param_rhat.py's own run (2 independent runs,
identical results both times) found sigma_fin at max_rhat=1.1418 --
the single worst free parameter in the entire ~20-parameter model, by a
wide margin over the next-worst (1.0639) -- with four financial latent
variables (W_instr_latent, E_exch_latent, M_maint_latent, W_total_latent)
clustered right beneath it at 1.05-1.06. Reading model.py directly
explains why: sigma_fin is ONE shared HalfNormal(0.05) prior used as the
likelihood sigma for FOUR separate reported-financials observation
channels at once (E_exch, M_maint, W_instr, W_total), each tied to its
own independent GaussianRandomWalk latent. A single shared scale has to
satisfy four channels that plausibly carry genuinely different real
noise levels -- different IPEDS line items, different reporting
behavior -- which is a real, plausible source of exactly the poor
mixing observed, and the same general family of problem (a shared scale
jointly constrained by multiple downstream quantities) as the
already-fixed z_raw/xi_scale funnel, though a different specific
geometry (a shared observation-noise scale across four likelihoods, not
a process's own step scale).

Method: monkey-patches model.build_model_stage2 to point to
model_variant_split_sigma_fin.build_model_stage2_split_sigma_fin -- a
diagnostic-only copy of build_model_stage2 that changes exactly one
thing (sigma_fin -> sigma_fin_exch/maint/instr/total, four independent
priors instead of one shared value) -- for the duration of this script's
own process only. model.py on disk and the live scoring pipeline are
both untouched; this is a real, isolated test of an unconfirmed
hypothesis, per this project's own documentation standard, not a
production change. Everything downstream of the model (feature
extraction, classification) is otherwise identical to the real
pipeline, reusing score_institution.compute_features_for_institution
unmodified -- the patch is transparent to it.

Same settings as diagnose_thomas_aquinas_param_rhat.py's own run, so the
two logs are directly, line-for-line comparable: 4 chains, 800
tune/800 draws, target_accept=0.95, cores=1, Numba backend, this
project's usual fixed seed, debug_param_rhat=True. 2 independent runs.

What confirms or rejects the hypothesis: if sigma_fin_exch/maint/instr/
total all now show rhat near 1.0, and the four latent variables' rhat
drops along with them, that is real, direct confirmation -- and the
same split should then be made for real in model.py's build_model_stage2
(a small, targeted, verifiable change, the same shape as the
z_raw/xi_scale fix). If any of the four new sigmas is still elevated,
or the model's overall max rhat hasn't meaningfully dropped, the
hypothesis is wrong or incomplete, and that is the real answer to
report -- not a reason to call this a partial success.
"""

from __future__ import annotations

import model
import model_variant_split_sigma_fin as variant

# The one line doing the actual test: for the rest of this process only,
# any caller that looks up model.build_model_stage2 (or mdl.build_model_
# stage2, same module object under score_institution.py's own alias)
# gets the split-sigma variant instead. Nothing on disk changes.
model.build_model_stage2 = variant.build_model_stage2_split_sigma_fin

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
    print(f"SIGMA_FIN SPLIT TEST: {N_RUNS} independent runs at {SETTINGS}")
    print("=" * 70)
    print("Testing item 6's finding: sigma_fin (one shared observation-noise "
          "scale across 4 financial channels) was the worst free parameter in "
          "both prior runs, at an identical 1.1418, by a wide margin over "
          "everything else. Hypothesis: splitting it into 4 independent "
          "per-channel scales resolves it. Look for: do sigma_fin_exch/maint/"
          "instr/total all converge (rhat near 1.0)? Does the rhat on "
          "E_exch_latent, M_maint_latent, W_instr_latent, W_total_latent drop "
          "along with them?")

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
    print("Compare each run's PER-PARAMETER RHAT BREAKDOWN above against "
          "diagnose_thomas_aquinas_param_rhat.py's log (sigma_fin at 1.1418, "
          "the 4 latents at 1.05-1.06). CONFIRMED if sigma_fin_exch/maint/"
          "instr/total and the 4 latents all now sit near 1.0. REJECTED OR "
          "INCOMPLETE if any of the 4 new sigmas is still elevated, or the "
          "model's overall max rhat hasn't meaningfully dropped -- report "
          "that plainly, not as a partial win, per this project's own "
          "documentation standard.")


if __name__ == "__main__":
    main()
