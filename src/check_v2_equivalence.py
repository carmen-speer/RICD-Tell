"""
Phase 0 equivalence check for "sampling protocol v2.md".

The v2 pipeline changes let an institution be scored when some years of
its College Scorecard enrollment, completion or tuition are missing
(allow_gaps=True). Those changes are meant to admit more institutions,
not to move any institution's score. This script checks that directly.

It takes the first 20 institutions, in slot order, that the first
confirmatory test scored (every one of them had complete data), fits each
once with the changed pipeline at seed 7 under the first test's exact
settings and window (FY2009-FY2019, 300 draws, 300 tuning steps, 2
chains, target_accept 0.9, cores 1, Numba), and compares each of the
eight features with the values the first test committed for that
institution at seeds 7, 101 and 202.

Pass rule (from the protocol): every feature of every institution lies
within the range spanned by the three committed seeds. The script also
reports whether each value equals the committed seed-7 value exactly,
and whether every NCES finance file it read is byte-for-byte the file
the first test read (by SHA-256), since a file NCES has since revised
would explain a difference that the code did not cause.

Nothing here looks up any outcome. The result is written to
data/v2/equivalence check.json.

Usage (GitHub Actions only, via check_v2_equivalence.yml):
    cd src
    python check_v2_equivalence.py --compact ../work/scorecard_compact.csv --finance ../work/finance
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import score_confirmatory as sc

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "v2" / "equivalence check.json"
OUTCOMES_PATH = ROOT / "data" / "confirmatory" / "outcomes.csv"
N_INSTITUTIONS = 20
FEATURES = ("d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy",
            "debt_spike", "delta_R_trend", "reserve_adequacy", "research_ratio")
TOL = 1e-9  # floating-point slack only


def first_scored() -> list[dict]:
    with open(OUTCOMES_PATH, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["group"] == "scored"]
    rows.sort(key=lambda r: int(r["slot"]))
    return rows[:N_INSTITUTIONS]


def committed_fits() -> tuple[dict, dict]:
    """Each institution's committed passing evaluation, and every finance-file hash v1 recorded."""
    evals, hashes = {}, {}
    for path in sorted(sc.SCORES_DIR.glob("batch_*.json")):
        batch = json.loads(path.read_text())
        for name, digest in (batch.get("finance files (sha256)") or {}).items():
            hashes.setdefault(name, set()).add(digest)
        for ev in batch.get("evaluations", []):
            if ev.get("result") == "pass":
                evals[ev["unitid"]] = ev
    return evals, hashes


def prefetch(out: str) -> dict:
    """The first test's download loop, without its frozen-file check (the v2 files differ by design)."""
    import fetch_live_data as fld
    base = Path(out)
    manifest, missing = {}, []
    for sector in sc.SECTORS:
        for year in range(sc.START_YEAR, sc.END_YEAR):
            got = None
            for attempt in range(1, 7):
                got = fld.download_ipeds_finance_bulk(year, dest_dir=base / sector, sector=sector)
                if got is not None:
                    break
                time.sleep(30 * attempt)
            if got is None:
                missing.append(f"{sector} {year}")
                continue
            for f in sorted(Path(got).glob("*.csv")):
                manifest[f"{sector}/{year}/{f.name}"] = hashlib.sha256(f.read_bytes()).hexdigest()
            time.sleep(2)
    if missing:
        raise SystemExit("Could not download these NCES finance files: " + ", ".join(missing)
                         + ". Nothing recorded; run the workflow again later.")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", required=True)
    ap.add_argument("--finance", required=True)
    args = ap.parse_args()

    import fetch_live_data as fld
    from score_institution import compute_features_for_institution

    manifest = prefetch(args.finance)
    fld.use_bulk_scorecard(args.compact)
    sc.use_finance_cache(args.finance)
    sc.FINANCE_DIR = args.finance

    evals, v1_hashes = committed_fits()
    file_check = {name: (digest in v1_hashes[name]) if name in v1_hashes else None
                  for name, digest in manifest.items()}

    results, all_within, all_exact = [], True, True
    for row in first_scored():
        u, name = row["unitid"], row["name"]
        committed = evals.get(u)
        if committed is None:
            raise SystemExit(f"No committed passing evaluation found for {name} ({u}).")
        sector = sc.finance_sector(u, committed["sector"])
        print(f"\n{'=' * 70}\n{name} ({u}), finance form sector {sector}\n{'=' * 70}", flush=True)
        feats = compute_features_for_institution(
            u, name, sector=sector, start_year=sc.START_YEAR, end_year=sc.END_YEAR,
            random_seed=7, allow_gaps=True, **sc.SAMPLER)
        rec = {"slot": int(row["slot"]), "unitid": u, "name": name, "finance form sector": sector}
        if feats is None:
            rec["result"] = "the changed pipeline returned no features"
            all_within = all_exact = False
            results.append(rec)
            continue
        by_seed = {f["seed"]: f["features"] for f in committed["fits"]}
        comparison = {}
        for k in FEATURES:
            new = float(getattr(feats, k))
            seeds = [by_seed[s][k] for s in sc.SEEDS]
            within = min(seeds) - TOL <= new <= max(seeds) + TOL
            exact = abs(new - by_seed[7][k]) <= TOL
            all_within &= within
            all_exact &= exact
            comparison[k] = {"v2 seed 7": new, "v1 seeds 7, 101, 202": seeds,
                             "within v1 seed range": within, "equals v1 seed 7": exact}
        rec["features"] = comparison
        rec["availability"] = getattr(feats, "availability", None)
        rec["result"] = "within range" if all(c["within v1 seed range"] for c in comparison.values()) \
            else "OUTSIDE RANGE"
        results.append(rec)

    env = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout.split()
    out = {
        "protocol": "sampling protocol v2.md, phase 0 (equivalence check)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "passed": all_within,
        "every value equals the committed seed-7 value exactly": all_exact,
        "finance files identical to the first test's (by SHA-256)": all(v for v in file_check.values() if v is not None),
        "finance files not recorded by the first test": sorted(k for k, v in file_check.items() if v is None),
        "finance files that differ from the first test's": sorted(k for k, v in file_check.items() if v is False),
        "institutions": results,
        "environment": env,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nPassed: {all_within}. Exact seed-7 match for every value: {all_exact}. Wrote {OUT_PATH}.")


if __name__ == "__main__":
    main()
