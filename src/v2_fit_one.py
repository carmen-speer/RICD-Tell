"""
Fits one institution once and writes its eight features to a JSON file.

Used by check_v2_equivalence_control.py, which runs this same file in two
copies of the pipeline (the code as it was before the v2 changes, and the
code after them) in separate processes on the same machine, so the two
can be compared with nothing else differing. Settings and window are the
first confirmatory test's (FY2009-FY2019, seed 7, 300 draws, 300 tuning
steps, 2 chains, target_accept 0.9, cores 1, Numba). No outcome is read.

Usage:
    python v2_fit_one.py --unitid U --name N --sector S --compact C --finance F --out O [--allow-gaps]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FEATURES = ("d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy",
            "debt_spike", "delta_R_trend", "reserve_adequacy", "research_ratio")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unitid", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--sector", required=True)
    ap.add_argument("--compact", required=True)
    ap.add_argument("--finance", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-gaps", action="store_true")
    args = ap.parse_args()

    import fetch_live_data as fld
    import score_confirmatory as sc
    from score_institution import compute_features_for_institution

    fld.use_bulk_scorecard(args.compact)
    sc.use_finance_cache(args.finance)
    sc.FINANCE_DIR = args.finance

    extra = {"allow_gaps": True} if args.allow_gaps else {}
    feats = compute_features_for_institution(
        args.unitid, args.name, sector=args.sector, start_year=sc.START_YEAR, end_year=sc.END_YEAR,
        random_seed=7, **sc.SAMPLER, **extra)
    out = None if feats is None else {k: float(getattr(feats, k)) for k in FEATURES}
    Path(args.out).write_text(json.dumps(out))


if __name__ == "__main__":
    main()
