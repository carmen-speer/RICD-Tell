"""
Phase 8 of "sampling protocol v2.md": test outcomes and measures.

Runs only once every test institution has a committed result, the
comparator flags are committed, and classifier v2 is committed, so that
every score and every comparator flag precedes every test outcome.

Outcomes. Each test institution is coded with the scoring year 2019 from
the IPEDS header files for 2019 through the latest available (2020-2026
are tried; those NCES does not serve are recorded as not found), under the
protocol's outcome definition: the same primary coding and sensitivity
codings B and C as in training, applied by the training script's own
coding function (v2_training_outcomes.code) with its scoring year and file
list set to the test's. A closure date counts if it falls after 30 June
2019, or is a bare year of 2020 or later.

Measures, for scored test institutions under the primary coding: E, S, F,
J = S - F, precision, closure rate and lift, with 95% Wilson intervals for
S, F and precision and a 95% percentile bootstrap interval for J (10,000
resamples of the scored institutions, random seed 20261115; a resample
with no closures or no survivors has no J and is dropped, and the number
dropped is reported). The flag is the frozen classifier v2's flag at its
frozen threshold, from seed 7.

Triggers and passing, as the first protocol defines them, applied
unchanged:
  minimum events  if E < 10 the result is underpowered for sensitivity,
                  no confirmatory claim is made, and only R3 is evaluated;
  R1              the lower bound of J's interval is at or below 0;
  R2              E >= 10 and S < 0.50;
  R3              F > 0.30;
  R4              the comparator's J is equal to or greater than the
                  tracker's J, both over the scored institutions for which
                  the comparator is computable;
  passed          E >= 10, the lower bound of J's interval above 0,
                  S >= 0.50 and F <= 0.30.

The protocol's further pre-specified analyses, none of which changes a
trigger or the pass criterion: the measures under codings B and C; by
sector, including J within the for-profit sector; the analysis-only
variant without the missing-data features, and the fitted coefficients of
those features; closure rates among unscorable and structurally
unscorable institutions against scored ones, and bounds on S and F over
all drawn non-structural institutions with every unscorable institution
counted first as flagged and then as not flagged; the seed disagreements
and their outcomes; and the flagged survivors, listed for the separate
anchor analysis. The panel sanity check is a separate step.

Reading check. Every header file must yield at least 3,000 institutions
(each lists several thousand); otherwise the run stops and records
nothing, because a file that reads as empty would otherwise make every
institution absent from it and count it a closure under ground (d). The
number of institutions read from each file is recorded. This check was
added after the first phase 8 run, which read no institution from HD2025
(see the erratum in "sampling protocol v2.md").

Outputs: data/v2/test outcomes.json and data/v2/test results.json.

Usage (GitHub Actions only, via v2_test_results.yml):
    cd src
    python v2_test_results.py
"""

from __future__ import annotations

import datetime
import json
import math

import numpy as np
import requests

import v2_common as v2
import v2_training_outcomes as coding
from score_v2_test import CLASSIFIER_PATH, OUTCOMES_PATH, SCORES_DIR, done, institutions
from v2_comparator import OUT_PATH as COMPARATOR_PATH
from v2_training_outcomes import committed

RESULTS_PATH = v2.V2_DIR / "test results.json"
SCORING_YEAR = 2019
TRIED = list(range(2019, 2027))
BOOT_N = 10_000
BOOT_SEED = 20261115
Z = 1.959963984540054
MIN_ROWS = 3_000        # every IPEDS header file lists several thousand institutions


