"""
Diagnostic for the "collapse, but already reset" gap documented in
README Known Gaps (found 2026-09-19, not yet built). Every one of the
eight validated features looks only at an institution's most recent
observed window (frac_high_entropy specifically at its last 5
periods) -- none of them ask whether a disruption visible earlier in
that same window is still worsening or has since stabilized.

University of Phoenix-Arizona (100.0% live) and Sweet Briar College
(80.1% live, 52.4% in the frozen panel) are this project's two live
test cases for that gap. Sweet Briar is the more useful one because it
has a REAL, CONFIRMED post-crisis recovery (announced closure 2015,
reopened after an alumnae-led rescue) to check a candidate fix
against, where Phoenix's restructuring outcome is not itself
independently confirmed one way or the other.

WHAT THIS SCRIPT DOES: computes, for both institutions, the concrete
within-window trajectory feature the README already scopes as the
next experiment (not a new idea invented here) -- splits each
institution's live lookback window into an EARLY segment (the
mid-window slice d_A_trend already uses elsewhere in this pipeline)
and a LATE segment (the most recent 5 periods -- the same window
frac_high_entropy already uses), and computes the downside-entropy-
based high-entropy fraction separately for each segment.

  within_window_trend = frac_high_entropy(LATE) - frac_high_entropy(EARLY)

A meaningfully POSITIVE value (late higher than early) reads as
entropy that is still rising within the window -- ongoing collapse. A
meaningfully NEGATIVE value (late lower than early) reads as entropy
that peaked earlier in the window and has since fallen -- stabilizing
after a shock, exactly what a real post-crisis recovery should look
like.

WHY SWEET BRIAR IS THE REAL TEST, NOT JUST A PLAUSIBLE STORY: Sweet
Briar's window is deliberately set to start at 2010 (not the panel/
live-batch default of 2013) specifically so it spans its real 2015
near-closure and its real post-2016 recovery. If this candidate
feature is doing what it's meant to, Sweet Briar's within_window_trend
should come back meaningfully NEGATIVE -- a real, falsifiable
prediction. If it instead comes back flat or positive, that is real
evidence against this specific construction, not a reason to force it
into the classifier anyway.

WHY PHOENIX IS NOT A CONFIRMATORY TEST THE SAME WAY: Phoenix's real,
large enrollment contraction and restructuring is well documented, but
whether that restructuring reads as a completed, stabilizing reset as
of the live pipeline's current window, or an ongoing decline, is not
itself an independently confirmed fact this project has. Phoenix's
result here is exploratory, read alongside Sweet Briar's, not a second
independent confirmation of the same kind.

WHAT THIS SCRIPT DELIBERATELY DOES NOT DO: it does not add
within_window_trend to classifier.FEATURE_NAMES, does not touch
dynamics.py, classifier.py, or score_institution.py, and does not
refit or re-validate the classifier against the panel. Promoting an
unvalidated 9th feature into the live classifier without a real
leave-one-out re-check against the full panel is exactly the kind of
unverified change this project does not make (see README Known Gaps
throughout, and recompute_panel_entropy.py's own docstring for the
precedent this would have to follow if this candidate holds up). This
script's only job is to produce the real numbers needed to decide
whether that further step is worth taking at all.

ADDED after the first real run (2026-09-20): that first run's own
console output flagged the standard rhat > 1.01 / low-ESS convergence
warnings at production settings, and Sweet Briar's within_window_trend
turned out to be driven almost entirely by a single terminal period
flipping from high-entropy to baseline, not a genuine multi-year
decline through its real, documented 2016-2022 recovery years -- the
same kind of convergence-vs-real-signal ambiguity
diagnose_window_mismatch.py and diagnose_clemson_wvu.py already exist
to resolve elsewhere in this project. This script now re-runs both
institutions a second time at the same higher-precision settings those
scripts use (1000 draws, 1000 tune, 4 chains, target_accept=0.95) and
reports whether each institution's LAST period's regime label, and its
overall within_window_trend, hold or change -- so a result resting on
one data point isn't reported as confirmed without that check.

Requires COLLEGE_SCORECARD_API_KEY in the environment (same as every
other live-data script in this project) -- run via GitHub Actions, not
locally: this project's sandboxed development environments cannot
reach NCES/College Scorecard (see fetch_live_data.py's own module
docstring).

Does NOT call save_live_score() -- never touches
docs/data/live_scores.json or the public dashboard. Diagnostic only.

Usage:
    python diagnose_reset_recovery.py
"""

from __future__ import annotations

import datetime
import traceback

import numpy as np
import pymc as pm

import model as mdl
import dynamics as dyn
import real_adapter as ra
import fetch_live_data as fld

