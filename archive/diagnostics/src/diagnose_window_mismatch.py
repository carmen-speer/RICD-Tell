"""
Follow-up to diagnose_panel_pipeline_consistency.py, built to resolve
what that first diagnostic could not.

WHAT THE FIRST DIAGNOSTIC (diagnose_panel_pipeline_consistency.py) FOUND,
run 2026-09-15: all five panel-frozen "stable" public flagships --
Michigan, UVA, UNC-Chapel Hill, and Wisconsin confirmed directly
(Florida did not appear in the captured run output; this script
re-checks it too) -- came back with frac_high_entropy jumping from
their frozen 0.0000 to 0.6000-0.8000 when recomputed live, and
reserve_adequacy dropping by roughly 0.22-0.38 in every case, all in
the same direction. That consistency across independent institutions
is real signal, not noise -- but two different real explanations were
left tangled together and neither could be ruled out from that run
alone:

  (1) WINDOW MISMATCH: score_institution.py's compute_features_for_institution()
      defaults end_year to datetime.date.today().year - 2. The panel
      (data/panel/panel.json) was committed to this repo on
      2026-08-29 (confirmed via `git log --follow`, not guessed) --
      but that is the panel's COMMIT date, not proof of what end_year
      the original, no-longer-present extract_features.py script
      actually used when it built these feature vectors. Since
      2026-08-29 and today (2026-09-15) fall in the same calendar
      year, the literal "year rolled over since panel-build" story
      cannot be the mechanism here -- both dates compute the same
      today().year - 2 = 2024. A real mismatch is still very plausible
      (extract_features.py may simply have used a different, hardcoded
      end_year that was never kept in sync with this default), it just
      isn't explained by elapsed time the way the first diagnostic's
      docstring guessed.

  (2) MCMC NON-CONVERGENCE: every single live run in the first
      diagnostic reported rhat > 1.01 and effective sample size < 100,
      at production's actual settings (300 draws, 300 tune, 2 chains).
      frac_high_entropy is a fraction of POSTERIOR-DRAW regime
      classifications (dynamics.classify_regime on rolling variance of
      the posterior mean trajectories) -- exactly the kind of
      downstream quantity that gets noisy or biased under real
      non-convergence, independent of any window effect. The other
      panel-vs-live deltas (delta_R_final, delta_R_trend) flipped sign
      inconsistently across institutions, which looks like sampling
      noise rather than a systematic effect -- unlike frac_high_entropy
      and reserve_adequacy, which moved the same direction for all
      four confirmed institutions.

This script separates those two explanations empirically instead of
guessing between them:
  - Runs at n_draws=1000, n_tune=1000, n_chains=4, target_accept=0.95
    (score_institution.py now accepts these as real parameters --
    see that file's compute_features_for_institution() -- rather than
    the hardcoded 300/300/2 production default) to remove
    non-convergence as a live confound.
  - At those settings, sweeps end_year across 2023, 2024, and 2025
    (bracketing the current 2024 default in both directions) for each
    of the five panel institutions, diffing every candidate against
    the frozen panel record.
  - Prints a compact final summary table across every
    institution x end_year combination, so the answer survives even
    if a long Actions log gets truncated in a copy-paste.

READING THE RESULT:
  - If some end_year candidate reproduces frac_high_entropy close to
    the panel's frozen value (near 0.0) for most/all institutions even
    at these much higher settings, that confirms a real window
    mismatch with a specific, fixable value -- score_institution.py's
    default should be pinned to it.
  - If NO end_year candidate reproduces the panel closely for most
    institutions even with non-convergence removed, that rules out a
    simple end_year fix and points somewhere else: the underlying
    model/dynamics code has very likely been revised since panel.json
    was frozen (dynamics.py's own docstrings document multiple
    corrected mechanisms -- the O_o/O_p scoring fix, the regime-floor
    fix, the causal-normalization window fix -- any of which could
    have shifted results after the panel was built without the panel
    ever being regenerated against the current code). In that case the
    real fix is regenerating panel.json from the current pipeline, not
    tuning a live-scoring parameter.
  - If frac_high_entropy shrinks substantially at ANY end_year once
    n_draws/n_tune/n_chains go up, relative to the first diagnostic's
    300/300/2 numbers, that is itself direct evidence that
    non-convergence was inflating it, regardless of which window turns
    out to be right -- worth fixing in score_institution.py's
    production defaults independent of the window question.

Does NOT call save_live_score() -- this never touches
docs/data/live_scores.json or the public dashboard. Diagnostic only.

Usage:
    python diagnose_window_mismatch.py
    python diagnose_window_mismatch.py --only 170976
    python diagnose_window_mismatch.py --end-years 2023,2024,2025

Requires COLLEGE_SCORECARD_API_KEY set in the environment (same as
score_institution.py / score_batch.py / diagnose_feature_values.py).

This is a genuinely slower run than the first diagnostic -- 4x the
chains and roughly 3x the draws/tune per fit, times three end_year
candidates instead of one, across five institutions. Expect this to
take much longer in the Actions log than the ~1 minute the first
diagnostic took; that is the deliberate cost of removing
non-convergence as a confound, not a hang.
"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

from score_institution import compute_features_for_institution

# The panel's own commit date, confirmed via `git log --follow --
# data/panel/panel.json` against this repo on 2026-09-15: the panel
# file was introduced in the "Initial commit: RICD higher-ed collapse
# tracker" commit, dated 2026-08-29. Recorded here as documentation
# for whoever reads this script's output next, not used in any
# computation below (the actual build date of the ORIGINAL, no-longer-
# present extract_features.py run could be earlier than this commit;
# the commit date is only an upper bound on it).
PANEL_COMMITTED_DATE = "2026-08-29"

TARGETS = [
    ("170976", "Michigan", "public", 2013),
    ("234076", "UVA", "public", 2013),
    ("199120", "UNC-Chapel Hill", "public", 2013),
    ("134130", "Florida", "public", 2013),
    ("240444", "Wisconsin", "public", 2013),
]

DEFAULT_END_YEAR_CANDIDATES = [2023, 2024, 2025]

# Removes non-convergence as a confound -- see module docstring. Real
# rhat > 1.01 / ESS < 100 warnings were observed at production's
# 300/300/2 on every single run in the first diagnostic.
N_DRAWS = 1000
N_TUNE = 1000
N_CHAINS = 4
TARGET_ACCEPT = 0.95

PANEL_PATH = Path(__file__).resolve().parent.parent / "data" / "panel" / "panel.json"

FEATURE_FIELDS = [
    "d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy",
    "debt_spike", "delta_R_trend", "reserve_adequacy", "research_ratio",
]

# The two features the first diagnostic's docstring flagged as the
# ones that would actually confirm a window mismatch (as opposed to
# delta_R_final/delta_R_trend, which flipped sign inconsistently
# across institutions in that run and look more like sampling noise).
KEY_FIELDS = ["frac_high_entropy", "reserve_adequacy"]


def fmt(v):
    return f"{v:.4f}" if isinstance(v, (int, float)) else "  n/a "


def load_panel_record(unitid: str) -> dict | None:
    with open(PANEL_PATH) as f:
        panel = json.load(f)
    for rec in panel:
        if rec["unitid"] == unitid:
            return rec
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Check just this one UNITID from TARGETS")
    parser.add_argument("--end-years", default="",
                         help="Comma-separated end_year candidates to sweep "
                              "(default: 2023,2024,2025)")
    args = parser.parse_args()

    targets = TARGETS
    if args.only:
        targets = [t for t in TARGETS if t[0] == args.only]
        if not targets:
            raise SystemExit(f"UNITID {args.only} is not in TARGETS -- edit this script to add it.")

    end_year_candidates = DEFAULT_END_YEAR_CANDIDATES
    if args.end_years:
        end_year_candidates = [int(y.strip()) for y in args.end_years.split(",") if y.strip()]

    print(f"Panel committed: {PANEL_COMMITTED_DATE} (see module docstring for what this "
          f"does and doesn't tell us)")
    print(f"Sampling settings for this run: n_draws={N_DRAWS}, n_tune={N_TUNE}, "
          f"n_chains={N_CHAINS}, target_accept={TARGET_ACCEPT} "
          f"(production default is 300/300/2/0.9)")
    print(f"end_year candidates: {end_year_candidates}")

    # unitid -> end_year -> {field: delta} or None (insufficient data) or "ERROR"
    summary: dict[str, dict[int, dict | str | None]] = {}

    for unitid, name, sector, start_year in targets:
        summary[unitid] = {}
        panel_rec = load_panel_record(unitid)
        if panel_rec is None:
            print(f"\nREAL ERROR: {name} ({unitid}) not found in {PANEL_PATH} -- check the UNITID.")
            continue

        print(f"\n{'=' * 100}\n{name} ({unitid})\n{'=' * 100}")
        print(f"\nFROZEN PANEL RECORD (as used to train/validate the classifier):")
        for field in FEATURE_FIELDS:
            print(f"  {field:20s} = {fmt(panel_rec.get(field))}")
        print(f"  outcome              = {'stable' if panel_rec.get('outcome') == 0 else 'closure'}")

        for end_year in end_year_candidates:
            print(f"\n--- {name} ({unitid}), end_year={end_year} "
                  f"(window {start_year}-{end_year - 1}) ---")
            try:
                live = compute_features_for_institution(
                    unitid, name, sector=sector, start_year=start_year, end_year=end_year,
                    n_draws=N_DRAWS, n_tune=N_TUNE, n_chains=N_CHAINS, target_accept=TARGET_ACCEPT,
                )
                if live is None:
                    print(f"  RESULT: insufficient_data at end_year={end_year} -- see the real "
                          f"reason printed above.")
                    summary[unitid][end_year] = None
                    continue

                live_vec = {
                    "d_A_trend": live.d_A_trend, "d_A_final": live.d_A_final,
                    "delta_R_final": live.delta_R_final, "frac_high_entropy": live.frac_high_entropy,
                    "debt_spike": live.debt_spike, "delta_R_trend": live.delta_R_trend,
                    "reserve_adequacy": live.reserve_adequacy, "research_ratio": live.research_ratio,
                }
                for field in FEATURE_FIELDS:
                    print(f"  {field:20s} = {fmt(live_vec.get(field))}")

                deltas = {}
                print(f"\n  DELTA (live minus panel):")
                for field in FEATURE_FIELDS:
                    p = panel_rec.get(field)
                    l = live_vec.get(field)
                    if isinstance(p, (int, float)) and isinstance(l, (int, float)):
                        deltas[field] = l - p
                        flag = " <-- key field" if field in KEY_FIELDS else ""
                        print(f"    {field:20s} delta = {l - p:+.4f}{flag}")
                summary[unitid][end_year] = deltas
            except Exception as e:
                print(f"  REAL ERROR at end_year={end_year} for {name} ({unitid}): "
                      f"{type(e).__name__}: {e}")
                traceback.print_exc()
                summary[unitid][end_year] = "ERROR"

    # --- Final summary table: survives even if the log above got truncated ---
    print(f"\n{'=' * 100}\nSUMMARY -- |delta| on the two key fields, by institution x end_year "
          f"(lower is closer to the frozen panel; 'insuff' = insufficient live data; "
          f"'ERROR' = real exception, see traceback above)\n{'=' * 100}")
    header = f"{'institution':20s}" + "".join(f"{'end_year=' + str(y):>28s}" for y in end_year_candidates)
    print(header)
    for unitid, name, sector, start_year in targets:
        row = f"{name:20s}"
        for end_year in end_year_candidates:
            result = summary.get(unitid, {}).get(end_year, "n/a")
            if result is None:
                cell = "insuff"
            elif result == "ERROR":
                cell = "ERROR"
            elif isinstance(result, dict):
                parts = []
                for field in KEY_FIELDS:
                    d = result.get(field)
                    parts.append(f"{field.split('_')[0]}={d:+.3f}" if isinstance(d, (int, float)) else "n/a")
                cell = " ".join(parts)
            else:
                cell = "n/a"
            row += f"{cell:>28s}"
        print(row)

    print(f"\n{'=' * 100}\nDIAGNOSTIC DONE -- read the module docstring's \"READING THE RESULT\" "
          f"section against this table before concluding anything.\n{'=' * 100}")


if __name__ == "__main__":
    main()
