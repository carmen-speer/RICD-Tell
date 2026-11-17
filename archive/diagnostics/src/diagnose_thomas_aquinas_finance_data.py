"""
Item 6, next step after the sigma_fin split test: diagnose_sigma_fin_
split.py's real result showed the shared-sigma hypothesis was only part
of the story. Splitting sigma_fin resolved E_exch cleanly (rhat 1.0634
-> 1.0028) and substantially improved M_maint and W_total (1.0593 ->
1.0125, 1.0578 -> 1.0165), but did essentially nothing for W_instr
(1.0639 -> 1.0605, unchanged within noise) -- and sigma_fin_instr became
the single worst parameter in the whole 38-variable model at 1.0983.
Whatever is wrong with the instructional-spend channel specifically is a
different, still-unidentified problem, not the shared-observation-noise
mechanism the split already fixed for the other three channels.

This script doesn't touch the model at all. It downloads and parses
Thomas Aquinas College's (UNITID 124292) real finance data -- the exact
same fld.download_ipeds_finance_bulk + fld.parse_live_finance calls
score_institution.py itself makes -- and prints the real, actual
E_exch/M_maint/W_instr/W_total values for every year, plus simple
year-over-year change statistics, to check one concrete hypothesis: that
W_instr's real values move faster, year to year, than its own
GaussianRandomWalk latent's fixed sigma=0.01 (model.py's
W_instr_latent = pm.GaussianRandomWalk("W_instr_latent", sigma=0.01, ...))
can plausibly track -- which would force NUTS to fight the latent's own
step-size prior to follow the real data, a real and different
poor-mixing mechanism than a shared observation-noise scale, and one
that wouldn't be fixed by splitting sigma_fin at all.

The other three channels' own GaussianRandomWalk sigmas are printed
alongside W_instr's for direct comparison: E_exch_latent sigma=0.02,
M_maint_latent sigma=0.005, W_total_latent sigma=0.02. If W_instr's real
year-over-year swings are large relative to sigma=0.01 in a way the
other three channels' swings are not relative to their own sigmas, that
is real, direct evidence for this hypothesis. If W_instr's swings look
proportionately ordinary next to the other three, the cause is
something else again, and that is the real, honest answer to report --
not a reason to force this explanation to fit.

Only runs from GitHub Actions -- nces.ed.gov is not reachable from the
sandboxed environments used to develop this code.
"""
from __future__ import annotations

import datetime

import numpy as np

import fetch_live_data as fld

UNITID = "124292"
NAME = "Thomas Aquinas College"
SECTOR = "private"
START_YEAR = 2013

# From model.py's build_model_stage2 -- the fixed step-size sigma and
# init_dist mean each channel's GaussianRandomWalk latent uses. Not
# re-derived here; copied verbatim so this diagnostic is checking the
# real, currently-live values, not a guess at them.
LATENT_SIGMAS = {
    "E_exch": 0.02,
    "M_maint": 0.005,
    "W_instr": 0.01,
    "W_total": 0.02,
}


def describe(label, values, window_years, sigma):
    real = [(y, v) for y, v in zip(window_years, values) if not np.isnan(v)]
    print(f"\n--- {label} (GaussianRandomWalk sigma={sigma}) ---")
    if not real:
        print("  No real observed years.")
        return
    for y, v in real:
        print(f"  {y}: {v:.4f}")
    vals = np.array([v for _, v in real])
    print(f"  n={len(vals)}, mean={vals.mean():.4f}, std={vals.std():.4f}, "
          f"min={vals.min():.4f}, max={vals.max():.4f}")
    if len(vals) >= 2:
        deltas = np.abs(np.diff(vals))
        ratio = deltas / sigma
        print(f"  year-over-year |delta|: mean={deltas.mean():.4f}, max={deltas.max():.4f}")
        print(f"  |delta| / latent sigma: mean={ratio.mean():.2f}x, max={ratio.max():.2f}x "
              f"(a GaussianRandomWalk step this many sigmas from 0 in one year is exactly "
              f"the kind of move that produces poor mixing/divergences if it happens often)")


def main():
    end_year = datetime.date.today().year - 2  # IPEDS lags by ~2 years
    window_years = [f"{y}-{str(y + 1)[2:]}" for y in range(START_YEAR, end_year)]

    print("=" * 70)
    print(f"REAL FINANCE DATA CHECK: {NAME} ({UNITID}), {window_years[0]}-{window_years[-1]}")
    print("=" * 70)
    print("Downloading real IPEDS bulk finance files...")

    dest_base = f"/tmp/ipeds_live/{UNITID}"
    finance_years_available = []
    for year in range(START_YEAR, end_year):
        result = fld.download_ipeds_finance_bulk(year, dest_dir=dest_base, sector=SECTOR)
        if result:
            finance_years_available.append(year)
    print(f"Downloaded {len(finance_years_available)}/{end_year - START_YEAR} years successfully.")

    E_exch, M_maint, W_instr, W_total, mask, scale = fld.parse_live_finance(
        UNITID, window_years, dest_base, sector=SECTOR)
    print(f"Parsed {int(mask.sum())} real years of finance data (scale={scale:,.0f}).")

    describe("E_exch  (revenue, F2B01)", E_exch, window_years, LATENT_SIGMAS["E_exch"])
    describe("M_maint (institutional support, F2E061)", M_maint, window_years, LATENT_SIGMAS["M_maint"])
    describe("W_instr (instruction, F2E011)", W_instr, window_years, LATENT_SIGMAS["W_instr"])
    describe("W_total (total expenses, F2B02)", W_total, window_years, LATENT_SIGMAS["W_total"])

    print("\n" + "=" * 70)
    print("Compare the four channels' 'year-over-year |delta| / latent sigma' lines "
          "above. If W_instr's ratio is meaningfully larger than E_exch's, M_maint's, "
          "and W_total's, that's real, direct evidence its GaussianRandomWalk sigma=0.01 "
          "is too tight for its real volatility -- a different, specific reparameterization "
          "target (raise W_instr_latent's sigma, or give it its own fitted sigma the way "
          "sigma_fin was just split) than the sigma_fin split already tested. If W_instr's "
          "ratio looks ordinary next to the other three, this hypothesis is wrong, and that "
          "is the real answer to report -- the cause is still open.")


if __name__ == "__main__":
    main()
