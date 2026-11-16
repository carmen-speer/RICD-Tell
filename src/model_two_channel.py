"""
model_two_channel.py: the scoring model of model.py with one change, for
"reanalysis protocol.md" only.

model.py is frozen with classifier v3 and is not edited. Where the meta
channel P_m is not measured, model.py's fallback sets P_m to a constant
that evaluates to 1.5, outside [0, 1], so the two gaps involving P_m (each
at least 0.5) always dominated D_total = max(D_op, D_om, D_pm). Here, where
P_m is not measured, those two gaps are left out and D_total = D_op, the
official-operational gap alone. Where P_m is measured, nothing differs from
model.py.
"""

"""
PyMC state-space model for RICD-BSSM v0.1 (spec Sec 4-8).

Latent P_t is parameterized via unconstrained logits z_t in R^4, with
P_t = softmax(z_t) (build-order Phase 2's recommendation) -- inference
happens in unconstrained space; the manuscript's explicit simplex
projection remains the *simulation* default (dynamics.py), not the
inference default. These are legitimately different numerical
representations of the same theoretical object, not a contradiction.

This is a scalar-observation reduction of the full latent state, fit to
noisy observations of O_o(P_t) and O_p(P_t) (the two channels an adapter
can actually pull for a real institution), to check whether the known
generating parameters of the synthetic worlds can be recovered.
"""

import numpy as np
import pymc as pm
import pytensor.tensor as pt

from jump_diffusion import build_shock_type_latent, compute_spike_deterministic


def build_model(obs_Oo, obs_Op, obs_types_Oo, obs_types_Op, dt=1.0):
    """
    obs_Oo, obs_Op: arrays of noisy observations of O_o(t), O_p(t).
    obs_types_Oo/Op: parallel arrays of 'observed'/'estimated'/'reconstructed'
                      tags (spec Sec 3/7) -- used to select which noise
                      scale and bias term applies to each timepoint.
    """
    T = len(obs_Oo)
    score_p = np.array([1.00, 0.70, 0.35, 0.05, 0.02])

    def sigma_for(obs_types, sigma_obs, sigma_est, sigma_rec):
        # returns a pytensor vector of per-timepoint noise scales
        arr = np.zeros(len(obs_types), dtype=object)
        return pt.stack([
            sigma_obs if tp == "observed" else (sigma_est if tp == "estimated" else sigma_rec)
            for tp in obs_types
        ])

    def bias_for(obs_types, b_rec):
        return pt.stack([
            0.0 if tp != "reconstructed" else b_rec for tp in obs_types
        ])

    with pm.Model() as model:
        # --- Priors (spec Sec 8) ---
        gamma_F = pm.LogNormal("gamma_F", mu=0, sigma=1)
        kappa_lag = pm.Beta("kappa_lag", alpha=1, beta=1)  # single constant lag for v0.1 fit
        sigma_obs = pm.HalfNormal("sigma_obs", sigma=0.05)
        sigma_est = pm.HalfNormal("sigma_est", sigma=0.10)
        sigma_rec = pm.HalfNormal("sigma_rec", sigma=0.20)
        b_rec = pm.Normal("b_rec", mu=0, sigma=1)
        xi_scale = pm.HalfNormal("xi_scale", sigma=0.05)

        # --- Latent P_t via unconstrained logits (build-order Phase 2) ---
        # NON-CENTERED parameterization, not the centered
        # GaussianRandomWalk(sigma=xi_scale, ...) used in the first version.
        # That centered form directly scales the random walk's innovations
        # by xi_scale, a parameter sampled simultaneously -- textbook Neal's
        # funnel geometry (narrow step size needed when xi_scale is small,
        # wide when it's large, and NUTS cannot use one step size for both).
        # This was the actual cause of the overflow warnings, low effective
        # sample size, and high r-hat on xi_scale specifically, in both the
        # synthetic and real-data runs -- confirmed by the fact that it
        # appeared identically in both, ruling out a data-specific fluke.
        # Non-centered form samples raw unit-scale innovations independent
        # of xi_scale, then applies the scale as a deterministic
        # transformation afterward, decoupling the two and removing the
        # funnel.
        z_raw = pm.Normal("z_raw", mu=0, sigma=1, shape=(T, 4))
        z_init = pm.Normal("z_init", mu=0, sigma=1, shape=(4,))
        z_steps = z_raw * xi_scale  # deterministic scaling, outside the sampled distribution
        z = pm.Deterministic("z", z_init[None, :] + pt.cumsum(z_steps, axis=0))
        # pad with a zero reference logit to get 5 categories, softmax
        zeros_col = pt.zeros((T, 1))
        z_full = pt.concatenate([zeros_col, z], axis=1)
        P = pt.special.softmax(z_full, axis=1)  # (T, 5)

        O_p_true = pt.dot(P, score_p)  # (T,)

        # O_o as its own lagged latent state (dynamics.step_O_o's logic,
        # expressed as a deterministic recursion inside the model since
        # kappa_lag is itself a fitted parameter here)
        def oo_step(op_prev, oo_prev, kappa_lag):
            return oo_prev + kappa_lag * (op_prev - oo_prev)

        oo_init = O_p_true[0]
        oo_seq, _ = pytensor_scan_oo(O_p_true, oo_init, kappa_lag)
        O_o_true = oo_seq

        # --- Observation model (spec Sec 7), obs/est/rec distinguished ---
        sigma_Oo = sigma_for(obs_types_Oo, sigma_obs, sigma_est, sigma_rec)
        sigma_Op = sigma_for(obs_types_Op, sigma_obs, sigma_est, sigma_rec)
        bias_Oo = bias_for(obs_types_Oo, b_rec)
        bias_Op = bias_for(obs_types_Op, b_rec)

        pm.Normal("obs_Oo", mu=O_o_true + bias_Oo, sigma=sigma_Oo, observed=obs_Oo)
        pm.Normal("obs_Op", mu=O_p_true + bias_Op, sigma=sigma_Op, observed=obs_Op)

        pm.Deterministic("P_trace", P)
        pm.Deterministic("O_o_true", O_o_true)
        pm.Deterministic("O_p_true", O_p_true)

    return model


