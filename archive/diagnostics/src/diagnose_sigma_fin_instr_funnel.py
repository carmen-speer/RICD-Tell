"""
Item 6, continued: diagnose_sigma_fin_split.py's real result showed
splitting sigma_fin fixed E_exch cleanly and substantially improved
M_maint and W_total, but left W_instr essentially unchanged --
sigma_fin_instr became the single worst parameter in the whole model
(rhat 1.0983). diagnose_thomas_aquinas_finance_data.py's real result
then rejected the first follow-up hypothesis (that W_instr's real data
is unusually volatile relative to its fixed GaussianRandomWalk sigma):
W_instr actually has the SMALLEST year-over-year-delta/sigma ratio of
all four channels (mean 0.13x, max 0.33x), not the largest, and the
relationship runs backwards from what that hypothesis predicted --
E_exch has the largest ratio (mean 1.18x, max 3.13x) and converged
cleanly; W_instr has the smallest and didn't improve at all.

That inverse, monotonic pattern (more real volatility -> better
post-split convergence, across all four channels) points to a different,
specific hypothesis: Thomas Aquinas's real instructional-spending series
is unusually SMOOTH (confirmed directly -- nearly monotonic, smallest
observed deltas of all four channels), so the real residual noise around
its trend is small, which means sigma_fin_instr -- a free HalfNormal(0.05)
observation-noise scale -- may be getting pulled very close to its own
lower boundary at zero to fit that smooth data well. A HalfNormal
parameter whose true posterior mass sits hard against zero is a
well-documented source of poor NUTS mixing (related to, but geometrically
distinct from, the xi_scale funnel already fixed elsewhere in this
model, where a *step*-scale being fit simultaneously with the process
using it caused the same family of difficulty).

This script builds the same split-sigma model variant
(model_variant_split_sigma_fin.py, already used and unmodified by
diagnose_sigma_fin_split.py -- not touched here either) directly against
Thomas Aquinas's real live data, samples once, and prints the RAW
POSTERIOR of all four sigma_fin_* parameters side by side -- mean, sd,
min, max, and the 2.5/50/97.5 percentiles -- so we can see directly
whether sigma_fin_instr's posterior actually sits close to zero relative
to the other three, rather than inferring it indirectly from rhat alone.
It also prints a simple, direct funnel check: the correlation, across
all post-warmup draws, between each channel's sigma_fin_* draw and that
same draw's own W_instr_latent (or the matching latent's) total path
variance -- a classic funnel signature is a strong positive correlation
(small sigma draws paired with a tightly-clustered, low-variance latent
path; large sigma draws paired with a loosely-wandering one).

Does not touch model.py, model_variant_split_sigma_fin.py, or the live
pipeline -- reads the real data and samples once, using the same
settings as every other diagnostic in this investigation.
"""
from __future__ import annotations

import datetime

import numpy as np
import pymc as pm

import fetch_live_data as fld
import real_adapter as ra
import model_variant_split_sigma_fin as variant

UNITID = "124292"
NAME = "Thomas Aquinas College"
SECTOR = "private"
START_YEAR = 2013

SETTINGS = dict(
    tune=800, chains=4, cores=1, target_accept=0.95,
    compile_kwargs={"mode": "NUMBA"}, progressbar=False, random_seed=7,
)


def summarize(name, draws):
    flat = np.asarray(draws).flatten()
    print(f"  {name}: mean={flat.mean():.5f}, sd={flat.std():.5f}, "
          f"min={flat.min():.5f}, max={flat.max():.5f}, "
          f"p2.5={np.percentile(flat, 2.5):.5f}, p50={np.percentile(flat, 50):.5f}, "
          f"p97.5={np.percentile(flat, 97.5):.5f}")
    return flat


def main():
    end_year = datetime.date.today().year - 2
    window_years = [f"{y}-{str(y + 1)[2:]}" for y in range(START_YEAR, end_year)]

    print("=" * 70)
    print(f"SIGMA_FIN_INSTR FUNNEL CHECK: {NAME} ({UNITID})")
    print("=" * 70)
    print("Building real data and the split-sigma model variant, sampling once "
          "at production-diagnostic settings, then printing the raw posterior "
          "of all four sigma_fin_* parameters side by side.")

    series = fld.build_live_series(UNITID, START_YEAR, end_year, sector=SECTOR)
    if series is None:
        print("INSUFFICIENT ENROLLMENT DATA -- cannot proceed.")
        return
    O_o_real, O_p_real = ra.compute_O_o_O_p(series)

    dest_base = f"/tmp/ipeds_live/{UNITID}"
    for year in range(START_YEAR, end_year):
        fld.download_ipeds_finance_bulk(year, dest_dir=dest_base, sector=SECTOR)
    E_exch, M_maint, W_instr, W_total, mask, scale = fld.parse_live_finance(
        UNITID, window_years, dest_base, sector=SECTOR)
    if mask.sum() < 3:
        print("INSUFFICIENT PARSED FINANCE DATA -- cannot proceed.")
        return

    types = ["observed"] * len(O_o_real)
    pymc_model = variant.build_model_stage2_split_sigma_fin(
        O_o_real, O_p_real, types, types, E_exch, M_maint, W_instr, W_total, mask)

    with pymc_model:
        idata = pm.sample(800, **SETTINGS)

    print("\nRAW POSTERIOR, all four sigma_fin_* parameters (HalfNormal(0.05) prior "
          "on each; prior's own std is 0.05, for scale):")
    posts = {}
    for var in ["sigma_fin_exch", "sigma_fin_maint", "sigma_fin_instr", "sigma_fin_total"]:
        posts[var] = summarize(var, idata.posterior[var].values)

    print("\nFUNNEL CHECK: correlation between each channel's sigma_fin_* draw and "
          "that channel's own latent path variance in the same draw (high positive "
          "correlation = classic funnel signature -- small sigma paired with a "
          "tightly-clustered latent, large sigma paired with a loosely-wandering one):")
    latent_names = {
        "sigma_fin_exch": "E_exch_latent", "sigma_fin_maint": "M_maint_latent",
        "sigma_fin_instr": "W_instr_latent", "sigma_fin_total": "W_total_latent",
    }
    for sigma_var, latent_var in latent_names.items():
        latent_draws = idata.posterior[latent_var].values  # (chain, draw, T)
        chains, draws, T = latent_draws.shape
        path_var = latent_draws.reshape(chains * draws, T).var(axis=1)
        sigma_flat = posts[sigma_var]
        corr = np.corrcoef(sigma_flat, path_var)[0, 1]
        print(f"  {sigma_var} vs {latent_var} path variance: correlation={corr:.3f}")

    print("\n" + "=" * 70)
    print("If sigma_fin_instr's posterior (mean/p50 especially) sits noticeably "
          "closer to zero than the other three, AND its correlation with "
          "W_instr_latent's path variance is the strongest of the four, that's real, "
          "direct confirmation of the near-boundary/funnel hypothesis -- the concrete "
          "fix would then be a tighter or differently-shaped prior on sigma_fin_instr "
          "specifically (or a non-centered reparameterization of W_instr_latent itself, "
          "the same family of fix already used for z_raw/xi_scale), not a generic "
          "target_accept or tuning change. If the four sigmas and correlations look "
          "comparable, this hypothesis is wrong too, and that's the real answer to "
          "report -- not a reason to force it.")


if __name__ == "__main__":
    main()
