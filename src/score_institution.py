"""
The real, end-to-end deployment entry point: given a UNITID, fetch
live data, run it through the RICD state-space model, extract the
eight validated features, and produce a real classification.

This is the piece that did not exist before -- extract_features.py in
the original session was a hardcoded batch script for the known
54-institution validation panel, not a general-purpose scorer for a
new, unknown institution. This file replicates that same validated
pipeline (real_adapter.py + model.py + classifier.py) against live
data instead of pre-downloaded local files.

Usage:
    python score_institution.py <unitid> <institution name> [--sector private|public|forprofit]

Requires COLLEGE_SCORECARD_API_KEY set in the environment.
"""

from __future__ import annotations

import sys
import json
import csv
import argparse
import datetime
from pathlib import Path

import numpy as np
import pymc as pm
import arviz as az

import model as mdl
import dynamics as dyn
import real_adapter as ra
import fetch_live_data as fld
from classifier import RICDClassifier, InstitutionFeatures, load_panel, GOVERNANCE_OVERRIDE_UNITIDS


def compute_features_for_institution(
    unitid: str, name: str, sector: str = "private",
    start_year: int = 2013, end_year: int | None = None,
    n_draws: int = 300, n_tune: int = 300, n_chains: int = 2,
    target_accept: float = 0.9, cores: int | None = None,
    debug_per_chain: bool = False, compile_mode: str | None = None,
    random_seed: int = 7, debug_param_rhat: bool = False,
    allow_gaps: bool = False, drift_terms: bool = False,
) -> InstitutionFeatures | None:
    """
    Real, live scoring pipeline for one institution, replicating
    extract_features.py's validated process() function against live
    data. Returns None, with a printed reason, if live data is
    genuinely insufficient -- never fabricates a feature value to
    force a result through.

    n_draws/n_tune/n_chains/target_accept default to the values this
    pipeline has always run with in production (score_batch.py,
    rescore.yml), so passing none of them changes no existing
    behavior. They exist as real parameters -- not hardcoded inside
    the pm.sample() call below -- specifically so a diagnostic caller
    can rule out MCMC non-convergence as a confound (real rhat > 1.01
    and effective-sample-size warnings were observed at the
    production 300/300/2 settings when this was tested on 2026-09-15,
    on every single one of five known-stable panel institutions) by
    re-running the identical pipeline at higher settings, without
    duplicating or forking this function to do it.

    cores (2026-09-23 addition): defaults to None, which preserves the
    exact original behavior (cores=n_chains, real multiprocessing) for
    any existing caller that doesn't pass it. Real production callers
    now pass cores=1 explicitly (see main() below) -- confirmed during
    the Thomas Aquinas College investigation that cores=2 (real
    multiprocessing) can give an entire batch of otherwise-identical
    runs a different answer from another whole batch, while cores=1
    gave the same answer seven times in a row, including direct
    chain-to-chain agreement within each run. The default itself is
    left at None/n_chains rather than flipped to 1, so existing
    diagnostic scripts that deliberately test production's real
    multiprocessing behavior (e.g. diagnose_thomas_aquinas_replication.py)
    keep doing exactly that without being silently changed underneath them.

    CONVERGENCE printing (2026-09-22 addition): every call prints the
    real divergence count and max rhat from its own idata.

    debug_per_chain (2026-09-23 addition): defaults to False, no
    change to existing behavior. When True, also prints each
    individual chain's own frac_high_entropy value (computed from that
    chain alone, not averaged with the others) right after the
    CONVERGENCE line.

    compile_mode (2026-09-22 addition, Thomas Aquinas pinned-environment
    follow-up): defaults to None, which preserves the exact original
    behavior (PyTensor's default C-compiled path) for any existing
    caller that doesn't pass it -- including every production call.
    When set (e.g. "NUMBA"), it's forwarded to pm.sample() as
    compile_kwargs={"mode": compile_mode}, so a diagnostic caller can
    test an alternate PyTensor backend without duplicating or forking
    this function to do it. Added after diagnose_thomas_aquinas_pinned_env.py
    confirmed the Thomas Aquinas reproducibility instability survives a
    byte-identical, version-pinned software environment across separate
    job dispatches -- ruling out environment drift and pointing at
    PyTensor's default non-BLAS-linked fallback path itself (see its own
    "severely degraded" warning, printed on every run in this entire
    investigation) as the remaining candidate, not just the BLAS library
    underneath it.

    random_seed (2026-09-22 addition, Thomas Aquinas varied-seed
    follow-up): defaults to 7, the exact value every caller in this
    project has always used -- so any existing caller that doesn't pass
    it, production included, behaves identically to before. Exists as a
    real parameter, not hardcoded, specifically so
    diagnose_thomas_aquinas_varied_seed.py can test genuinely different
    seeds. This matters because every "N replicates" diagnostic run
    anywhere in this entire investigation, including all ten Numba-
    backend runs that came back 10/10 stable on frac_high_entropy, reused
    this same fixed seed -- meaning none of them had actually tested
    whether the sampler's own random initialization affects the result,
    only whether the identical deterministic computation repeats itself.
    Real seed variation had never been tested before this addition.

    debug_param_rhat (2026-09-23 addition, item 6 of the Thomas Aquinas
    investigation's own stated next step): defaults to False, no change
    to existing behavior. When True, prints every sampled variable's own
    max rhat, worst first, right after the CONVERGENCE line -- not just
    the single worst-case number that line already reports. The point:
    CONVERGENCE's rhat_max says *that* something in this model's ~20 free
    parameters hasn't converged; it can't say *which* one, and a real
    reparameterization fix (the kind that already worked once in this
    model -- see z_raw/xi_scale's non-centering in model.py's own
    docstring, which fixed that parameter's specific funnel geometry)
    needs to target the actual offending parameter, not the model as a
    whole. This distinguishes real sampled/free parameters (marked with
    a '*' in the printed output -- an actual prior NUTS is exploring)
    from Deterministics (unmarked -- these only inherit whatever rhat
    their upstream free parameters already have, so a high rhat on a
    Deterministic like d_A_t is a symptom of the real free-parameter
    problem, not a second, separate one to chase).
    """
    end_year = end_year or (datetime.date.today().year - 2)  # IPEDS lags by ~2 years
    window_years = [f"{y}-{str(y + 1)[2:]}" for y in range(start_year, end_year)]

    # --- Real, live enrollment/admissions/completion series ---
    series = fld.build_live_series(unitid, start_year, end_year, sector=sector, allow_gaps=allow_gaps)
    if series is not None and allow_gaps:
        # Minimum record ("sampling protocol v2.md"): at least three years
        # with enrollment, completion and tuition all present. Missing
        # years are not filled in; the model fits only the observed ones.
        complete_years = int(np.sum(~np.isnan(series["n_undergrads"])
                                    & ~np.isnan(series["completion"])
                                    & ~np.isnan(series["tuition"])))
        if complete_years < 3:
            print(f"INSUFFICIENT ENROLLMENT DATA: only {complete_years} years with "
                  f"enrollment, completion and tuition all present for {name} ({unitid}) "
                  f"across {start_year}-{end_year} (the minimum is 3). Not scoring rather "
                  f"than guessing.")
            return None
    if series is None:
        print(f"INSUFFICIENT ENROLLMENT DATA: could not build a complete real "
              f"series for {name} ({unitid}) across {start_year}-{end_year}. "
              f"Not scoring rather than guessing.")
        return None

    O_o_real, O_p_real = ra.compute_O_o_O_p(series)

    # --- Real, live finance data: download bulk files, then parse them ---
    dest_base = f"/tmp/ipeds_live/{unitid}"
    finance_years_available = []
    for year in range(start_year, end_year):
        result = fld.download_ipeds_finance_bulk(year, dest_dir=dest_base, sector=sector)
        if result:
            finance_years_available.append(year)
    if len(finance_years_available) < 3:
        print(f"INSUFFICIENT FINANCE DATA: only {len(finance_years_available)} real years "
              f"downloaded for {name} ({unitid}). This is the known-fragile part of the "
              f"pipeline (see fetch_live_data.py) -- likely means NCES changed its bulk-file "
              f"naming convention this cycle and the download pattern needs a manual update, "
              f"not that the institution actually lacks data. Not scoring rather than guessing.")
        return None

    E_exch, M_maint, W_instr, W_total, mask, scale = fld.parse_live_finance(
        unitid, window_years, dest_base, sector=sector)
    if mask.sum() < 3:
        print(f"INSUFFICIENT PARSED FINANCE DATA: only {int(mask.sum())} real years "
              f"of finance data actually parsed for {name} ({unitid}) after download -- "
              f"likely a field-code mismatch for this sector/year (see "
              f"fetch_live_data.PRIVATE_FINANCE_FIELDS / PUBLIC_FINANCE_FIELDS). "
              f"Not scoring rather than guessing.")
        return None

    # --- Real Bayesian trajectory fit, identical to the validated pipeline ---
    types = ["observed"] * len(O_o_real)
    if drift_terms:
        # "sampling protocol v3.md": the exchange base (RICD Definition
        # 10.3a.1) as log undergraduate enrollment relative to its own peak,
        # with missing years left as NaN for the model to skip.
        _n = np.asarray(series["n_undergrads"], dtype=float)
        _n = np.where(_n > 0, _n, np.nan)
        enroll_obs = np.log(_n) - np.log(np.nanmax(_n))
        pymc_model = mdl.build_model_stage2(O_o_real, O_p_real, types, types, E_exch, M_maint, W_instr,
                                            W_total, mask, enroll_obs=enroll_obs)
    else:
        pymc_model = mdl.build_model_stage2(O_o_real, O_p_real, types, types, E_exch, M_maint, W_instr, W_total, mask)
    with pymc_model:
        sample_kwargs = dict(
            tune=n_tune, chains=n_chains,
            cores=cores if cores is not None else n_chains,
            target_accept=target_accept, progressbar=False, random_seed=random_seed,
        )
        if compile_mode is not None:
            sample_kwargs["compile_kwargs"] = {"mode": compile_mode}
        idata = pm.sample(n_draws, **sample_kwargs)

    # CONVERGENCE (2026-09-22): real, extracted diagnostics, printed
    # directly from this run's own idata -- see docstring above.
    n_divergences = int(idata.sample_stats["diverging"].values.sum())
    rhat_max = float(az.rhat(idata).max().to_array().max())
    print(f"CONVERGENCE: {n_divergences} divergences, max rhat={rhat_max:.4f} "
          f"(rhat should be close to 1.0; PyMC's own warning threshold is 1.01)")

    # PER-PARAMETER RHAT BREAKDOWN (2026-09-23, opt-in only): see
    # debug_param_rhat's own docstring above for why this exists and how
    # to read the '*' marker.
    if debug_param_rhat:
        rhat_ds = az.rhat(idata)
        free_rv_names = {rv.name for rv in pymc_model.free_RVs}
        rows = []
        for var in rhat_ds.data_vars:
            var_vals = rhat_ds[var].values
            var_max_rhat = float(np.nanmax(var_vals))
            rows.append((var, var_max_rhat, var in free_rv_names))
        rows.sort(key=lambda r: r[1], reverse=True)
        print(f"PER-PARAMETER RHAT BREAKDOWN ({len(rows)} variables, worst first; "
              f"'*' = a real sampled/free parameter NUTS is directly exploring, "
              f"unmarked = a Deterministic that only inherits its rhat from "
              f"whichever free parameters feed it):")
        for var, var_max_rhat, is_free in rows:
            marker = "*" if is_free else " "
            print(f"  {marker} {var:20s} max_rhat={var_max_rhat:.4f}")

    # PER-CHAIN BREAKDOWN (2026-09-23, opt-in only): see docstring above.
    if debug_per_chain:
        n_chains_actual = idata.posterior.sizes["chain"]
        print(f"PER-CHAIN BREAKDOWN ({n_chains_actual} chains, each computed from "
              f"that chain alone, not averaged with the others):")
        for c in range(n_chains_actual):
            d_A_t_c = idata.posterior["d_A_t"].isel(chain=c).mean(dim=["draw"]).values
            Oo_post_c = idata.posterior["O_o_true"].isel(chain=c).mean(dim=["draw"]).values
            Op_post_c = idata.posterior["O_p_true"].isel(chain=c).mean(dim=["draw"]).values
            sigma_o_c = dyn.rolling_causal_variance(Oo_post_c, window=6)
            sigma_p_c = dyn.rolling_causal_downside_variance(Op_post_c, window=6)
            regime_c = dyn.classify_regime(sigma_o_c, sigma_p_c)
            frac_high_entropy_c = float(np.mean(regime_c[-5:] == "high-entropy"))
            divergences_c = int(idata.sample_stats["diverging"].isel(chain=c).values.sum())
            print(f"  chain {c}: frac_high_entropy={frac_high_entropy_c:.4f}, "
                  f"divergences={divergences_c}, d_A_t_final={float(d_A_t_c[-1]):.6f}")

    d_A_t = idata.posterior["d_A_t"].mean(dim=["chain", "draw"]).values
    delta_R_t = idata.posterior["delta_R_t"].mean(dim=["chain", "draw"]).values
    Oo_post = idata.posterior["O_o_true"].mean(dim=["chain", "draw"]).values
    Op_post = idata.posterior["O_p_true"].mean(dim=["chain", "draw"]).values
    D_op_proxy = np.abs(Oo_post - Op_post)
    sigma_o = dyn.rolling_causal_variance(Oo_post, window=6)
    # DIRECTIONAL ENTROPY FIX (2026-09-20, follow-up to the 2026-09-19
    # debt_spike-sign gate below in this same file's history): the
    # operational channel's variance is now downside-only
    # (dynamics.rolling_causal_downside_variance -- see its own
    # docstring for the full reasoning and the real evidence that made
    # the sign-gate approach insufficient). sigma_o is left as ordinary
    # symmetric variance -- it's a baseline comparison magnitude here,
    # not the signal needing direction correction.
    sigma_p = dyn.rolling_causal_downside_variance(Op_post, window=6)
    regime = dyn.classify_regime(sigma_o, sigma_p)
    # Diagnostic-only comparison against the OLD symmetric construction,
    # so a rescore run's log shows exactly what this fix changed for
    # this institution, rather than a silent, unverifiable delta the
    # way the debt_spike gate's console output originally was (see
    # "DIAGNOSTIC VISIBILITY" below, and the gap it closes).
    sigma_p_symmetric_old = dyn.rolling_causal_variance(Op_post, window=6)
    regime_old = dyn.classify_regime(sigma_o, sigma_p_symmetric_old)
    frac_high_entropy_old_symmetric = float(np.mean(regime_old[-5:] == "high-entropy"))

    n = len(window_years)
    mid = slice(max(0, n // 2 - 3), max(1, n // 2))
    late = slice(max(0, n - 5), n)
    d_A_mid = float(np.mean(d_A_t[mid])) if n > 3 else float(d_A_t[0])
    d_A_late = float(np.mean(d_A_t[late]))
    d_A_trend = d_A_late - d_A_mid
    d_A_final = float(d_A_t[-1])
    delta_R_final = float(delta_R_t[-1])
    frac_high_entropy = float(np.mean(regime[-5:] == "high-entropy"))

    def delta_R_trend_from(traj):
        traj = np.array(traj)
        n2 = len(traj)
        m = traj[n2 // 3: 2 * n2 // 3].mean()
        l = traj[-n2 // 4:].mean() if n2 >= 4 else traj[-1]
        return float(l - m)

    delta_R_trend = delta_R_trend_from(delta_R_t)

    # --- The remaining features, computed directly from real parsed data ---
    if sector == "private":
        _fields_for_sector = fld.PRIVATE_FINANCE_FIELDS
    elif sector == "forprofit":
        _fields_for_sector = fld.FORPROFIT_FINANCE_FIELDS
    else:
        _fields_for_sector = fld.PUBLIC_FINANCE_FIELDS
    liabilities_field = _fields_for_sector["total_liabilities"]
    # For-profit institutions have no real "endowment" key at all (see
    # FORPROFIT_FINANCE_FIELDS's own comment) -- .get() with a sentinel
    # that can't match a real column lets the lookup below fail
    # gracefully into the existing "no real endowment data" path
    # instead of a KeyError here, before that path even runs.
    endowment_field = _fields_for_sector.get("endowment", "NO_ENDOWMENT_FIELD_FOR_THIS_SECTOR")

    liabilities_by_year, endowment_val, research_val, instruction_val = {}, None, None, None
    for year in finance_years_available:
        year_dir = Path(dest_base) / str(year)
        csv_files = list(year_dir.glob("*.csv")) if year_dir.exists() else []
        if not csv_files:
            continue
        try:
            with open(csv_files[0], encoding="latin-1") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("UNITID") == unitid:
                        liabilities_by_year[year] = float(row[liabilities_field])
                        if endowment_val is None:
                            try:
                                endowment_val = float(row[endowment_field])
                            except (KeyError, ValueError):
                                pass
                        if sector == "private":
                            try:
                                research_val = float(row["F2E021"])
                                instruction_val = float(row["F2E011"])
                            except (KeyError, ValueError):
                                pass
                        break
        except (ValueError, KeyError, FileNotFoundError):
            continue

    if len(liabilities_by_year) < 3:
        print(f"INSUFFICIENT DEBT DATA: only {len(liabilities_by_year)} real years of "
              f"total-liabilities data parsed for {name} ({unitid}). Not scoring rather "
              f"than guessing.")
        return None

    years_sorted = sorted(liabilities_by_year)
    vals = [liabilities_by_year[y] for y in years_sorted]
    scale_max = max(vals) if max(vals) > 0 else 1.0
    vals_norm = [v / scale_max for v in vals]
    diffs = np.diff(vals_norm)
    debt_spike = float(np.max(diffs) - np.median(np.abs(diffs))) if len(diffs) > 0 else 0.0

    # nanmax (2026-11-14, "sampling protocol v2.md"): peak over observed
    # years only; identical to max for a complete series.
    peak_enrollment = float(np.nanmax(series["n_undergrads"])) if len(series["n_undergrads"]) else None
    if endowment_val is not None and peak_enrollment:
        reserve_adequacy = float(np.log1p(endowment_val / peak_enrollment))
    else:
        print(f"NOTE: no real endowment data found for {name} ({unitid}) -- "
              f"reserve_adequacy defaulting to 0.0 (log1p(0)), consistent with the "
              f"validated panel's treatment of institutions with a real, structural "
              f"absence of endowment data (e.g., for-profits) rather than a missing-data gap.")
        reserve_adequacy = 0.0

    research_ratio = (research_val / instruction_val) if (research_val and instruction_val) else 0.0

    # SUPERSEDED (2026-09-20): a debt_spike-sign gate previously lived here
    # (applied 2026-09-19), zeroing frac_high_entropy whenever
    # debt_spike <= 0. It is removed in favor of the fix now applied
    # upstream, at sigma_p's construction above
    # (dynamics.rolling_causal_downside_variance) -- see that function's
    # own docstring for the full reasoning. The gate is not merely
    # theoretically weaker: a real, live re-score run on 2026-09-19/20,
    # AFTER the gate was deployed, showed it never fired for Houston,
    # UCF, FSU, Buffalo, Clemson, or Cal State Long Beach -- every one of
    # them still scored high_risk at essentially the same probability as
    # before the gate existed. debt_spike and operational-entropy
    # direction are not the same signal for these institutions (most
    # likely because their own debt_spike came back positive, from
    # ordinary capital borrowing rather than distress), so gating one on
    # the other's sign could not separate a genuine positive shock from a
    # destabilizing one. debt_spike itself is untouched and still stored
    # below as its own independent feature.
    #
    # NOT yet validated against the real 54-institution panel: unlike the
    # debt_spike gate (which could be checked directly against panel.json's
    # already-computed features with no network access), this fix changes
    # sigma_p's construction itself, which requires re-running the full
    # live pipeline per institution to get new frac_high_entropy values --
    # something this development environment cannot do (no network access
    # to NCES/College Scorecard; see fetch_live_data.py's own module
    # docstring). src/recompute_panel_entropy.py and its matching workflow
    # do this real validation on GitHub Actions, the one environment on
    # this project that can actually reach that data -- run that workflow
    # and check its leave-one-out accuracy comparison before treating this
    # fix as confirmed safe, not just plausible.
    print(f"DIRECTIONAL ENTROPY: debt_spike={debt_spike:.6f} (stored, no longer gates "
          f"anything), frac_high_entropy (new, downside-only)={frac_high_entropy:.4f}, "
          f"frac_high_entropy (old, symmetric, for comparison only)="
          f"{frac_high_entropy_old_symmetric:.4f}")

    feats = InstitutionFeatures(
        unitid=unitid, name=name,
        d_A_trend=d_A_trend, d_A_final=d_A_final, delta_R_final=delta_R_final,
        frac_high_entropy=frac_high_entropy, debt_spike=debt_spike,
        delta_R_trend=delta_R_trend, reserve_adequacy=reserve_adequacy,
        research_ratio=research_ratio, outcome=None,
    )
    if drift_terms:
        # RICD §10.3a read-outs ("sampling protocol v3.md"), each from the
        # posterior mean trajectory, at the end of the window T.
        post = idata.posterior
        cov = post["coverage_t"].mean(dim=["chain", "draw"]).values
        drift = post["enroll_drift"].mean(dim=["chain", "draw"]).values
        resid = post["enroll_step_resid"].mean(dim=["chain", "draw"]).values
        k = min(5, len(cov))
        tail = np.log(np.maximum(cov[-k:], 1e-6))
        g = float(np.polyfit(np.arange(k), tail, 1)[0]) if k >= 2 else 0.0      # slide rate, Prop. 10.3a.1
        c_T = float(cov[-1])
        gap = max(-np.log(max(c_T, 1e-6)), 0.0)
        urgency = 0.0 if g <= 0 else g / (g + gap)                               # collapse urgency
        feats.drift = {
            "enroll_drift": float(drift[-2]) if len(drift) >= 2 else float(drift[-1]),  # drift into year T
            "slide_rate": g,
            "collapse_urgency": float(urgency),
            "coverage_final": c_T,
            "enroll_jump_recent": float(max(0.0, -np.min(resid[-3:]))) if len(resid) else 0.0,
        }
        print(f"DRIFT TERMS: {feats.drift}")
    if allow_gaps:
        # Which years were actually present, for the missing-data features
        # computed by the v2 scripts ("sampling protocol v2.md"). Recorded
        # only; nothing here changes any of the eight features above.
        feats.availability = {
            "years": [int(y) + 1 for y in range(start_year, end_year)],  # fiscal years
            "enrollment": [bool(x) for x in ~np.isnan(series["n_undergrads"])],
            "completion": [bool(x) for x in ~np.isnan(series["completion"])],
            "tuition": [bool(x) for x in ~np.isnan(series["tuition"])],
            "finance": [bool(x) for x in np.asarray(mask, dtype=bool)],
        }
    return feats


def save_live_score(result: dict, path: str = "../docs/data/live_scores.json") -> None:
    """
    Real persistence step -- this is the piece that was missing before
    today: the live pipeline computed a real result but never saved it
    anywhere the public dashboard could read it. This saves/updates
    this institution's result (keyed by unitid, so re-scoring the same
    institution replaces its old entry rather than piling up
    duplicates) in a JSON file inside docs/data/, which GitHub Pages
    already serves alongside the validated panel data -- no separate
    publish step needed, the existing Pages deployment picks it up
    automatically on the next commit.

    Every outcome gets saved here, including "insufficient_data" --
    consistent with this project's own honesty standard: a failed or
    incomplete live-scoring attempt is real information (it shows the
    pipeline was actually run and what happened), not something to
    hide until it succeeds.
    """
    result = dict(result)
    result["scored_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if p.exists():
        try:
            loaded = json.loads(p.read_text())
            if isinstance(loaded, list):
                existing = loaded
        except (json.JSONDecodeError, OSError):
            existing = []  # a real, honest corrupt/missing file -- start fresh rather than crash

    existing = [r for r in existing if r.get("unitid") != result.get("unitid")]
    existing.append(result)
    existing.sort(key=lambda r: r.get("name", ""))
    p.write_text(json.dumps(existing, indent=2))
    print(f"Saved live score for {result.get('name')} ({result.get('unitid')}) to {p}")


# UNITID of the Michigan smoke test run separately by rescore.yml's
# own score_institution.py CLI step -- it never appears in
# score_batch.py's INSTITUTIONS list, so a pruning pass keyed only to
# that list would wrongly delete it as "stale" on every run.
MICHIGAN_SMOKE_TEST_UNITID = "170976"


def prune_stale_live_scores(current_unitids: set, path: str = "../docs/data/live_scores.json") -> None:
    """
    Removes any saved live score whose unitid is neither in
    current_unitids nor the Michigan smoke test. Real cleanup for the
    Youngstown State -> West Virginia University swap (and any future
    swap): without this, a retired institution's old "insufficient_data"
    row sits on the public dashboard forever, because save_live_score
    only ever adds or updates entries, never removes them. Only called
    from score_batch.py's own run, right after it knows its own real
    current list, so it never prunes an institution that simply hasn't
    been (re-)scored yet this run.
    """
    p = Path(path)
    if not p.exists():
        return
    try:
        existing = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return  # a real, honest corrupt/missing file -- nothing to prune
    if not isinstance(existing, list):
        return
    keep_ids = current_unitids | {MICHIGAN_SMOKE_TEST_UNITID}
    pruned = [r for r in existing if r.get("unitid") in keep_ids]
    removed = [r for r in existing if r.get("unitid") not in keep_ids]
    if removed:
        for r in removed:
            print(f"Pruned stale live score: {r.get('name')} ({r.get('unitid')}) -- no longer tracked.")
        p.write_text(json.dumps(pruned, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("unitid")
    parser.add_argument("name", nargs="+")
    parser.add_argument("--sector", default="private", choices=["private", "public", "forprofit"])
    args = parser.parse_args()
    unitid, name = args.unitid, " ".join(args.name)

    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    if unitid in GOVERNANCE_OVERRIDE_UNITIDS:
        result_dict = {
            "unitid": unitid, "name": name, "prediction": "high_risk",
            "method": "governance_override",
        }
    else:
        # NUMBA BACKEND (2026-09-22, Thomas Aquinas investigation
        # follow-up): compile_mode="NUMBA" is now the real production
        # setting here, not just a diagnostic-only override. See
        # compute_features_for_institution's own docstring above for
        # what this changes, and the README's Known Gaps section for
        # the full evidence (20/20 real trials -- 10 across separate
        # job dispatches, 10 across varied random seeds -- all
        # agreeing on frac_high_entropy under this backend, though
        # real rhat<1.01 convergence was not achieved under any
        # tested backend, Numba included).
        features = compute_features_for_institution(
            unitid, name, sector=args.sector, cores=1, compile_mode="NUMBA",
        )
        if features is None:
            result_dict = {"unitid": unitid, "name": name, "prediction": "insufficient_data"}
        else:
            result = clf.classify(features)
            result_dict = {
                "unitid": result.unitid, "name": result.name,
                "prediction": "high_risk" if result.prediction == 1 else "stable",
                "method": result.method, "probability": result.probability,
            }

    print(json.dumps(result_dict, indent=2))
    save_live_score(result_dict)


if __name__ == "__main__":
    main()
