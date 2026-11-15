"""
Reproducibility check for "sampling protocol v3.md", run before any
institution is scored with the drift terms.

The drift-type and shock-type collapse terms (RICD §10.3a) change the
scoring model, so the two guarantees the v2 checks established are tested
again:

1. Unchanged when switched off. With the drift terms off, the model must
   be exactly the v2 model. On each replica's own machine, the first 5
   scored institutions of the v2 test (window FY2009-FY2019, seed 7) are
   fitted twice with the v2 single-fit script: once with the pipeline as
   it was before the drift terms were added (model.py and
   score_institution.py taken from commit 4dbb884, every other file
   identical) and once with the current pipeline. The two must agree
   exactly (floating-point slack of 1e-9 only). Both fits run on the same
   machine, so any difference can only come from the code. This is also
   what guarantees that the live pipeline, which never switches the terms
   on, is unaffected.

   The first run of this check compared refits with the values committed
   in data/v2/test scores/ instead. Every institution the v2 test scored
   on the same processor model as the refit matched exactly; the two it
   scored on other processor models (Intel Xeon 6975P-C, AMD EPYC 9V45)
   did not, by up to 0.02. That comparison is kept as a report, because
   it measures how much a score depends on the machine, which the code
   change cannot affect.
2. Machine variation with the terms on. Two replicas, as two separate jobs,
   fit the first 10 scored institutions of the v2 test with the drift terms
   on (v3_score_one.py), each fit in its own process with an empty compile
   cache. Their differences are reported with the two processor models.

Passing: part 1 holds on both replicas. Part 2 is reported, not judged:
the first run of this check showed that exact agreement across processor
models does not hold for every institution even without the drift terms,
so every v3 result records the processor that produced it.

No outcome is used: the institutions are chosen by slot order among the
v2 test's scored institutions, and only their committed features are read.
The result is written to data/v3/reproducibility check.json.

Usage (GitHub Actions only, via check_v3_reproducibility.yml):
    cd src
    python check_v3_reproducibility.py replica --name a --compact C --finance F --out DIR
    python check_v3_reproducibility.py compare --dir DIR
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

import v2_common as v2
import v3_common as v3

OUT_PATH = v3.V3_DIR / "reproducibility check.json"
V2_TEST_SCORES = v2.V2_DIR / "test scores"
N_ON, N_OFF = 10, 5
BEFORE_DRIFT = "4dbb884"                     # last commit before the drift terms
CHANGED = ("model.py", "score_institution.py")
TOL = 1e-9


def first_scored() -> list[dict]:
    rows = []
    for p in sorted(V2_TEST_SCORES.glob("batch_*.json")):
        rows += [r for r in json.loads(p.read_text())["results"] if r["status"] == "scored"]
    rows.sort(key=lambda r: int(r["slot"]))
    return rows[:N_ON]


def old_src() -> Path:
    """A copy of src/ with the two changed files as they were before the drift terms."""
    here = Path(__file__).resolve().parent
    dst = Path(tempfile.mkdtemp(prefix="src_before_drift_")) / "src"
    shutil.copytree(here, dst, ignore=shutil.ignore_patterns("__pycache__"))
    for f in CHANGED:
        old = subprocess.run(["git", "show", f"{BEFORE_DRIFT}:src/{f}"], cwd=here, capture_output=True,
                             text=True, check=True).stdout
        (dst / f).write_text(old)
    return dst


def fit(script: str, row: dict, compact: str, finance: str, cwd: Path | None = None) -> dict:
    cache = tempfile.mkdtemp(prefix=f"cache_{row['unitid']}_")
    env = dict(os.environ)
    env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
    env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
    res = Path(cache) / "result.json"
    subprocess.run([sys.executable, script, "--unitid", row["unitid"], "--name", row["name"],
                    "--sector", row["finance form sector"], "--window", "test", "--seed", "7",
                    "--compact", str(Path(compact).resolve()), "--finance", str(Path(finance).resolve()),
                    "--out", str(res)], cwd=cwd or Path(__file__).resolve().parent, env=env, check=True)
    return json.loads(res.read_text())


def cmd_replica(name: str, compact: str, finance: str, out: str) -> None:
    win = v2.WINDOWS["test"]
    v2.prefetch_finance(finance, win["start_year"], win["end_year"], required=True)
    rows = first_scored()
    before = old_src()
    off, on = [], []
    for row in rows[:N_OFF]:
        r_old = fit("v2_score_one.py", row, compact, finance, cwd=before)
        r_new = fit("v2_score_one.py", row, compact, finance)
        off.append({"unitid": row["unitid"], "name": row["name"], "committed": row["features (seed 7)"],
                    "before drift terms": r_old.get("features"), "refit": r_new.get("features"),
                    "status": r_new["status"]})
    for row in rows:
        r = fit("v3_score_one.py", row, compact, finance)
        on.append({"unitid": row["unitid"], "name": row["name"], "status": r["status"],
                   "features": r.get("features"), "drift": r.get("drift"),
                   "divergences": r.get("divergences"), "rhat max": r.get("rhat max")})
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, f"replica_{name}.json").write_text(json.dumps(
        {"machine": v2.machine(), "pipeline file hashes": v3.pipeline_hashes(), "off": off, "on": on}, indent=2))


def diff(x: dict | None, y: dict | None) -> dict | None:
    if x is None or y is None or set(x) != set(y):
        return None
    return {k: abs(x[k] - y[k]) for k in x}


def ok(d: dict | None) -> bool:
    return d is not None and all(v <= TOL for v in d.values())


def cmd_compare(directory: str) -> None:
    a = json.loads(Path(directory, "replica_a.json").read_text())
    b = json.loads(Path(directory, "replica_b.json").read_text())
    off_rows, off_ok = [], True
    for rep, data in (("a", a), ("b", b)):
        for r in data["off"]:
            d = diff(r["before drift terms"], r["refit"])
            dc = diff(r["committed"], r["refit"])
            off_ok &= ok(d)
            off_rows.append({"replica": rep, "unitid": r["unitid"], "name": r["name"],
                             "differences from the pipeline before the drift terms (same machine)": d, "equal": ok(d),
                             "differences from the committed v2 score (report only)": dc})
    on_rows, on_ok = [], True  # on_ok is reported, not judged
    for ra, rb in zip(a["on"], b["on"]):
        df, dd = diff(ra["features"], rb["features"]), diff(ra["drift"], rb["drift"])
        equal = ok(df) and ok(dd)
        on_ok &= equal
        on_rows.append({"unitid": ra["unitid"], "name": ra["name"], "replica a": {"features": ra["features"], "drift": ra["drift"]},
                        "replica b": {"features": rb["features"], "drift": rb["drift"]},
                        "differences": {"features": df, "drift": dd}, "equal": equal,
                        "divergences (a, b)": [ra["divergences"], rb["divergences"]]})
    same_code = a["pipeline file hashes"] == b["pipeline file hashes"]
    verdict = "passed" if (off_ok and same_code) else "failed"
    history = []
    if OUT_PATH.exists():
        prev = json.loads(OUT_PATH.read_text())
        history = prev.get("earlier runs", []) + [{k: prev[k] for k in ("written at (UTC)", "verdict", "processors")}]
    v2.write_json(OUT_PATH, {
        "protocol": "sampling protocol v3.md, reproducibility check (before any drift-term scoring)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "drift terms off: identical to the pipeline before the drift terms": off_ok,
        "drift terms on: identical on both machines (reported, not judged)": on_ok,
        "processors": [a["machine"]["cpu"], b["machine"]["cpu"]],
        "pipeline file hashes": a["pipeline file hashes"],
        "drift terms off": off_rows,
        "drift terms on": on_rows,
        "machines": {"a": a["machine"], "b": b["machine"]},
        "earlier runs": history,
    })
    print(f"Verdict: {verdict}. Off-check {off_ok}, on-check (reported) {on_ok}. "
          f"Processors: {a['machine']['cpu']} / {b['machine']['cpu']}.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("replica")
    for x in ("--name", "--compact", "--finance", "--out"):
        p.add_argument(x, required=True)
    p = sub.add_parser("compare")
    p.add_argument("--dir", required=True)
    a = ap.parse_args()
    if a.cmd == "replica":
        cmd_replica(a.name, a.compact, a.finance, a.out)
    else:
        cmd_compare(a.dir)


if __name__ == "__main__":
    main()