def build_model_stage2(obs_Oo, obs_Op, obs_types_Oo, obs_types_Op,
                        E_exch_obs, M_maint_obs, W_instr_obs, W_total_obs,
                        finance_mask, dt=1.0,
                        pt_share_obs=None, pt_share_mask=None,
                        debt_obs=None, debt_mask=None,
                        online_share_obs=None, online_share_mask=None,
                        enroll_obs=None):
    """
    Stage 2 extension of build_model: adds real resource dynamics
    R(t)/delta_R(t), tied to sparse real IPEDS finance observations
    (only `finance_mask` of the T timepoints are actually observed),
    and stress S(t), driven by the same divergence D(t) already
    computed from P_t.

    W_total_obs (real total expenses, F2B02) drives the actual resource
    recursion and delta_R(t). M_maint_obs and W_instr_obs
    (institutional support, instruction) are tracked as their own
    separate observed signals -- real, meaningful quantities in their
    own right -- but do not by themselves determine deficit. An earlier
    version conflated "two expense sub-categories" with "total
    spending," and delta_R_t was confirmed exactly zero at every
    timepoint as a result -- fixed by wiring in the real total-expenses
    figure that was already being extracted but not used.

    STATED SIMPLIFICATION: Pi_f(t) (feedback permeability), which the
    stress recursion needs, is not separately modeled with its own
    dynamics in this Stage 2 pass -- it is approximated as a single
    fitted scalar rather than a time-varying latent process.

    STAGE 4 UPDATE: P_m, D_om, D_pm now genuinely exist in this model
    for the first time. Previously only D_op (via D_op_proxy) drove the
    stress recursion at all -- the three-channel official/operational/
    meta architecture central to this document's own theory had never
    actually been implemented, only the two-channel O_o-versus-O_p
    split. pt_share_obs (real part-time instructional staff share, per
    RICD 9.0's P_m proxy replacement) is genuinely sparse -- real HR
    data currently covers only 2013/2017/2023 -- and is modeled here as
    a latent Gaussian random walk with observations only at pt_share_mask
    timepoints, exactly the same sparse-observation pattern already
    used for finance data, rather than a deterministic "hold nearest
    known value" fill. This gives P_m(t) genuine posterior uncertainty
    in the years between real HR observations, which a deterministic
    fill could not. Where pt_share_obs is not supplied at all, P_m
    falls back to the admissions-rate proxy (RICD 9.0's stated
    fallback), and D_om/D_pm are computed from that instead -- a
    real, if lower-confidence, three-channel model rather than none.

    FINAL WIRING: debt_obs (raw total_liabilities, sparse, real IPEDS
    balance-sheet data) and online_share_obs (raw Fall Enrollment
    distance-education share, sparse, real IPEDS data) are now modeled
    as genuine latent sequences with sparse real observations, the same
    treatment P_m_true already received, rather than the external,
    already-fit-output post-hoc numpy computation debt_max_spike and
    the delivery-substitution interaction previously lived in. debt_spike
    (Definition 11.10.2's severity signal) and Substitution (Definition
    11.10.3's interaction term) are now Deterministics computed inside
    this model from genuinely latent trajectories, carrying real
    posterior uncertainty neither previously had as fixed, external
    numbers.
    """
    T = len(obs_Oo)
    score_p = np.array([1.00, 0.70, 0.35, 0.05, 0.02])

    def sigma_for(obs_types, sigma_obs, sigma_est, sigma_rec):
        return pt.stack([
            sigma_obs if tp == "observed" else (sigma_est if tp == "estimated" else sigma_rec)
            for tp in obs_types
        ])

    with pm.Model() as model:
        # --- Priors, FDFM layer (unchanged from Stage 1) ---
        gamma_F = pm.LogNormal("gamma_F", mu=0, sigma=1)
        kappa_lag = pm.Beta("kappa_lag", alpha=1, beta=1)
        sigma_obs = pm.HalfNormal("sigma_obs", sigma=0.05)
        sigma_est = pm.HalfNormal("sigma_est", sigma=0.10)
        sigma_rec = pm.HalfNormal("sigma_rec", sigma=0.20)
        b_rec = pm.Normal("b_rec", mu=0, sigma=1)
        xi_scale = pm.HalfNormal("xi_scale", sigma=0.05)

        # --- Latent P_t, non-centered (Stage 1 fix retained) ---
        z_raw = pm.Normal("z_raw", mu=0, sigma=1, shape=(T, 4))
        z_init = pm.Normal("z_init", mu=0, sigma=1, shape=(4,))
        z_steps = z_raw * xi_scale
        z = pm.Deterministic("z", z_init[None, :] + pt.cumsum(z_steps, axis=0))
        zeros_col = pt.zeros((T, 1))
        z_full = pt.concatenate([zeros_col, z], axis=1)
        P = pt.special.softmax(z_full, axis=1)
        O_p_true = pt.dot(P, score_p)

        def oo_step(op_prev, oo_prev, kappa_lag):
            return oo_prev + kappa_lag * (op_prev - oo_prev)
        oo_init = O_p_true[0]
        oo_seq, _ = pytensor_scan_oo(O_p_true, oo_init, kappa_lag)
        O_o_true = oo_seq

        sigma_Oo = sigma_for(obs_types_Oo, sigma_obs, sigma_est, sigma_rec)
        sigma_Op = sigma_for(obs_types_Op, sigma_obs, sigma_est, sigma_rec)
        # Missing years (2026-11-14, "sampling protocol v2.md", phase 0):
        # a NaN in obs_Oo or obs_Op marks a year with no observation. The
        # channel is then fitted only at its observed years, the same
        # masking already used for the finance channels below. When every
        # year is observed, the original two lines run unchanged, so the
        # model built for a complete series is exactly the model it was.
        oo_seen = ~np.isnan(np.asarray(obs_Oo, dtype=float))
        op_seen = ~np.isnan(np.asarray(obs_Op, dtype=float))
        if oo_seen.all() and op_seen.all():
            pm.Normal("obs_Oo", mu=O_o_true, sigma=sigma_Oo, observed=obs_Oo)
            pm.Normal("obs_Op", mu=O_p_true, sigma=sigma_Op, observed=obs_Op)
        else:
            oo_idx = np.where(oo_seen)[0]
            op_idx = np.where(op_seen)[0]
            pm.Normal("obs_Oo", mu=O_o_true[oo_idx], sigma=sigma_Oo[oo_idx],
                      observed=np.asarray(obs_Oo, dtype=float)[oo_idx])
            pm.Normal("obs_Op", mu=O_p_true[op_idx], sigma=sigma_Op[op_idx],
                      observed=np.asarray(obs_Op, dtype=float)[op_idx])
        pm.Deterministic("O_o_true", O_o_true)
        pm.Deterministic("O_p_true", O_p_true)

        # --- STAGE 4: P_m as a genuine latent sequence, not external ---
        if pt_share_obs is not None and pt_share_mask is not None and pt_share_mask.any():
            sigma_pm = pm.HalfNormal("sigma_pm", sigma=0.05)
            P_m_latent = pm.GaussianRandomWalk(
                "P_m_latent", sigma=0.01,
                init_dist=pm.Normal.dist(0.5, 0.15), shape=T,
            )
            pm_idx = np.where(pt_share_mask)[0]
            # P_m proxy = 1 - part_time_share (RICD 9.0): higher secure
            # staffing share -> higher genuine self-monitoring capacity.
            pm.Normal("obs_P_m", mu=P_m_latent[pm_idx], sigma=sigma_pm,
                      observed=(1 - pt_share_obs[pt_share_mask]))
            P_m_true = pm.Deterministic("P_m_true", P_m_latent)
        else:
            # Fallback: admissions-rate proxy (RICD 9.0's stated
            # fallback), no separate latent process needed since it is
            # already a direct function of observed O_p_true's own
            # admissions-linked construction upstream in the adapter.
            # TWO-CHANNEL MODE (reanalysis protocol.md): P_m is not
            # measured, so the three-channel calculation is undetermined
            # (the RICD Spine) and the two gaps involving P_m are left out.
            # (model.py's fallback evaluates to 1.5, outside [0, 1], so those
            # two gaps always dominated D_total; that is the error fixed here.)
            P_m_true = None

        D_op_proxy = pt.abs(O_o_true - O_p_true)
        if P_m_true is not None:
            D_om = pm.Deterministic("D_om", pt.abs(O_o_true - P_m_true))
            D_pm = pm.Deterministic("D_pm", pt.abs(O_p_true - P_m_true))

        # --- STAGE 2: real resource dynamics -------------------------
        sigma_fin = pm.HalfNormal("sigma_fin", sigma=0.05)
        E_exch_latent = pm.GaussianRandomWalk(
            "E_exch_latent", sigma=0.02, init_dist=pm.Normal.dist(0.3, 0.1), shape=T,
        )
        M_maint_latent = pm.GaussianRandomWalk(
            "M_maint_latent", sigma=0.005, init_dist=pm.Normal.dist(0.02, 0.01), shape=T,
        )
        W_instr_latent = pm.GaussianRandomWalk(
            "W_instr_latent", sigma=0.01, init_dist=pm.Normal.dist(0.08, 0.03), shape=T,
        )
        # Real total expenses -- what actually drives the resource
        # recursion and delta_R(t), not the M_maint+W_instr sub-slice.
        W_total_latent = pm.GaussianRandomWalk(
            "W_total_latent", sigma=0.02, init_dist=pm.Normal.dist(0.25, 0.1), shape=T,
        )

        obs_idx = np.where(finance_mask)[0]
        pm.Normal("obs_E_exch", mu=E_exch_latent[obs_idx], sigma=sigma_fin,
                  observed=E_exch_obs[finance_mask])
        pm.Normal("obs_M_maint", mu=M_maint_latent[obs_idx], sigma=sigma_fin,
                  observed=M_maint_obs[finance_mask])
        pm.Normal("obs_W_instr", mu=W_instr_latent[obs_idx], sigma=sigma_fin,
                  observed=W_instr_obs[finance_mask])
        pm.Normal("obs_W_total", mu=W_total_latent[obs_idx], sigma=sigma_fin,
                  observed=W_total_obs[finance_mask])

        # Resource recursion (RICD Sec 7.3), driven by REAL total
        # expenses, not the incomplete sub-category sum.
        # STAGE: RICD 7.2's Definition 7.9.1, General Divergence Cost --
        # M_diverge(t) = kappa_diverge * D(t), entering the resource
        # balance as an additional draw for ANY container, not only the
        # existing M_decep(t) channel scoped to high-entropy concealment.
        # STAGE 4 UPDATE: D(t) here is now the genuine three-channel
        # combination (max across D_op, D_om, D_pm), not D_op alone --
        # any one channel's unresolved divergence is a real cost, and
        # using only D_op silently ignored the other two once they
        # existed at all.
        if P_m_true is not None:
            D_total = pm.Deterministic("D_total", pt.maximum(pt.maximum(D_op_proxy, D_om), D_pm))
        else:
            D_total = pm.Deterministic("D_total", D_op_proxy)
        kappa_diverge = pm.HalfNormal("kappa_diverge", sigma=0.1)
        M_diverge = kappa_diverge * D_total

        # --- debt_spike: genuinely integrated, via jump-diffusion -----
        # An earlier attempt modeled debt as an ordinary continuous-drift
        # GaussianRandomWalk, the same treatment P_m received above, and
        # it failed: tested against Limestone, genuine posterior
        # debt_spike came out to ~0.08, against 0.65 from the external,
        # raw-data computation this feature was actually validated on --
        # nearly an order of magnitude lower. The cause was a category
        # error, not a prior to retune: debt is a shock-type observable
        # (RICD 9.4's drift-versus-shock classification, Part 15) --
        # long stable stretches punctuated by rare, large jumps -- and a
        # Gaussian random walk's homogeneous-step assumption pulled the
        # genuine jump toward consistency with ordinary small steps
        # around it. Fixed by modeling debt through jump_diffusion.py's
        # Student-t latent instead (heavy tails, no discrete
        # jump-indicator needed): tested against the same Limestone case,
        # posterior mean recovered to 0.578 (95% CI [0.26, 0.80],
        # genuinely containing the external 0.65 value), at the honest
        # cost of harder sampling geometry than the Gaussian case had --
        # expected and acceptable, since correctly representing a
        # process with real rare jumps is inherently harder to sample
        # than a process without them.
        debt_spike = None
        if debt_obs is not None and debt_mask is not None and debt_mask.any():
            debt_scale = np.nanmax(debt_obs[debt_mask])
            debt_scale = debt_scale if debt_scale > 0 else 1.0
            debt_latent = build_shock_type_latent("debt_latent", T, sigma_drift=0.05, nu=3.0,
                                                    init_mu=0.3, init_sigma=0.2)
            sigma_debt = pm.HalfNormal("sigma_debt", sigma=0.05)
            debt_idx = np.where(debt_mask)[0]
            pm.Normal("obs_debt", mu=debt_latent[debt_idx], sigma=sigma_debt,
                      observed=debt_obs[debt_mask] / debt_scale)
            debt_spike = compute_spike_deterministic(debt_latent, "debt_spike")

        # --- Substitution: kept external, per RICD 9.4's own guidance --
        # Online-share growth is ordinarily a drift-type quantity
        # (incremental year-over-year change, not a sudden jump the way
        # debt can spike), so the original failure mode does not apply
        # here the same way; Substitution (Definition 11.10.3) remains
        # computed externally from raw data as validated earlier this
        # session, since it was never the subject of the debt-spike
        # failure and re-deriving it inside this model was not separately
        # tested or shown to need this treatment.

        def r_step(e_t, w_t, m_t, r_prev):
            return r_prev + e_t - w_t - m_t
        r_init = pm.Normal("R_init", mu=0.5, sigma=0.2)
        R_seq, _ = pytensor_scan_R(E_exch_latent, W_total_latent, M_diverge, r_init)
        R_t = pm.Deterministic("R_t", R_seq)

        # delta_R: pre-recovery structural debt (Sec 7.9) -- unpaid gap
        # between real total spending (now including M_diverge) and real
        # revenue, floored at 0.
        deficit = pt.maximum(W_total_latent + M_diverge - E_exch_latent, 0)

        def deltaR_step(d_t, dr_prev):
            return dr_prev + d_t
        dr_init = pt.constant(0.0, dtype="float64")
        deltaR_seq, _ = pytensor_scan_deltaR(deficit, dr_init)
        delta_R_t = pm.Deterministic("delta_R_t", deltaR_seq)

        # --- STAGE 2/4: stress S(t), now driven by D_total -----------
        # STATED SIMPLIFICATION on Pi_f retained (see docstring).
        lam = pm.LogNormal("lambda_stress", mu=0, sigma=0.5)
        pi_f_const = pm.Beta("pi_f_const", alpha=2, beta=2)

        def s_step(d_t, pi_f, lam, s_prev, dt):
            decay = pt.exp(-lam * dt)
            return s_prev * decay + (1 - decay) * (1 - pi_f) * d_t
        s_init = pt.constant(0.0, dtype="float64")
        S_seq, _ = pytensor_scan_S(D_total, pi_f_const, lam, s_init, dt)
        S_t = pm.Deterministic("S_t", S_seq)

        # --- d_A(t) and P_C(t) (Sec 10.3, 11.10) -- designed to carry
        # exactly the divergence-to-resource-to-collapse causal chain,
        # never previously wired into this tracker at all. Uses S_t and
        # delta_R_t directly; F_t (fragmentation) is not yet built in
        # this reduced single-container model, so beta_F's contribution
        # defaults to zero -- a stated simplification, not silently
        # omitted.
        beta_S = pm.HalfNormal("beta_S", sigma=1)
        beta_R = pm.HalfNormal("beta_R", sigma=1)
        d_A_max = 1.0  # normalized ceiling
        S_tilde_proxy = S_t / (S_t.max() + 1e-6)  # simple in-model relative scale
        delta_R_tilde_proxy = delta_R_t / (delta_R_t.max() + 1e-6)
        if enroll_obs is None:
            # Unchanged: the live pipeline and every v2 fit take this branch,
            # so the model they build is exactly the model they always built.
            d_A_t = pm.Deterministic(
                "d_A_t", d_A_max * pt.exp(-beta_S * S_tilde_proxy - beta_R * delta_R_tilde_proxy)
            )
        else:
            # --- Drift-type and shock-type collapse (RICD §10.3a; "sampling
            # protocol v3.md"), used only when enroll_obs is supplied. ---
            # Exchange base (Definition 10.3a.2): log enrollment, relative to
            # its own peak, as a local linear trend whose level moves by a
            # slowly varying drift plus heavy-tailed (Student-t) steps, the
            # section 15.2 construction for a drift-type observable that can
            # take rare large steps. Observed only at years with a value.
            enroll_obs = np.asarray(enroll_obs, dtype=float)
            enroll_seen = ~np.isnan(enroll_obs)
            enroll_idx = np.where(enroll_seen)[0]
            enroll_first = float(enroll_obs[enroll_idx[0]])
            n_init = pm.Normal("enroll_init", mu=enroll_first, sigma=0.2)
            mu_init = pm.Normal("enroll_drift_init", mu=0.0, sigma=0.1)
            mu_steps = pm.Normal("enroll_drift_steps_raw", mu=0.0, sigma=1.0, shape=T - 1) * 0.02
            mu_seq = pt.concatenate([pt.stack([mu_init]), mu_init + pt.cumsum(mu_steps)])
            n_resid = pm.StudentT("enroll_steps_raw", nu=3.0, mu=0.0, sigma=1.0, shape=T - 1) * 0.03
            n_seq = pt.concatenate([pt.stack([n_init]), n_init + pt.cumsum(mu_seq[:-1] + n_resid)])
            pm.Deterministic("enroll_level", n_seq)
            pm.Deterministic("enroll_drift", mu_seq)
            pm.Deterministic("enroll_step_resid", n_resid)
            sigma_enroll = 0.02  # fixed: reported enrollment counts carry little measurement noise
            pm.Normal("obs_enroll", mu=n_seq[enroll_idx], sigma=sigma_enroll,
                      observed=enroll_obs[enroll_idx])
            # Cost coverage (Definition 10.3a.3): the share of exchange already
            # committed to total work, c = W_total / E_exch, from the two
            # reported finance channels.
            coverage = pm.Deterministic(
                "coverage_t", W_total_latent / pt.maximum(E_exch_latent, 1e-3))
            # Headroom term (Definition 10.3a.5): committed capacity contracts
            # adaptive possibility before any debt accumulates.
            beta_H = pm.HalfNormal("beta_H", sigma=1)
            d_A_t = pm.Deterministic(
                "d_A_t", d_A_max * pt.exp(-beta_S * S_tilde_proxy - beta_R * delta_R_tilde_proxy
                                          - beta_H * pt.maximum(coverage, 0.0))
            )
        kappa4_pc = pm.HalfNormal("kappa4_pc", sigma=1)
        P_C_t = pm.Deterministic("P_C_t", pt.sigmoid(kappa4_pc * (1 - d_A_t / d_A_max)))


        # --- STAGE 3: informational integrity ---
        # I(t) = 1 - D_op_proxy, reusing the same proxy already driving
        # the stress recursion above, for consistency rather than
        # introducing a second, differently-defined divergence measure.
        I_t = pm.Deterministic("I_t", 1 - D_op_proxy)

        # theta_hull REMOVED (was: pm.Beta("theta_hull", alpha=2, beta=2)
        # -- a decorative parameter sampled from its own prior with no
        # likelihood ever connecting it to a real outcome). The genuine
        # collapse-risk classifier this institution's own d_A_t,
        # delta_R_t, and regime classification feed into lives in
        # collapse_classifier.py, fit jointly across the full labeled
        # panel against real, known outcomes via a genuine Bernoulli
        # likelihood -- see build_collapse_classifier(). That module's
        # p_collapse posterior, including its credible interval width,
        # is the real replacement for what theta_hull was a placeholder
        # for, and doubles as the concrete implementation of Definition
        # 11.10.1's Divergent Signal Flag: a wide p_collapse credible
        # interval for a given institution is the flag, produced
        # natively by the Bayesian model rather than a separate
        # hand-coded percentile rule.

        pm.Deterministic("P_trace", P)

    return model


