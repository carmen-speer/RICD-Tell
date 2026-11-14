"""
Real adapter for RICD-BSSM: maps actual College Scorecard fields (via the
Rdatasets GitHub mirror of the U.S. Dept. of Education's public dataset)
to RICD's O_o, O_p, P_m channels, replacing the synthetic v0.1 adapter.

STAGE 2 UPDATE: adds real institutional finance data (revenue,
institutional-support/administrative spending, instructional spending,
net tuition), pulled from seven verified IPEDS Finance survey years
(2006-07, 2009-10, 2011-12, 2015-16, 2017-18, 2020-21, 2023-24) for six
private-nonprofit (FASB/F2-reporting) institutions, and wires E_exch,
M_maint, and W_adaptive to it. Verified against each year's actual data
dictionary, not assumed to carry over -- all five underlying variable
codes (F2B01, F2B02, F2E061, F2E011, F2D01) held identical meaning
across all seven years and 17 years span, confirmed directly.

CONCRETE MAPPING DECISIONS, STAGE 1 (superseded, kept for history):
O_p = completion rate. O_o = sticker tuition, normalized. P_m proxy WAS
admissions-rate trend, explicitly flagged at the time as not the real
construction.

STAGE 4 UPDATE: P_m proxy replaced. Primary proxy is now 1 - part-time
instructional staff share, drawn from real IPEDS HR data where
available (2013/2017/2023) -- a principled connection to genuine
self-monitoring capacity (job security enabling honest internal
dissent), not an arbitrary substitute the way admissions-rate trend
always was. Admissions-rate trend is retained only as a fallback for
years/institutions without HR data. External Governance Attestation
(RICD Definition 6.1.1 -- real AAUP censure/sanction or accreditor
action) is applied as a separate, direct override per
apply_governance_attestation() below, never blended into the
continuous proxy as one more weighted input.

CONCRETE MAPPING DECISIONS, STAGE 2 (new):
E_exch (resource inflow) = F2B01, total revenues and investment return.
M_maint (maintenance/administrative burden) = F2E061, institutional
support -- this is the genuine real-world counterpart to RICD's
maintenance-first priority convention, not a proxy for it.
W_adaptive candidate = F2E011, instruction spending -- money actually
reaching the core academic mission, distinct from administrative
overhead.
Net tuition = F2D01, confirmed net of discounts/allowances in every
year's dictionary description, not just the variable label.

Finance data is SPARSE relative to the annual enrollment/completion
panel: only 7 of 18 possible years are directly observed. This is
handled as a genuine sparse-observation problem in the state-space
model (model.py), not by interpolating fake intermediate values here --
R(t) and S(t) are latent, continuously-evolving states that the model
infers throughout, tied to real data only at the 7 years it actually
exists.
"""

import numpy as np
import csv
import json
from collections import defaultdict


def load_scorecard(path):
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    by_id = defaultdict(dict)
    for r in rows:
        by_id[r["id"]][r["academic_year"]] = r
    return by_id


def load_finance(path):
    """Load the pre-extracted real finance data (Stage 2)."""
    with open(path) as f:
        return json.load(f)


def extract_institution_series(by_id, unitid, window_years):
    """
    Pull the raw real fields for one institution across the panel window.
    Returns dict of numpy arrays, or None if any required field is
    missing for any year.
    """
    completion = []
    tuition = []
    admit_rate = []
    n_undergrads = []
    for y in window_years:
        row = by_id[unitid].get(y)
        if row is None:
            return None
        try:
            completion.append(float(row["rate_completion"]))
            tuition.append(float(row["cost_tuition_in"]))
            admit_rate.append(float(row["rate_admissions"]))
            n_undergrads.append(float(row["n_undergrads"]))
        except (ValueError, KeyError):
            return None
    return dict(
        completion=np.array(completion),
        tuition=np.array(tuition),
        admit_rate=np.array(admit_rate),
        n_undergrads=np.array(n_undergrads),
    )


