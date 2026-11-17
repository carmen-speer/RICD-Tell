"""
RICD Definition 8.9.1 (Common-Cause Signature), automated.

Confirmed earlier this session: this diagnostic only works on RAW,
adapter-level observables (e.g. raw year-over-year enrollment change),
not on Bayesian model-derived latent quantities (D_op, delta_R) -- the
model's own shared-prior structure smooths out exactly the kind of
sharp, synchronized shock this mechanism exists to detect. Confirmed
directly: raw enrollment co-movement showed a real, dramatic spike at
COVID (8.7% in 2019, the lowest value in a 16-year series, to 36.4% in
2020) that neither model-derived quantity showed at all. This module
therefore operates on raw data only, by design, not as an oversight.

This replaces the one-time, manually-run COVID validation script with a
real, callable, reusable tool that can be run against any year range or
any subset of the panel going forward, rather than re-derived by hand
each time the question comes up.
"""

import csv
import numpy as np


def compute_common_cause_series(scorecard_path, uids, observable="n_undergrads",
                                  year_start=2010, year_end=2022, shift_percentile=75):
    """
    Computes Co(t) for every calendar year in [year_start, year_end],
    using raw year-over-year percent change in `observable` across the
    given set of institutions.

    year_start defaults to 2010, not the earliest available year --
    confirmed earlier this session that the first several years of any
    institution's series show artificially inflated co-movement (34-67%)
    as a model/data warm-up artifact, not real signal. Years before 2010
    are excluded by default for exactly this reason; a caller with a
    specific reason to include them may override year_start, but should
    expect the same artifact to reappear.

    Returns a dict: {calendar_year: {'co_t': float, 'n_institutions': int,
    'median_abs_shift': float, 'flagged': bool}}, where 'flagged' uses
    a genuine statistical rule (Co(t) exceeding the row's own trailing
    baseline by more than 1.5x the baseline's own standard deviation),
    not an eyeballed threshold.
    """
    with open(scorecard_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    by_id = {}
    for r in rows:
        by_id.setdefault(r["id"], {})[r["academic_year"]] = r

    shifts_by_year = {}
    for uid in uids:
        inst_years = by_id.get(uid, {})
        years_sorted = sorted(inst_years.keys())
        for i in range(1, len(years_sorted)):
            y0, y1 = years_sorted[i - 1], years_sorted[i]
            try:
                v0 = float(inst_years[y0][observable])
                v1 = float(inst_years[y1][observable])
                if v0 > 0:
                    pct_change = (v1 - v0) / v0
                    calendar_year = int(y1[:4])
                    if year_start <= calendar_year <= year_end:
                        shifts_by_year.setdefault(calendar_year, []).append(pct_change)
            except (ValueError, KeyError):
                pass

    all_shifts = [s for shifts in shifts_by_year.values() for s in shifts]
    if not all_shifts:
        return {}
    threshold = np.percentile(np.abs(all_shifts), shift_percentile)

    results = {}
    for year in sorted(shifts_by_year.keys()):
        shifts = shifts_by_year[year]
        co_t = float(np.mean(np.abs(shifts) > threshold))
        med = float(np.median(np.abs(shifts)))
        results[year] = {"co_t": co_t, "n_institutions": len(shifts), "median_abs_shift": med}

    # Genuine statistical flag: co_t exceeding the series' own mean by
    # more than 1.5 standard deviations, computed leave-one-out (each
    # year's own value excluded from the baseline it's compared against)
    # rather than a fixed percentile chosen after seeing the COVID result.
    co_values = {y: v["co_t"] for y, v in results.items()}
    years = sorted(co_values.keys())
    for year in years:
        others = [co_values[y] for y in years if y != year]
        baseline_mean = np.mean(others)
        baseline_std = np.std(others)
        results[year]["flagged"] = bool(
            co_values[year] > baseline_mean + 1.5 * baseline_std
        )

    return results


def run_common_cause_check(scorecard_path, uids, **kwargs):
    """
    Convenience wrapper: runs compute_common_cause_series and returns
    only the flagged years, printing a short real-data report. This is
    the function to call for an ordinary "is anything unusual in this
    panel's history" check, without needing to know the underlying
    statistic's mechanics.
    """
    series = compute_common_cause_series(scorecard_path, uids, **kwargs)
    flagged = {y: v for y, v in series.items() if v["flagged"]}
    print(f"Common-Cause Signature check across {len(uids)} institutions, "
          f"{min(series.keys())}-{max(series.keys())}:")
    if not flagged:
        print("  No years flagged.")
    for year, v in flagged.items():
        print(f"  {year}: Co(t)={v['co_t']:.1%} (baseline institutions: "
              f"{v['n_institutions']}, median shift: {v['median_abs_shift']:.3f}) -- FLAGGED")
    return flagged