# Sweet Briar: 2010, not the panel/live-batch default of 2013, so the
# window actually includes its real 2015 crisis rather than starting
# two years into it. University of Phoenix-Arizona keeps its known
# start_year=2014 override -- see score_batch.py's own docstring: 2013
# returned a genuinely empty College Scorecard record for this UNITID.
TARGETS = [
    ("233718", "Sweet Briar College", "private", 2010),
    ("484613", "University of Phoenix-Arizona", "forprofit", 2014),
]

# Production sampling settings (score_institution.py's own defaults) --
# this validates what would actually run in production, not a
# different, more expensive configuration nothing else in this
# pipeline runs with.
PRODUCTION_SETTINGS = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9)

# Same higher-precision settings diagnose_window_mismatch.py and
# diagnose_clemson_wvu.py already use to rule out ordinary MCMC
# non-convergence as a confound.
HIGH_PRECISION_SETTINGS = dict(n_draws=1000, n_tune=1000, n_chains=4, target_accept=0.95)

# Within-window_trend magnitude below this (in absolute value) is read
# as "no real within-window movement either way", not as a false
# negative -- avoids over-reading small-sample noise as a clean result.
FLAT_THRESHOLD = 0.05


def compute_within_window_trend(unitid: str, name: str, sector: str, start_year: int,
                                 end_year: int | None = None,
                                 n_draws: int = 300, n_tune: int = 300, n_chains: int = 2,
                                 target_accept: float = 0.9, label: str = "PRODUCTION") -> dict | None:
    end_year = end_year or (datetime.date.today().year - 2)

    series = fld.build_live_series(unitid, start_year, end_year, sector=sector)
    if series is None:
        print(f"INSUFFICIENT ENROLLMENT DATA for {name} ({unitid}) across {start_year}-{end_year}. "
              f"Not scoring rather than guessing.")
        return None

    O_o_real, O_p_real = ra.compute_O_o_O_p(series)
    types = ["observed"] * len(O_o_real)

    dest_base = f"/tmp/ipeds_live/{unitid}"
    finance_years_available = []
    for year in range(start_year, end_year):
        result = fld.download_ipeds_finance_bulk(year, dest_dir=dest_base, sector=sector)
        if result:
            finance_years_available.append(year)
    if len(finance_years_available) < 3:
        print(f"INSUFFICIENT FINANCE DATA for {name} ({unitid}): only "
              f"{len(finance_years_available)} real years downloaded. Not scoring rather than guessing.")
        return None

    window_years = [f"{y}-{str(y + 1)[2:]}" for y in range(start_year, end_year)]
    E_exch, M_maint, W_instr, W_total, mask, scale = fld.parse_live_finance(
        unitid, window_years, dest_base, sector=sector)
    if mask.sum() < 3:
        print(f"INSUFFICIENT PARSED FINANCE DATA for {name} ({unitid}): only "
              f"{int(mask.sum())} real years parsed. Not scoring rather than guessing.")
        return None

    pymc_model = mdl.build_model_stage2(O_o_real, O_p_real, types, types, E_exch, M_maint, W_instr, W_total, mask)
    with pymc_model:
        idata = pm.sample(n_draws, tune=n_tune, chains=n_chains, cores=n_chains,
                           target_accept=target_accept, progressbar=False, random_seed=7)

    Oo_post = idata.posterior["O_o_true"].mean(dim=["chain", "draw"]).values
    Op_post = idata.posterior["O_p_true"].mean(dim=["chain", "draw"]).values
    sigma_o = dyn.rolling_causal_variance(Oo_post, window=6)
    # Same directional-entropy construction validated 2026-09-20 for the
    # production frac_high_entropy feature (see dynamics.py's own
    # docstring) -- this diagnostic builds on the already-fixed measure,
    # not the superseded symmetric one.
    sigma_p = dyn.rolling_causal_downside_variance(Op_post, window=6)
    regime = dyn.classify_regime(sigma_o, sigma_p)

    n = len(window_years)
    # Same mid-window slice score_institution.py already uses for d_A_trend.
    early = slice(max(0, n // 2 - 3), max(1, n // 2))
    # Same trailing slice the production frac_high_entropy feature already uses.
    late = slice(max(0, n - 5), n)

    frac_early = float(np.mean(regime[early] == "high-entropy"))
    frac_late = float(np.mean(regime[late] == "high-entropy"))
    within_window_trend = frac_late - frac_early
    last_period_regime = str(regime[-1])

    print(f"\n{name} ({unitid}), {label} settings (n_draws={n_draws}, n_tune={n_tune}, "
          f"n_chains={n_chains}, target_accept={target_accept}): "
          f"real window {start_year}-{end_year - 1} ({n} periods)")
    print(f"  full regime series (period-by-period): {list(regime)}")
    print(f"  LAST period regime = {last_period_regime}")
    print(f"  frac_high_entropy, EARLY segment (periods {early.start}:{early.stop}) = {frac_early:.4f}")
    print(f"  frac_high_entropy, LATE segment (periods {late.start}:{late.stop}, "
          f"matches the production feature's own window) = {frac_late:.4f}")
    print(f"  within_window_trend (late - early) = {within_window_trend:+.4f}")

    return {
        "unitid": unitid, "name": name, "n_periods": n,
        "frac_early": frac_early, "frac_late": frac_late,
        "within_window_trend": within_window_trend,
        "last_period_regime": last_period_regime,
    }


def main():
    production_results = {}
    high_precision_results = {}

    for unitid, name, sector, start_year in TARGETS:
        print(f"\n{'=' * 90}\nPRODUCTION settings: {name} ({unitid})\n{'=' * 90}")
        try:
            r = compute_within_window_trend(unitid, name, sector, start_year,
                                             label="PRODUCTION", **PRODUCTION_SETTINGS)
            if r:
                production_results[unitid] = r
        except Exception as e:
            print(f"REAL ERROR (production) for {name} ({unitid}): {type(e).__name__}: {e}")
            traceback.print_exc()

    for unitid, name, sector, start_year in TARGETS:
        print(f"\n{'=' * 90}\nHIGH-PRECISION settings (convergence recheck): {name} ({unitid})\n{'=' * 90}")
        try:
            r = compute_within_window_trend(unitid, name, sector, start_year,
                                             label="HIGH-PRECISION", **HIGH_PRECISION_SETTINGS)
            if r:
                high_precision_results[unitid] = r
        except Exception as e:
            print(f"REAL ERROR (high-precision) for {name} ({unitid}): {type(e).__name__}: {e}")
            traceback.print_exc()

    print(f"\n{'=' * 90}\nSUMMARY\n{'=' * 90}")
    for unitid, name, sector, start_year in TARGETS:
        prod = production_results.get(unitid)
        hi = high_precision_results.get(unitid)
        if not prod:
            print(f"  {name}: no production-settings result (see real error/insufficient-data above).")
            continue

        def verdict_for(wwt):
            if wwt < -FLAT_THRESHOLD:
                return "NEGATIVE (stabilizing-after-shock read)"
            elif wwt > FLAT_THRESHOLD:
                return "POSITIVE (entropy still rising)"
            return f"FLAT (|trend| <= {FLAT_THRESHOLD})"

        print(f"\n  {name}:")
        print(f"    PRODUCTION     within_window_trend = {prod['within_window_trend']:+.4f} "
              f"[{verdict_for(prod['within_window_trend'])}], last period = {prod['last_period_regime']}")
        if hi:
            print(f"    HIGH-PRECISION within_window_trend = {hi['within_window_trend']:+.4f} "
                  f"[{verdict_for(hi['within_window_trend'])}], last period = {hi['last_period_regime']}")
            delta = hi["within_window_trend"] - prod["within_window_trend"]
            same_last_period = hi["last_period_regime"] == prod["last_period_regime"]
            if not same_last_period or abs(delta) > FLAT_THRESHOLD:
                print(f"    CONVERGENCE CHECK: DID NOT HOLD -- last-period regime "
                      f"{'changed' if not same_last_period else 'held'}, trend moved by {delta:+.4f}. "
                      f"The production result is likely at least partly a sampling artifact, not a "
                      f"confirmed real signal.")
            else:
                print(f"    CONVERGENCE CHECK: HELD -- same last-period regime, trend moved only "
                      f"{delta:+.4f}. The production result is not a convergence artifact.")
        else:
            print(f"    HIGH-PRECISION: no result (see real error/insufficient-data above) -- "
                  f"convergence could not be checked.")

    print(f"\n{'=' * 90}")
    print("READING THIS RESULT:")
    print("Sweet Briar's real, confirmed 2015-16 crisis-and-recovery is the actual test of")
    print("this candidate feature. Its first production-settings run showed within_window_trend")
    print("driven almost entirely by its single LAST period flipping regime, not a multi-year")
    print("decline through its real 2016-2022 recovery -- the CONVERGENCE CHECK above exists")
    print("specifically to tell whether that one flip is real or sampling noise.")
    print("If the check DID NOT HOLD for an institution, treat its production result as")
    print("unconfirmed -- do not report it as validated evidence either way.")
    print("If it HELD, the production number is a real, if still thin, empirical result --")
    print("document it exactly as it came out, including how much of it rests on one period.")
    print("This script does not update panel.json, dynamics.py, classifier.py, or")
    print("score_institution.py. Promoting this as a real 9th feature is a separate, later")
    print("step requiring a full live re-fit and leave-one-out re-validation of all 54 panel")
    print("institutions (the same kind of validation recompute_panel_entropy.py already did")
    print("for the directional-entropy fix), not automatic from this result alone.")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    main()
