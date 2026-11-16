"""
"reanalysis protocol.md": the exploratory reanalysis of tracker v3 with the
two-channel scoring model (model_two_channel.py).

No file frozen with classifier v3 is edited. This script reuses the v3
scripts unchanged and redirects them: the scoring model is replaced by
model_two_channel.py, every output goes to data/v3 reanalysis/, and the
pipeline-file fingerprint used by the v3 freeze checks also covers
model_two_channel.py and this script. The v3 test outcomes are already
known, so every result here is exploratory and changes no v3 verdict.

Usage (GitHub Actions only):
    reanalysis_rescore.yml (reanalysis 1):
        python reanalysis.py rescore prefetch --finance ../work/finance
        python reanalysis.py rescore shard --shard 0 --of 20 --minutes 290 \\
            --compact ../work/scorecard_compact.csv --finance ../work/finance --out ../work/evals
        python reanalysis.py rescore merge --evals ../work/evals
    reanalysis_finish.yml (reanalysis 2):
        python reanalysis.py fit --compact ../work/scorecard_compact.csv
        python reanalysis.py test --compact ../work/scorecard_compact.csv --finance ../work/finance
        python reanalysis.py results
    Internal, one fit in its own process:
        python reanalysis.py one <the arguments of v3_score_one.py>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import v2_common as v2
import v3_common as v3c

R_DIR = v2.ROOT / "data" / "v3 reanalysis"
RESCORED = R_DIR / "rescored"
CLASSIFIER = R_DIR / "classifier.json"
TEST_SCORES = R_DIR / "test scores"
OUTCOMES = R_DIR / "test outcomes.json"
RESULTS = R_DIR / "test results.json"
V3_TEST_SCORES = v2.ROOT / "data" / "v3" / "test scores"
LABEL = ("reanalysis protocol.md (exploratory: the two-channel scoring model, model_two_channel.py; "
         "the v3 test outcomes were already known, so no result here is a test)")
SEED = 7

v3c.PIPELINE_FILES = tuple(v3c.PIPELINE_FILES) + ("model_two_channel.py", "reanalysis.py")


def relabel(path: Path) -> None:
    d = json.loads(path.read_text())
    d = {"protocol": LABEL, "original v3 label": d.get("protocol"), **{k: v for k, v in d.items() if k != "protocol"}}
    v2.write_json(path, d)


def run_one(args: list[str], cache_prefix: str) -> dict | None:
    cache = tempfile.mkdtemp(prefix=cache_prefix)
    env = dict(os.environ)
    env["PYTENSOR_FLAGS"] = f"base_compiledir={cache}/pytensor"
    env["NUMBA_CACHE_DIR"] = f"{cache}/numba"
    res = Path(cache) / "result.json"
    subprocess.run([sys.executable, "reanalysis.py", "one", *args, "--out", str(res)],
                   cwd=Path(__file__).resolve().parent, env=env)
    if not res.exists():
        print("RETRY NEXT RUN: the fit process ended without a result.")
        return None
    r = json.loads(res.read_text())
    if r["status"] in ("error", "download failure"):
        print(f"RETRY NEXT RUN: {r['status']}: {r.get('error', '')}")
        return None
    return r


# ---------------------------------------------------------------- reanalysis 1: rescore
def test_list() -> list[dict]:
    out = []
    for p in sorted(V3_TEST_SCORES.glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            if r["status"] != "structurally unscorable":
                out.append({"unitid": r["unitid"], "name": r["name"], "sector": r["sector"],
                            "finance form sector": r["finance form sector"], "window": "test",
                            "scoring year": 2019, "key": f"v3test:{r['unitid']}"})
    return out


def rescore(argv: list[str]) -> None:
    import score_v3_development as dev
    base_list = dev.development_list
    dev.SCORES_DIR = RESCORED
    dev.development_list = lambda: base_list() + test_list()

    def checked_hashes() -> dict:
        if CLASSIFIER.exists():
            raise SystemExit("The reanalysis classifier is already fitted; nothing is rescored after it.")
        return v3c.pipeline_hashes()
    dev.checked_hashes = checked_hashes

    def fit_one(inst: dict, compact: str, finance: str) -> dict | None:
        print(f"\n{'=' * 70}\n{inst['name']} ({inst['unitid']}), {inst['window']} window, two-channel\n{'=' * 70}",
              flush=True)
        return run_one(["--unitid", inst["unitid"], "--name", inst["name"], "--sector", inst["finance form sector"],
                        "--window", inst["window"], "--seed", str(SEED),
                        "--compact", str(Path(compact).resolve()), "--finance", str(Path(finance).resolve())],
                       f"cache_{inst['unitid']}_")
    dev.fit_one = fit_one
    before = set(RESCORED.glob("batch_*.json"))
    sys.argv = ["score_v3_development.py", *argv]
    dev.main()
    for p in set(RESCORED.glob("batch_*.json")) - before:
        relabel(p)
    if argv and argv[0] == "merge":
        print(f"{len(dev.done())} of {len(dev.development_list())} institutions now have a two-channel result "
              f"({len(base_list())} development, {len(test_list())} v3 test).")


# ---------------------------------------------------------------- reanalysis 2: fit, test list, results
def fit(argv: list[str]) -> None:
    import fit_classifier_v3 as f
    f.OUT_PATH = CLASSIFIER
    f.DEV_SCORES = RESCORED

    def dev_batches() -> list[dict]:
        out = []
        for p in sorted(RESCORED.glob("batch_*.json")):
            b = json.loads(p.read_text())
            b["results"] = [r for r in b["results"] if not r["key"].startswith("v3test:")]
            out.append(b)
        return out
    f.dev_batches = dev_batches
    sys.argv = ["fit_classifier_v3.py", *argv]
    f.main()
    relabel(CLASSIFIER)


def rescored_test() -> dict:
    out = {}
    for p in sorted(RESCORED.glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            if r["key"].startswith("v3test:"):
                out[r["unitid"]] = {k: r[k] for k in ("seed", "status", "divergences", "rhat max", "features",
                                                      "drift", "availability", "reason") if k in r}
    return out


def test(argv: list[str]) -> None:
    import score_v3_test as t
    t.CLASSIFIER_PATH = CLASSIFIER
    t.OUTCOMES_PATH = OUTCOMES
    t.SCORES_DIR = TEST_SCORES
    cache = rescored_test()

    def fit_one(inst: dict, sector: str, compact: str, finance: str) -> dict | None:
        r = cache.get(inst["unitid"])
        if r is None:
            raise SystemExit(f"{inst['unitid']} has no two-channel result; run reanalysis 1 again.")
        return r
    t.fit_one = fit_one
    work = Path(tempfile.mkdtemp(prefix="evals_"))
    sys.argv = ["score_v3_test.py", "shard", "--shard", "0", "--of", "1", "--minutes", "100000",
                "--out", str(work), *argv]
    t.main()
    before = set(TEST_SCORES.glob("batch_*.json"))
    sys.argv = ["score_v3_test.py", "merge", "--evals", str(work)]
    t.main()
    for p in set(TEST_SCORES.glob("batch_*.json")) - before:
        relabel(p)


def results() -> None:
    import score_v3_test as t
    t.CLASSIFIER_PATH = CLASSIFIER
    t.OUTCOMES_PATH = OUTCOMES
    t.SCORES_DIR = TEST_SCORES
    import v3_test_results as res
    res.RESULTS_PATH = RESULTS
    res.main()
    relabel(OUTCOMES)
    relabel(RESULTS)


def one(argv: list[str]) -> None:
    import model_two_channel
    sys.modules["model"] = model_two_channel
    import v3_score_one
    sys.argv = ["v3_score_one.py", *argv]
    v3_score_one.main()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd, rest = sys.argv[1], sys.argv[2:]
    R_DIR.mkdir(parents=True, exist_ok=True)
    if cmd == "rescore":
        rescore(rest)
    elif cmd == "fit":
        fit(rest)
    elif cmd == "test":
        test(rest)
    elif cmd == "results":
        results()
    elif cmd == "one":
        one(rest)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