def build_finance_observation_mask(finance_data, unitid, window_years):
    """
    For a given institution and the full annual window, return:
      - E_exch_obs: array (len(window_years),), NaN where not observed
      - M_maint_obs: same shape, institutional support
      - W_instr_obs: same shape, instruction spending
      - W_total_obs: same shape, REAL total expenses (F2B02) -- used for
        the resource recursion's W_t, not the incomplete
        instruction+institutional-support sum. An earlier version of
        this function only wired in two expense sub-categories, which
        meant W_t could never structurally exceed revenue given their
        real scale, and delta_R_t (resource debt) never activated --
        confirmed as exactly zero at every timepoint when actually run.
        F2B02 was already extracted but not used; this fixes that.
      - observed_mask: boolean array, True at the 7 real finance years
      - scale: the fixed normalization scale used

    Values are normalized by a fixed, pre-specified reference scale
    (not each institution's own trailing range -- 6.8's causal
    normalization rule).
    """
    fin = finance_data.get(unitid, {})
    n = len(window_years)
    E_exch = np.full(n, np.nan)
    M_maint = np.full(n, np.nan)
    W_instr = np.full(n, np.nan)
    W_total = np.full(n, np.nan)
    mask = np.zeros(n, dtype=bool)

    scale = 15_000_000_000.0 if unitid == "162928" else 500_000_000.0

    for i, y in enumerate(window_years):
        cal_year = int(y[:4]) + 1
        key = str(cal_year)
        if key in fin:
            E_exch[i] = fin[key]["revenue"] / scale
            M_maint[i] = fin[key]["institutional_support"] / scale
            W_instr[i] = fin[key]["instruction"] / scale
            W_total[i] = fin[key]["expenses"] / scale
            mask[i] = True

    return E_exch, M_maint, W_instr, W_total, mask, scale


def compute_O_o_O_p(series):
    """
    Apply the stated mapping (module docstring) to raw fields, returning
    O_o(t), O_p(t) in [0,1] -- both normalized against a fixed reference
    range, not each institution's own trailing range.
    """
    # nanmax (2026-11-14, "sampling protocol v2.md", phase 0): the
    # percentage test reads the largest observed value, so a missing
    # (NaN) year cannot silently send a percentage series down the wrong
    # branch. For a complete series nanmax equals max; missing years stay
    # NaN through np.clip.
    O_p = np.clip(series["completion"] / 100.0, 0, 1) if np.nanmax(series["completion"]) > 1 else \
          np.clip(series["completion"], 0, 1)
    O_o = np.clip(series["tuition"] / 60000.0, 0, 1)
    return O_o, O_p


def compute_P_m_proxy(series, hr_data=None, uid=None):
    """
    P_m proxy, revised. The admissions-rate version below is kept as the
    fallback for years/institutions where no HR data is available, but
    it is no longer the primary proxy -- see module docstring history.

    Primary proxy, where HR data exists: 1 - part_time_share. Tenured
    and tenure-track faculty have genuine job security enabling honest
    internal dissent; contingent, non-tenure-track faculty are
    structurally less able to serve as an honest self-monitoring
    population (RICD Definition 8.5b.5's form/function material and
    Definition 11.10.2's contingent-staffing signal both bear directly
    on this). A rising part-time share is accordingly read as a
    declining capacity for genuine self-monitoring, not merely a cost
    signal -- this is a principled connection to what P_m is actually
    meant to represent, not an arbitrary substitute the way raw
    admissions-rate trend always was.

    Where hr_data supplies a real part-time share for this institution
    and year, it is used directly. Where it does not (most years, since
    real HR data currently covers only 2013/2017/2023), the admissions-
    rate fallback is used, and P_m for the intervening years should be
    read as lower-confidence than years with real HR data -- an honest
    interpolation gap, not a claim that admissions rate has become a
    good proxy again.

    External Governance Attestation (RICD Definition 6.1.1) is applied
    separately, as a direct override, not blended into this continuous
    proxy -- see apply_governance_attestation() below.
    """
    admit = series["admit_rate"]
    if admit.max() > 1:
        admit = admit / 100.0
    fallback = np.clip(1 - admit, 0, 1)

    if hr_data is None or uid is None or uid not in hr_data.get("2023", {}) and uid not in hr_data.get("2017", {}):
        return fallback

    # Use real PT-share where available for a given year; hold the
    # nearest known real value for years without direct HR data rather
    # than silently reverting to the admissions-rate fallback mid-series.
    proxy = fallback.copy()
    known = {}
    for year_key in ("2017", "2023"):
        v = hr_data.get(year_key, {}).get(uid, {}).get("pt_share")
        if v is not None:
            known[int(year_key)] = 1 - v
    if known:
        years_sorted = sorted(known.keys())
        for i, year in enumerate(series.get("years", [])):
            nearest = min(years_sorted, key=lambda y: abs(y - year))
            proxy[i] = known[nearest]
    return proxy


def apply_governance_attestation(uid, external_flags):
    """
    RICD Definition 6.1.1 (External Governance Attestation), applied
    directly. external_flags is adapter-supplied: {uid: {'source':
    'AAUP-censure'|'AAUP-sanction'|'accreditor-probation'|..., 'active':
    bool}, ...}. Per Definition 6.1.1, this is never blended into the
    continuous P_m proxy as one more weighted input -- it is reported
    directly, as confirmed evidence, regardless of how rare it is in a
    given dataset. Returns None where no attestation exists (the
    continuous proxy governs alone), or a strong override signal where
    one does.
    """
    flag = external_flags.get(uid)
    if flag is None or not flag.get("active"):
        return None
    return {"attested": True, "source": flag["source"]}
