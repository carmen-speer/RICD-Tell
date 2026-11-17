"""
Diagnostic-only variant of build_model_stage2 (model.py), built to test
one specific hypothesis about item 6's finding: that `sigma_fin` -- a
single shared observation-noise scale used as the likelihood sigma for
FOUR separate reported-financials channels at once (E_exch, M_maint,
W_instr, W_total), each matched against its own independent
GaussianRandomWalk latent -- is the real cause of Thomas Aquinas's worst
rhat (1.1418, identical across 2 independent runs, by a wide margin over
every other free parameter; see diagnose_thomas_aquinas_param_rhat.py's
own run log).

The hypothesis, stated plainly: forcing one shared sigma_fin to
reconcile four financial-reporting channels that plausibly have
genuinely different real noise levels (reported exchange revenue,
maintenance spend, instructional spend, and total spend are different
line items with different reporting behavior) requires NUTS to find a
single compromise value satisfying four different constraints at once --
a real, plausible source of poor mixing, and the same family of problem
(a shared scale jointly constrained by multiple downstream quantities)
as the already-fixed z_raw/xi_scale funnel, though a different specific
geometry (a shared *observation-noise* scale across four likelihoods,
not a process's own *step* scale).

This file changes exactly one thing relative to model.py's
build_model_stage2: sigma_fin becomes four independent HalfNormal(0.05)
priors (sigma_fin_exch, sigma_fin_maint, sigma_fin_instr,
sigma_fin_total), one per observation channel, instead of one shared
value. Every other line is unchanged from model.py, copied verbatim --
this is deliberate: an unconfirmed hypothesis gets tested in an isolated
copy first, exactly as the project's own documentation standard
requires, and does not touch the production model.py or the live
scoring pipeline until (and unless) diagnose_sigma_fin_split.py actually
confirms the four new sigmas converge and the four latent variables'
rhat drops along with them.

If this file and model.py's build_model_stage2 ever drift apart for any
reason other than this one deliberate change, that is itself a bug in
this diagnostic, not a feature -- re-sync by re-copying build_model_stage2
and re-applying only the sigma_fin split below.
"""

import numpy as np
import pymc as pm
import pytensor.tensor as pt

from jump_diffusion import build_shock_type_latent, compute_spike_deterministic
from model import pytensor_scan_oo, pytensor_scan_R, pytensor_scan_deltaR, pytensor_scan_S


