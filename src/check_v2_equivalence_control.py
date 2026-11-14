"""
Controlled equivalence check for "sampling protocol v2.md", phase 0
(first amendment).

The first equivalence check (data/v2/equivalence check.json) compared the
changed pipeline, run on one GitHub Actions machine, with values the first
confirmatory test committed from other machines. For 10 of its 20
institutions the values matched exactly; for the other 10, the four
features that come out of the model's sampling step differed slightly,
although none of those 10 has any gap in its data, so the changed code
ran the original lines for them. That points to differences between
machines, not to the code. This check separates the two.

For each of the same 20 institutions, on one machine and one after the
other, it fits:
  1. the pipeline as it was before the v2 changes (the four changed files
     taken from commit 8a1608d, everything else identical), at seed 7;
  2. the changed pipeline (allow_gaps=True), at seed 7;
  3. the changed pipeline again, at seed 7, to measure whether the machine
     reproduces its own result.
Each fit runs in its own process, so nothing carries over between them.

Pass rule (first amendment to the protocol):
  - If every repeat (3) equals its first run (2) exactly, the machine is
    deterministic, and the check passes only if the old code (1) equals
    the changed code (2) exactly, for every feature of every institution.
  - If any repeat differs from its first run, the check passes only if,
    for every feature of every institution, the old-versus-changed
    difference is no larger than the largest repeat difference observed
    for that feature across all 20 institutions.
"Exactly" allows floating-point slack of 1e-9 only.

Nothing here looks up any outcome. The result is written to
data/v2/equivalence control.json.

Usage (GitHub Actions only, via check_v2_equivalence_control.yml):
    cd src
    python check_v2_equivalence_control.py --compact ../work/scorecard_compact.csv --finance ../work/finance
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

import check_v2_equivalence as eq
import score_confirmatory as sc

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "v2" / "equivalence control.json"
OLD_COMMIT = "8a1608d"
CHANGED_FILES = ("fetch_live_data.py", "model.py", "real_adapter.py", "score_institution.py")
OLD_DIR = Path("/tmp/v1_pipeline")
TOL = 1e-9


def build_old_pipeline() -> None:
    if OLD_DIR.exists():
        shutil.rmtree(OLD_DIR)
    shutil.copytree(ROOT / "src", OLD_DIR)
    for f in CHANGED_FILES:
        text = subprocess.run(["git", "show", f"{OLD_COMMIT}:src/{f}"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout
        (OLD_DIR / f).write_text(text)


def fit(directory: Path, row: dict, sector: str, args, allow_gaps: bool, tag: str) -> dict | None:
    out = Path(f"/tmp/fit_{row['unitid']}_{tag}.json")
    cmd = [sys.executable, "v2_fit_one.py", "--unitid", row["unitid"], "--name", row["name"],
           "--sector", sector, "--compact", str(Path(args.compact).resolve()),
           "--finance", str(Path(args.finance).resolve()), "--out", str(out)]
    if allow_gaps:
        cmd.append("--allow-gaps")
    print(f"--- {row['name']} ({row['unitid']}): {tag}", flush=True)
    subprocess.run(cmd, cwd=directory, check=True)
    return json.loads(out.read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", required=True)
    ap.add_argument("--finance", required=True)
    args = ap.parse_args()

    eq.prefetch(args.finance)
    sc.FINANCE_DIR = args.finance
    build_old_pipeline()
    new_dir = ROOT / "src"

    rows = eq.first_scored()
    evals, _ = eq.committed_fits()
    recs = []
    for row in rows:
        sector = sc.finance_sector(row["unitid"], evals[row["unitid"]]["sector"])
        old = fit(OLD_DIR, row, sector, args, False, "old")
        new = fit(new_dir, row, sector, args, True, "new")
        rep = fit(new_dir, row, sector, args, True, "new repeat")
        recs.append({"slot": int(row["slot"]), "unitid": row["unitid"], "name": row["name"],
                     "finance form sector": sector, "old code": old, "changed code": new,
                     "changed code, repeat": rep,
                     "committed v1 seed 7": {k: f["features"][k] for f in evals[row["unitid"]]["fits"]
                                             if f["seed"] == 7 for k in eq.FEATURES}})

    def diff(a, b, k):
        if a is None or b is None:
            return float("inf")
        return abs(a[k] - b[k])

    repeat_max = {k: max(diff(r["changed code"], r["changed code, repeat"], k) for r in recs) for k in eq.FEATURES}
    deterministic = all(v <= TOL for v in repeat_max.values())
    failures = []
    for r in recs:
        r["old vs changed"] = {k: diff(r["old code"], r["changed code"], k) for k in eq.FEATURES}
        r["changed vs repeat"] = {k: diff(r["changed code"], r["changed code, repeat"], k) for k in eq.FEATURES}
        r["old vs committed v1"] = {k: diff(r["old code"], r["committed v1 seed 7"], k) for k in eq.FEATURES}
        limit = {k: TOL for k in eq.FEATURES} if deterministic else {k: repeat_max[k] + TOL for k in eq.FEATURES}
        bad = [k for k in eq.FEATURES if r["old vs changed"][k] > limit[k]]
        if bad:
            failures.append({"unitid": r["unitid"], "name": r["name"], "features": bad})

    env = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout.split()
    out = {
        "protocol": "sampling protocol v2.md, phase 0 (equivalence check, first amendment)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "old code": f"the four changed files from commit {OLD_COMMIT}; all other files identical",
        "machine reproduces its own result exactly": deterministic,
        "largest repeat difference per feature": repeat_max,
        "passed": not failures,
        "failures": failures,
        "old code reproduces the committed v1 seed-7 values exactly (institutions)":
            sum(all(v <= TOL for v in r["old vs committed v1"].values()) for r in recs),
        "institutions": recs,
        "environment": env,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nMachine deterministic: {deterministic}. Passed: {not failures}. Wrote {OUT_PATH}.")


if __name__ == "__main__":
    main()
