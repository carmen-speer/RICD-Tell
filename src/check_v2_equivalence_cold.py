"""
Cold-cache equivalence check for "sampling protocol v2.md", phase 0
(second amendment).

The controlled check (data/v2/equivalence control.json) fitted the same 20
institutions three times each on one machine. For 19, the pipeline as it
was before the v2 changes and the changed pipeline agreed exactly on every
feature, and every repeat equalled its first run. For one, Alabama A & M
University, the old and changed pipelines differed; its old-code fit was
the first model fit of the whole job, made before any compiled code had
been cached, and it alone reproduced the first test's committed value
exactly. That points to the state of the compile cache, not the code, as
the source of the difference. This check tests that directly.

For each of the same 20 institutions, on one machine, it fits the old
pipeline, the changed pipeline, and the changed pipeline again, at seed 7,
each in its own process and each starting from its own new, empty
PyTensor compile directory and Numba cache directory, so that no fit
reuses anything an earlier fit compiled. The order alternates: for
odd-numbered slots the old pipeline is fitted first, for even-numbered
slots the changed pipeline is fitted first, so that neither version is
always the first fit.

Pass rule (second amendment to the protocol): the same as the controlled
check's. If every repeat equals its first run exactly, the check passes
only if the old and changed pipelines agree exactly on every feature of
every institution; if any repeat differs, the old-versus-changed
difference must be no larger than the largest repeat difference for that
feature across the 20 institutions. "Exactly" allows floating-point slack
of 1e-9 only.

The result is written to data/v2/equivalence cold.json, together with how
many cold fits of the old pipeline reproduce the first test's committed
seed-7 values exactly, which bears on whether the first test's own fits
were cold. Nothing here looks up any outcome.

Usage (GitHub Actions only, via check_v2_equivalence_cold.yml):
    cd src
    python check_v2_equivalence_cold.py --compact ../work/scorecard_compact.csv --finance ../work/finance
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import check_v2_equivalence as eq
import check_v2_equivalence_control as ctl
import score_confirmatory as sc

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "v2" / "equivalence cold.json"
TOL = 1e-9


def fit_cold(directory: Path, row: dict, sector: str, args, allow_gaps: bool, tag: str) -> dict | None:
    cache = tempfile.mkdtemp(prefix=f"cache_{row['unitid']}_{tag.replace(' ', '_')}_")
    env = dict(os.environ)
    env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
    env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
    out = Path(cache) / "features.json"
    cmd = [sys.executable, "v2_fit_one.py", "--unitid", row["unitid"], "--name", row["name"],
           "--sector", sector, "--compact", str(Path(args.compact).resolve()),
           "--finance", str(Path(args.finance).resolve()), "--out", str(out)]
    if allow_gaps:
        cmd.append("--allow-gaps")
    print(f"--- {row['name']} ({row['unitid']}): {tag}, empty cache at {cache}", flush=True)
    subprocess.run(cmd, cwd=directory, env=env, check=True)
    return json.loads(out.read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", required=True)
    ap.add_argument("--finance", required=True)
    args = ap.parse_args()

    eq.prefetch(args.finance)
    sc.FINANCE_DIR = args.finance
    ctl.build_old_pipeline()
    old_dir, new_dir = ctl.OLD_DIR, ROOT / "src"

    evals, _ = eq.committed_fits()
    recs = []
    for row in eq.first_scored():
        sector = sc.finance_sector(row["unitid"], evals[row["unitid"]]["sector"])
        old_first = int(row["slot"]) % 2 == 1
        if old_first:
            old = fit_cold(old_dir, row, sector, args, False, "old")
            new = fit_cold(new_dir, row, sector, args, True, "new")
        else:
            new = fit_cold(new_dir, row, sector, args, True, "new")
            old = fit_cold(old_dir, row, sector, args, False, "old")
        rep = fit_cold(new_dir, row, sector, args, True, "new repeat")
        recs.append({"slot": int(row["slot"]), "unitid": row["unitid"], "name": row["name"],
                     "finance form sector": sector, "fitted first": "old code" if old_first else "changed code",
                     "old code": old, "changed code": new, "changed code, repeat": rep,
                     "committed v1 seed 7": {k: f["features"][k] for f in evals[row["unitid"]]["fits"]
                                             if f["seed"] == 7 for k in eq.FEATURES}})

    def diff(a, b, k):
        if a is None or b is None:
            return float("inf")
        return abs(a[k] - b[k])

    repeat_max = {k: max(diff(r["changed code"], r["changed code, repeat"], k) for r in recs) for k in eq.FEATURES}
    deterministic = all(v <= TOL for v in repeat_max.values())
    limit = {k: TOL if deterministic else repeat_max[k] + TOL for k in eq.FEATURES}
    failures = []
    for r in recs:
        r["old vs changed"] = {k: diff(r["old code"], r["changed code"], k) for k in eq.FEATURES}
        r["changed vs repeat"] = {k: diff(r["changed code"], r["changed code, repeat"], k) for k in eq.FEATURES}
        r["old vs committed v1"] = {k: diff(r["old code"], r["committed v1 seed 7"], k) for k in eq.FEATURES}
        bad = [k for k in eq.FEATURES if r["old vs changed"][k] > limit[k]]
        if bad:
            failures.append({"unitid": r["unitid"], "name": r["name"], "features": bad})

    env = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout.split()
    out = {
        "protocol": "sampling protocol v2.md, phase 0 (equivalence check, second amendment: cold cache)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "old code": f"the four changed files from commit {ctl.OLD_COMMIT}; all other files identical",
        "every fit started from an empty compile cache": True,
        "machine reproduces its own result exactly": deterministic,
        "largest repeat difference per feature": repeat_max,
        "passed": not failures,
        "failures": failures,
        "cold old-code fits reproducing the committed v1 seed-7 values exactly (institutions)":
            sum(all(v <= TOL for v in r["old vs committed v1"].values()) for r in recs),
        "institutions": recs,
        "environment": env,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nMachine deterministic: {deterministic}. Passed: {not failures}. Wrote {OUT_PATH}.")


if __name__ == "__main__":
    main()