def build_model_stage2_split_sigma_fin(
        obs_Oo, obs_Op, obs_types_Oo, obs_types_Op,
        E_exch_obs, M_maint_obs, W_instr_obs, W_total_obs,
        finance_mask, dt=1.0,
        pt_share_obs=None, pt_share_mask=None,
        debt_obs=None, debt_mask=None,
        online_share_obs=None, online_share_mask=None):
    """
    Identical to model.py's build_model_stage2 except for the STAGE 2
    block below, where sigma_fin (one shared HalfNormal(0.05)) is
    replaced by four independent HalfNormal(0.05) priors, one per
    financial observation channel. See this module's own docstring for
    why. Every other section is copied verbatim from model.py -- do not
    edit anything outside the marked block without also updating
    model.py's real build_model_stage2, or the two will silently diverge.
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
        pm.Normal("obs_Oo", mu=O_o_true, sigma=sigma_Oo, observed=obs_Oo)
        pm.Normal("obs_Op", mu=O_p_true, sigma=sigma_Op, observed=obs_Op)
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
            pm.Normal("obs_P_m", mu=P_m_latent[pm_idx], sigma=sigma_pm,
                      observed=(1 - pt_share_obs[pt_share_mask]))
            P_m_true = pm.Deterministic("P_m_true", P_m_latent)
        else:
            P_m_true = pm.Deterministic("P_m_true", 1 - O_p_true * 0 + 0.5)

        D_op_proxy = pt.abs(O_o_true - O_p_true)
        D_om = pm.Deterministic("D_om", pt.abs(O_o_true - P_m_true))
        D_pm = pm.Deterministic("D_pm", pt.abs(O_p_true - P_m_true))

        # === STAGE 2: real resource dynamics -- THE ONE CHANGE =========
        # sigma_fin split into four independent per-channel scales
        # instead of one shared value. This is the entire, only
        # difference from model.py's build_model_stage2.
        sigma_fin_exch = pm.HalfNormal("sigma_fin_exch", sigma=0.05)
        sigma_fin_maint = pm.HalfNormal("sigma_fin_maint", sigma=0.05)
        sigma_fin_instr = pm.HalfNormal("sigma_fin_instr", sigma=0.05)
        sigma_fin_total = pm.HalfNormal("sigma_fin_total", sigma=0.05)
        E_exch_latent = pm.GaussianRandomWalk(
            "E_exch_latent", sigma=0.02, init_dist=pm.Normal.dist(0.3, 0.1), shape=T,
        )
        M_maint_latent = pm.GaussianRandomWalk(
            "M_maint_latent", sigma=0.005, init_dist=pm.Normal.dist(0.02, 0.01), shape=T,
        )
        W_instr_latent = pm.GaussianRandomWalk(
            "W_instr_latent", sigma=0.01, init_dist=pm.Normal.dist(0.08, 0.03), shape=T,
        )
        W_total_latent = pm.GaussianRandomWalk(
            "W_total_latent", sigma=0.02, init_dist=pm.Normal.dist(0.25, 0.1), shape=T,
        )

        obs_idx = np.where(finance_mask)[0]
        pm.Normal("obs_E_exch", mu=E_exch_latent[obs_idx], sigma=sigma_fin_exch,
                  observed=E_exch_obs[finance_mask])
        pm.Normal("obs_M_maint", mu=M_maint_latent[obs_idx], sigma=sigma_fin_maint,
                  observed=M_maint_obs[finance_mask])
        pm.Normal("obs_W_instr", mu=W_instr_latent[obs_idx], sigma=sigma_fin_instr,
                  observed=W_instr_obs[finance_mask])
        pm.Normal("obs_W_total", mu=W_total_latent[obs_idx], sigma=sigma_fin_total,
                  observed=W_total_obs[finance_mask])
        # === END OF THE ONE CHANGE ======================================

        D_total = pm.Deterministic("D_total", pt.maximum(pt.maximum(D_op_proxy, D_om), D_pm))
        kappa_diverge = pm.HalfNormal("kappa_diverge", sigma=0.1)
        M_diverge = kappa_diverge * D_total

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

        def r_step(e_t, w_t, m_t, r_prev):
            return r_prev + e_t - w_t - m_t
        r_init = pm.Normal("R_init", mu=0.5, sigma=0.2)
        R_seq, _ = pytensor_scan_R(E_exch_latent, W_total_latent, M_diverge, r_init)
        R_t = pm.Deterministic("R_t", R_seq)

        deficit = pt.maximum(W_total_latent + M_diverge - E_exch_latent, 0)

        def deltaR_step(d_t, dr_prev):
            return dr_prev + d_t
        dr_init = pt.constant(0.0, dtype="float64")
        deltaR_seq, _ = pytensor_scan_deltaR(deficit, dr_init)
        delta_R_t = pm.Deterministic("delta_R_t", deltaR_seq)

        lam = pm.LogNormal("lambda_stress", mu=0, sigma=0.5)
        pi_f_const = pm.Beta("pi_f_const", alpha=2, beta=2)

        def s_step(d_t, pi_f, lam, s_prev, dt):
            decay = pt.exp(-lam * dt)
            return s_prev * decay + (1 - decay) * (1 - pi_f) * d_t
        s_init = pt.constant(0.0, dtype="float64")
        S_seq, _ = pytensor_scan_S(D_total, pi_f_const, lam, s_init, dt)
        S_t = pm.Deterministic("S_t", S_seq)

        beta_S = pm.HalfNormal("beta_S", sigma=1)
        beta_R = pm.HalfNormal("beta_R", sigma=1)
        d_A_max = 1.0
        S_tilde_proxy = S_t / (S_t.max() + 1e-6)
        delta_R_tilde_proxy = delta_R_t / (delta_R_t.max() + 1e-6)
        d_A_t = pm.Deterministic(
            "d_A_t", d_A_max * pt.exp(-beta_S * S_tilde_proxy - beta_R * delta_R_tilde_proxy)
        )
        kappa4_pc = pm.HalfNormal("kappa4_pc", sigma=1)
        P_C_t = pm.Deterministic("P_C_t", pt.sigmoid(kappa4_pc * (1 - d_A_t / d_A_max)))

        I_t = pm.Deterministic("I_t", 1 - D_op_proxy)

        pm.Deterministic("P_trace", P)

    return model