def wilson(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return [c - h, c + h]


def measures(flag, closed, boot: bool = True) -> dict:
    flag, closed = np.asarray(flag, bool), np.asarray(closed, bool)
    N, E = len(flag), int(closed.sum())
    tp, fp = int((flag & closed).sum()), int((flag & ~closed).sum())
    nflag = tp + fp
    S = tp / E if E else None
    F = fp / (N - E) if N - E else None
    prec = tp / nflag if nflag else None
    rate = E / N if N else None
    J = (S - F) if S is not None and F is not None else None
    out = {"N": N, "E (closed or failed)": E, "flagged": nflag, "true positives": tp, "false positives": fp,
           "sensitivity S": S, "S 95% Wilson": wilson(tp, E),
           "false-alarm rate F": F, "F 95% Wilson": wilson(fp, N - E),
           "precision": prec, "precision 95% Wilson": wilson(tp, nflag),
           "closure rate": rate, "lift": (prec / rate) if prec is not None and rate else None, "J": J}
    if boot and N:
        rng = np.random.default_rng(BOOT_SEED)
        boots, dropped = [], 0
        for _ in range(BOOT_N):
            i = rng.integers(0, N, N)
            f, c = flag[i], closed[i]
            e = c.sum()
            if e == 0 or e == N:
                dropped += 1
                continue
            boots.append((f & c).sum() / e - (f & ~c).sum() / (N - e))
        out["J 95% bootstrap"] = ([float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
                                  if boots else [None, None])
        out["bootstrap resamples dropped (no J)"] = dropped
    return out


def download_all() -> tuple[dict, list]:
    files, not_found = {}, []
    for y in TRIED:
        try:
            files[y] = coding.download_hd(y)
        except SystemExit:
            if y == SCORING_YEAR:
                raise
            not_found.append(f"HD{y}")
    return files, not_found


def main() -> None:
    clf_commit = committed(CLASSIFIER_PATH)
    comp_commit = committed(COMPARATOR_PATH)
    insts = institutions()
    missing = [i["unitid"] for i in insts if i["unitid"] not in done()]
    if missing:
        raise SystemExit(f"{len(missing)} test institutions have no committed result; no outcome is looked up.")
    scores_commit = committed(SCORES_DIR)
    clf = json.loads(CLASSIFIER_PATH.read_text())
    comp = {r["unitid"]: r["operating margin"] for r in json.loads(COMPARATOR_PATH.read_text())["institutions"]}
    results = {}
    for p in sorted(SCORES_DIR.glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            results[r["unitid"]] = r

    files, not_found = download_all()
    years = sorted(files)
    coding.SCORING_YEAR, coding.FILES = SCORING_YEAR, years      # the test's scoring year and header files
    tables = {y: coding.rows_by_id(f["csv"]) for y, f in files.items()}
    for y in years:                                               # a file that reads as (nearly) empty is a
        files[y]["institutions read"] = len(tables[y])            # reading error, never an outcome
        if len(tables[y]) < MIN_ROWS:
            raise SystemExit(f"HD{y} yielded {len(tables[y])} institutions (fewer than {MIN_ROWS}); "
                             "it was not read correctly. Nothing is recorded.")

    records = []
    for i in insts:
        u = i["unitid"]
        r = results[u]
        c = coding.code(u, {y: tables[y].get(u) for y in years})
        rec = {"slot": i["slot"], "unitid": u, "name": i["name"], "sector": i["sector"], "status": r["status"],
               "closed or failed (primary)": c["closed or failed (primary)"], "coding B": c["coding B"],
               "coding C": c["coding C"], "standing grounds": c["standing grounds"], "events": c["events"],
               "in first file": c["in HD2014"], "in latest file": c["in HD2019"]}
        if r["status"] == "scored":
            rec.update({"flag": r["flag (seed 7)"], "score": r["score (seed 7)"],
                        "variant flag (analysis only)": r["variant flag (seed 7, analysis only)"],
                        "seeds disagree": r["seeds disagree"], "flags at seeds 7, 101, 202": r["flags at seeds 7, 101, 202"],
                        "comparator": {"computable": comp[u]["computable"], "flag": comp[u].get("flag")}})
        records.append(rec)

    v2.write_json(OUTCOMES_PATH, {
        "protocol": "sampling protocol v2.md, phase 8 (test outcomes)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scoring year": SCORING_YEAR,
        "header files": [{k: v for k, v in f.items() if k != "csv"} for f in files.values()],
        "header files not served": not_found,
        "institutions": [{k: v for k, v in r.items() if k not in ("flag", "score", "variant flag (analysis only)",
                                                                   "seeds disagree", "flags at seeds 7, 101, 202",
                                                                   "comparator")} for r in records],
    })

    scored = [r for r in records if r["status"] == "scored"]
    flag = [bool(r["flag"]) for r in scored]
    closed = [r["closed or failed (primary)"] for r in scored]
    primary = measures(flag, closed)
    E = primary["E (closed or failed)"]
    J_low = primary.get("J 95% bootstrap", [None])[0]

    comp_set = [r for r in scored if r["comparator"]["computable"]]
    comp_tracker = measures([bool(r["flag"]) for r in comp_set], [r["closed or failed (primary)"] for r in comp_set])
    comp_csd = measures([bool(r["comparator"]["flag"]) for r in comp_set], [r["closed or failed (primary)"] for r in comp_set])

    underpowered = E < 10
    triggers = {
        "R1 (no discrimination)": None if underpowered else (J_low is None or J_low <= 0),
        "R2 (low sensitivity)": None if underpowered else (primary["sensitivity S"] < 0.50),
        "R3 (excess false alarms)": (primary["false-alarm rate F"] is not None and primary["false-alarm rate F"] > 0.30),
        "R4 (no advantage over the comparator)": None if underpowered else (
            comp_csd["J"] is not None and comp_tracker["J"] is not None and comp_csd["J"] >= comp_tracker["J"]),
    }
    passed = (not underpowered and J_low is not None and J_low > 0 and primary["sensitivity S"] >= 0.50
              and primary["false-alarm rate F"] <= 0.30)

    def by(group, key="flag"):
        return measures([bool(r[key]) for r in group], [r["closed or failed (primary)"] for r in group], boot=False)

    nonstruct = [r for r in records if r["status"] != "structurally unscorable"]
    uns = [r for r in records if r["status"] == "unscorable"]
    bound_hi = measures([bool(r.get("flag")) if r["status"] == "scored" else True for r in nonstruct],
                        [r["closed or failed (primary)"] for r in nonstruct], boot=False)
    bound_lo = measures([bool(r.get("flag")) if r["status"] == "scored" else False for r in nonstruct],
                        [r["closed or failed (primary)"] for r in nonstruct], boot=False)

    def rate(group):
        n = len(group); e = sum(r["closed or failed (primary)"] for r in group)
        return {"N": n, "closed or failed": e, "rate": (e / n) if n else None}

    out = {
        "protocol": "sampling protocol v2.md, phase 8 (measures and revision triggers)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "classifier v2 (commit, time)": clf_commit, "test scores (commit, time)": scores_commit,
        "comparator flags (commit, time)": comp_commit,
        "header files used": [f"HD{y}" for y in years], "header files not served": not_found,
        "threshold": clf["classifier v2"]["threshold"],
        "primary result (scored institutions, primary coding)": primary,
        "underpowered for sensitivity (E < 10)": underpowered,
        "triggers": triggers,
        "passed": passed,
        "R4 comparison (scored institutions with a computable comparator)": {
            "N": len(comp_set), "tracker": comp_tracker, "comparator": comp_csd},
        "sensitivity codings (never used for triggers)": {
            "coding B (successor records count as surviving)": measures(flag, [r["coding B"] for r in scored], boot=False),
            "coding C (absence alone counts as surviving)": measures(flag, [r["coding C"] for r in scored], boot=False)},
        "by sector": {s: by([r for r in scored if r["sector"] == s]) for s in ("public", "private", "forprofit")},
        "missing-data features": {
            "fitted coefficients": {k: clf["classifier v2"]["coefficients"][k] for k in ("gap_trailing", "gap_internal")},
            "variant without them (analysis only)": by(scored, "variant flag (analysis only)")},
        "unscorable institutions": {
            "closure rate, scored": rate(scored), "closure rate, unscorable": rate(uns),
            "closure rate, structurally unscorable": rate([r for r in records if r["status"] == "structurally unscorable"]),
            "bounds over all drawn non-structural institutions": {
                "every unscorable counted as flagged": {k: bound_hi[k] for k in ("N", "sensitivity S", "false-alarm rate F", "J")},
                "every unscorable counted as not flagged": {k: bound_lo[k] for k in ("N", "sensitivity S", "false-alarm rate F", "J")}}},
        "seed disagreement": {"scored institutions whose three seeds disagree": sum(r["seeds disagree"] for r in scored),
                              "of them closed or failed": sum(r["seeds disagree"] and r["closed or failed (primary)"] for r in scored),
                              "institutions": [{"unitid": r["unitid"], "name": r["name"], "flags": r["flags at seeds 7, 101, 202"],
                                                "closed or failed": r["closed or failed (primary)"]} for r in scored if r["seeds disagree"]]},
        "flagged survivors (for the separate anchor analysis)": [
            {"unitid": r["unitid"], "name": r["name"], "sector": r["sector"], "score": r["score"]}
            for r in scored if r["flag"] and not r["closed or failed (primary)"]],
        "panel sanity check": "a separate step; not part of this result",
        "machine": v2.machine(),
    }
    v2.write_json(RESULTS_PATH, out)
    p = primary
    print(f"E={E}  S={p['sensitivity S']}  F={p['false-alarm rate F']}  J={p['J']}  J 95%={p.get('J 95% bootstrap')}")
    print("triggers:", triggers, "| passed:", passed)


if __name__ == "__main__":
    main()