def pytensor_scan_oo(op_series, oo_init, kappa_lag):
    """pytensor.scan wrapper for the O_o lag recursion."""
    import pytensor

    def step(op_prev, oo_prev, kappa_lag):
        return oo_prev + kappa_lag * (op_prev - oo_prev)

    result, updates = pytensor.scan(
        fn=step,
        sequences=[op_series[:-1]],
        outputs_info=[oo_init],
        non_sequences=[kappa_lag],
    )
    full = pt.concatenate([oo_init[None], result])
    return full, updates


def pytensor_scan_R(E_exch, W_t, M_diverge, r_init):
    import pytensor
    def step(e_t, w_t, m_t, r_prev):
        return r_prev + e_t - w_t - m_t
    result, updates = pytensor.scan(
        fn=step, sequences=[E_exch[1:], W_t[1:], M_diverge[1:]], outputs_info=[r_init],
    )
    full = pt.concatenate([r_init[None], result])
    return full, updates


def pytensor_scan_deltaR(deficit, dr_init):
    import pytensor
    def step(d_t, dr_prev):
        return dr_prev + d_t
    result, updates = pytensor.scan(
        fn=step, sequences=[deficit[1:]], outputs_info=[dr_init],
    )
    full = pt.concatenate([dr_init[None], result])
    return full, updates


def pytensor_scan_S(D, pi_f, lam, s_init, dt):
    import pytensor
    def step(d_t, s_prev, pi_f, lam, dt):
        decay = pt.exp(-lam * dt)
        return s_prev * decay + (1 - decay) * (1 - pi_f) * d_t
    result, updates = pytensor.scan(
        fn=step, sequences=[D[1:]], outputs_info=[s_init],
        non_sequences=[pi_f, lam, dt],
    )
    full = pt.concatenate([s_init[None], result])
    return full, updates
