"""
Phase 5 of "sampling protocol v3.md": v3 test outcomes and measures.

Runs only once every v3 test institution has a committed result and the
comparator flags are committed, so that every score and every comparator
flag precedes every v3 test outcome.

Outcomes. Each v3 test institution is coded with the scoring year 2019
from the IPEDS header files for 2019 through the latest available (2020
through 2026 are tried), under the outcome definition of "sampling
protocol v2.md", by the same coding function and with the same reading
check as the corrected v2 phase 8 (every header file must yield at least
3,000 institutions, or the run stops and records nothing).

Measures, for scored v3 test institutions under the primary coding, as in
v2: E, S, F, J, precision, closure rate and lift, with 95% Wilson
intervals and a 95% percentile bootstrap interval for J (10,000
resamples, random seed 20261115).

Triggers and passing:
  minimum events  E >= 10 overall and E_np >= 10 among public and private
                  nonprofit institutions; if either is not met, the test is
                  underpowered and does not pass;
  R1              the lower bound of J's interval is at or below 0;
  R2              S < 0.50;
  R3              F > 0.30;
  R4              the comparator's J is equal to or greater than the
                  tracker's J, over the scored institutions for which the
                  comparator is computable;
  R5              the J of flagging every for-profit institution and nothing
                  else is equal to or greater than the tracker's J, over all
                  scored institutions;
  R6              among scored public and private nonprofit institutions,
                  the lower bound of the tracker's J interval (10,000
                  resamples of those institutions, random seed 20261115) is
                  at or below 0;
  passed          both minimums met and none of R1 to R6 fires.

Second verdict: whether the tracker's own features add anything beyond
size and sector. Among scored public and private nonprofit institutions,
the area under the ROC curve of classifier v3's probability is compared
with that of the frozen size-and-sector baseline's, by a paired 95%
percentile bootstrap of the difference (10,000 resamples of those
institutions, random seed 20261116). The tracker's features are found to
add value if the interval's lower bound is above 0, and not shown to add
value otherwise; if fewer than 10 of those institutions closed, the
verdict is that the test is underpowered for it. The two models' J at
their frozen cuts are reported beside it. This verdict does not change the
first.

Further pre-specified analyses, none of which changes a trigger or the
pass criterion: the measures under codings B and C; by sector; a paired
bootstrap interval for the tracker's J minus the for-profit-only rule's
J; the frozen classifier v2's coefficients applied to the same institutions'
v3-pipeline features; closure
rates among unscorable and structurally unscorable institutions and bounds
on S and F over all listed non-structural institutions; and the flagged
survivors.

The anchor sensor (RICD §10.5b.13c) is judged by two tests, neither of
which changes classifier v3's triggers or either verdict above:

  main test        among scored institutions flagged by classifier v3, the
                   area under the ROC curve of the anchor capacity for
                   survival, with a 95% percentile bootstrap interval
                   (10,000 resamples, random seed 20261117). The anchor
                   sensor passes if the lower bound is above 0.5, and the
                   test is underpowered unless at least 10 flagged
                   institutions closed and at least 10 survived;
  second test      over all scored institutions, the J of the anchored flag
                   minus the J of classifier v3's flag, with a paired 95%
                   bootstrap interval. The anchored flag improves on the
                   tracker if the lower bound is above 0.

Both are repeated under coding B, where a merger counts as survival, since
a system can save a member by merging it. Reported, not scored: closure
rates among flagged institutions with and without each of religious
affiliation, HBCU, tribal and land-grant status, and for-profit chain
membership, from data/v3/anchors.json. The processor of every scored
result is recorded, and the count and flag rate on each processor are
reported, because the pipeline's results differ slightly between processor
families (data/v3/reproducibility check.json).

Outputs: data/v3/test outcomes.json and data/v3/test results.json.

Usage (GitHub Actions only, via v3_test_results.yml):
    cd src
    python v3_test_results.py
"""

from __future__ import annotations

import datetime
import json

import numpy as np
from sklearn.metrics import roc_auc_score

import v2_common as v2
import v2_training_outcomes as coding
from v2_test_results import BOOT_N, BOOT_SEED, MIN_ROWS, SCORING_YEAR, download_all, measures
from v2_training_outcomes import committed
from score_v3_test import CLASSIFIER_PATH, OUTCOMES_PATH, SCORES_DIR, V3_DIR, done, institutions
from v3_comparator import OUT_PATH as COMPARATOR_PATH

RESULTS_PATH = V3_DIR / "test results.json"
ANCHORS_PATH = V3_DIR / "anchors.json"
AUC_SEED = 20261116
ANCHOR_SEED = 20261117


def anchor_auc(capacity, survived) -> dict:
    a, s_ = np.asarray(capacity, float), np.asarray(survived, bool)
    nc, ns = int((~s_).sum()), int(s_.sum())
    out = {"flagged institutions": len(s_), "closed": nc, "survived": ns,
           "underpowered": nc < 10 or ns < 10}
    if nc == 0 or ns == 0:
        out.update({"AUC": None, "AUC 95% bootstrap": [None, None], "verdict": "no test (one outcome only)"})
        return out
    out["AUC"] = float(roc_auc_score(s_, a))
    rng = np.random.default_rng(ANCHOR_SEED)
    vals = []
    for _ in range(BOOT_N):
        i = rng.integers(0, len(s_), len(s_))
        if 0 < s_[i].sum() < len(i):
            vals.append(roc_auc_score(s_[i], a[i]))
    out["AUC 95% bootstrap"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
    lo = out["AUC 95% bootstrap"][0]
    out["verdict"] = ("underpowered" if out["underpowered"] else
                      "passed: anchoring explains flagged survivors" if lo > 0.5 else
                      "failed: anchoring is not shown to explain flagged survivors")
    return out


def auc_difference(p_a, p_b, closed) -> dict:
    a, b, c = (np.asarray(x, float) for x in (p_a, p_b, closed))
    c = c.astype(bool)
    n = len(c)
    out = {"AUC, classifier v3": float(roc_auc_score(c, a)), "AUC, size-and-sector baseline": float(roc_auc_score(c, b))}
    out["difference"] = out["AUC, classifier v3"] - out["AUC, size-and-sector baseline"]
    rng = np.random.default_rng(AUC_SEED)
    diffs, dropped = [], 0
    for _ in range(BOOT_N):
        i = rng.integers(0, n, n)
        if c[i].all() or not c[i].any():
            dropped += 1
            continue
        diffs.append(roc_auc_score(c[i], a[i]) - roc_auc_score(c[i], b[i]))
    out["difference 95% paired bootstrap"] = [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]
    out["bootstrap resamples dropped"] = dropped
    return out


def paired_difference(flag_a, flag_b, closed) -> list:
    a, b, c = (np.asarray(x, bool) for x in (flag_a, flag_b, closed))
    n = len(c)
    rng = np.random.default_rng(BOOT_SEED)
    diffs = []
    for _ in range(BOOT_N):
        i = rng.integers(0, n, n)
        cc = c[i]
        e = cc.sum()
        if e == 0 or e == n:
            continue
        ja = (a[i] & cc).sum() / e - (a[i] & ~cc).sum() / (n - e)
        jb = (b[i] & cc).sum() / e - (b[i] & ~cc).sum() / (n - e)
        diffs.append(ja - jb)
    return [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))] if diffs else [None, None]


def main() -> None:
    clf_commit = committed(CLASSIFIER_PATH)
    comp_commit = committed(COMPARATOR_PATH)
    insts = institutions()
    missing = [i["unitid"] for i in insts if i["unitid"] not in done()]
    if missing:
        raise SystemExit(f"{len(missing)} v3 test institutions have no committed result; no outcome is looked up.")
    scores_commit = committed(SCORES_DIR)
    clf = json.loads(CLASSIFIER_PATH.read_text())
    comp = {r["unitid"]: r["operating margin"] for r in json.loads(COMPARATOR_PATH.read_text())["institutions"]}
    results = {}
    for p in sorted(SCORES_DIR.glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            results[r["unitid"]] = r

    files, not_found = download_all()
    years = sorted(files)
    coding.SCORING_YEAR, coding.FILES = SCORING_YEAR, years
    tables = {y: coding.rows_by_id(f["csv"]) for y, f in files.items()}
    for y in years:
        files[y]["institutions read"] = len(tables[y])
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
            rec.update({"flag": bool(r["flag"]), "score": r["score"],
                        "anchored flag": bool(r["anchored flag"]), "anchor capacity": r["anchor capacity (scale-free)"],
                        "processor": r["processor"],
                        "baseline flag": bool(r["baseline flag"]), "baseline score": r["baseline score"],
                        "v2 flag": bool(r["classifier v2 flag on v3-pipeline features (analysis only)"]),
                        "comparator": {"computable": comp[u]["computable"], "flag": comp[u].get("flag")}})
        records.append(rec)

    hidden = ("flag", "score", "anchored flag", "anchor capacity", "processor", "baseline flag", "baseline score",
              "v2 flag", "comparator")
    v2.write_json(OUTCOMES_PATH, {
        "protocol": "sampling protocol v3.md, phase 5 (test outcomes)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scoring year": SCORING_YEAR,
        "header files": [{k: v for k, v in f.items() if k != "csv"} for f in files.values()],
        "header files not served": not_found,
        "institutions": [{k: v for k, v in r.items() if k not in hidden} for r in records],
    })

    scored = [r for r in records if r["status"] == "scored"]
    nonprofit = [r for r in scored if r["sector"] != "forprofit"]
    closed = [r["closed or failed (primary)"] for r in scored]
    flag = [r["flag"] for r in scored]
    sector_rule = [r["sector"] == "forprofit" for r in scored]

    primary = measures(flag, closed)
    np_m = measures([r["flag"] for r in nonprofit], [r["closed or failed (primary)"] for r in nonprofit])
    rule_m = measures(sector_rule, closed, boot=False)
    E, E_np = primary["E (closed or failed)"], np_m["E (closed or failed)"]
    J_low = primary.get("J 95% bootstrap", [None])[0]
    Jnp_low = np_m.get("J 95% bootstrap", [None])[0]

    comp_set = [r for r in scored if r["comparator"]["computable"]]
    comp_tracker = measures([r["flag"] for r in comp_set], [r["closed or failed (primary)"] for r in comp_set], boot=False)
    comp_csd = measures([bool(r["comparator"]["flag"]) for r in comp_set],
                        [r["closed or failed (primary)"] for r in comp_set], boot=False)

    underpowered = E < 10 or E_np < 10
    triggers = {
        "R1 (no discrimination)": J_low is None or J_low <= 0,
        "R2 (low sensitivity)": primary["sensitivity S"] is None or primary["sensitivity S"] < 0.50,
        "R3 (excess false alarms)": primary["false-alarm rate F"] is not None and primary["false-alarm rate F"] > 0.30,
        "R4 (no advantage over the comparator)": (comp_csd["J"] is not None and comp_tracker["J"] is not None
                                                  and comp_csd["J"] >= comp_tracker["J"]),
        "R5 (no advantage over flagging every for-profit)": (rule_m["J"] is not None and primary["J"] is not None
                                                              and rule_m["J"] >= primary["J"]),
        "R6 (no discrimination among public and private nonprofit)": Jnp_low is None or Jnp_low <= 0,
    }
    passed = not underpowered and not any(triggers.values())

    np_closed = [r["closed or failed (primary)"] for r in nonprofit]
    if E_np < 10:
        second = {"verdict": "underpowered (fewer than 10 public and private nonprofit closures)"}
    else:
        both = [r for r in nonprofit if r["score"] is not None and r["baseline score"] is not None]
        second = auc_difference([r["score"] for r in both], [r["baseline score"] for r in both],
                                [r["closed or failed (primary)"] for r in both])
        second["institutions compared"] = len(both)
        second["verdict"] = ("the tracker's features add value beyond size and sector"
                             if second["difference 95% paired bootstrap"][0] > 0
                             else "not shown that the tracker's features add value beyond size and sector")
    second["J at frozen cuts, public and private nonprofit"] = {
        "classifier v3": np_m["J"],
        "size-and-sector baseline": measures([r["baseline flag"] for r in nonprofit], np_closed, boot=False)["J"]}
    second["baseline, all scored institutions"] = measures([r["baseline flag"] for r in scored], closed, boot=False)

    def by(group, key="flag"):
        return measures([bool(r[key]) for r in group], [r["closed or failed (primary)"] for r in group], boot=False)

    nonstruct = [r for r in records if r["status"] != "structurally unscorable"]

    def rate(group):
        n = len(group); e = sum(r["closed or failed (primary)"] for r in group)
        return {"N": n, "closed or failed": e, "rate": (e / n) if n else None}

    bound_hi = measures([r.get("flag", False) if r["status"] == "scored" else True for r in nonstruct],
                        [r["closed or failed (primary)"] for r in nonstruct], boot=False)
    bound_lo = measures([r.get("flag", False) if r["status"] == "scored" else False for r in nonstruct],
                        [r["closed or failed (primary)"] for r in nonstruct], boot=False)
    keys = ("N", "sensitivity S", "false-alarm rate F", "J")

    anchors = json.loads(ANCHORS_PATH.read_text())["cohorts"]["2019"]["records"]
    flagged = [r for r in scored if r["flag"]]

    def anchor_tests(key):
        surv = [not r[key] for r in flagged]
        main_t = anchor_auc([r["anchor capacity"] for r in flagged], surv)
        oc = [r[key] for r in scored]
        diff = paired_difference([r["anchored flag"] for r in scored], flag, oc)
        jv, ja = measures(flag, oc, boot=False)["J"], measures([r["anchored flag"] for r in scored], oc, boot=False)["J"]
        return {"main test: does anchoring explain flagged survivors": main_t,
                "second test: anchored flag against classifier v3's flag": {
                    "J, classifier v3": jv, "J, anchored flag": ja,
                    "difference, paired 95% bootstrap": diff,
                    "verdict": ("improves on the tracker" if diff[0] is not None and diff[0] > 0
                                else "not shown to improve on the tracker")},
                "flags cleared": sum(1 for r in scored if r["flag"] and not r["anchored flag"]),
                "of which closed": sum(1 for r in scored if r["flag"] and not r["anchored flag"] and r[key])}

    def described(pred):
        with_ = [r for r in flagged if pred(anchors.get(r["unitid"]) or {})]
        without = [r for r in flagged if not pred(anchors.get(r["unitid"]) or {})]
        return {"with": rate(with_), "without": rate(without)}

    anchor_out = {
        "primary coding": anchor_tests("closed or failed (primary)"),
        "coding B (mergers count as survival)": anchor_tests("coding B"),
        "reported, not scored (closure rates among flagged institutions)": {
            "religious affiliation": described(lambda a: a.get("RELAFFIL", "-2") not in ("", "-2", "-1")),
            "HBCU": described(lambda a: bool(a.get("HBCU"))),
            "tribal": described(lambda a: bool(a.get("TRIBAL"))),
            "land-grant": described(lambda a: bool(a.get("LANDGRNT"))),
            "for-profit chain member": described(lambda a: bool(a.get("system member")) and a.get("control") == "3"),
            "nonprofit or public system member (S_par = 1)": described(lambda a: a.get("S_par") == 1)},
    }
    procs = sorted({r["processor"] for r in scored})
    processor_out = {p: {"scored": sum(1 for r in scored if r["processor"] == p),
                         "flagged": sum(1 for r in scored if r["processor"] == p and r["flag"])} for p in procs}

    out = {
        "protocol": "sampling protocol v3.md, phase 5 (measures and revision triggers)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "classifier v3 (commit, time)": clf_commit, "test scores (commit, time)": scores_commit,
        "comparator flags (commit, time)": comp_commit,
        "header files used": [f"HD{y}" for y in years], "header files not served": not_found,
        "thresholds": {"public and private nonprofit": clf["classifier v3"]["threshold, public and private nonprofit"],
                       "for-profit": clf["classifier v3"]["threshold, for-profit"]},
        "primary result (scored institutions, primary coding)": primary,
        "public and private nonprofit (R6)": np_m,
        "flag every for-profit and nothing else (R5)": rule_m,
        "minimum events": {"E": E, "E among public and private nonprofit": E_np, "underpowered": underpowered},
        "triggers": triggers,
        "passed": passed,
        "second verdict: do the tracker's features add value beyond size and sector": second,
        "R4 comparison (scored institutions with a computable comparator)": {
            "N": len(comp_set), "tracker": comp_tracker, "comparator": comp_csd},
        "tracker J minus for-profit-only rule J, paired 95% bootstrap (analysis only)":
            paired_difference(flag, sector_rule, closed),
        "sensitivity codings (never used for triggers)": {
            "coding B (successor records count as surviving)": measures(flag, [r["coding B"] for r in scored], boot=False),
            "coding C (absence alone counts as surviving)": measures(flag, [r["coding C"] for r in scored], boot=False)},
        "by sector": {s: by([r for r in scored if r["sector"] == s]) for s in ("public", "private", "forprofit")},
        "frozen classifier v2 coefficients on the same institutions' v3-pipeline features (analysis only)": {
            "all scored": measures([r["v2 flag"] for r in scored], closed),
            "public and private nonprofit": by(nonprofit, "v2 flag")},
        "unscorable institutions": {
            "closure rate, scored": rate(scored),
            "closure rate, unscorable": rate([r for r in records if r["status"] == "unscorable"]),
            "closure rate, structurally unscorable": rate([r for r in records if r["status"] == "structurally unscorable"]),
            "bounds over all listed non-structural institutions": {
                "every unscorable counted as flagged": {k: bound_hi[k] for k in keys},
                "every unscorable counted as not flagged": {k: bound_lo[k] for k in keys}}},
        "anchor sensor": anchor_out,
        "processors": processor_out,
        "flagged survivors": [
            {"unitid": r["unitid"], "name": r["name"], "sector": r["sector"], "score": r["score"],
             "anchor capacity": r["anchor capacity"], "anchored flag": r["anchored flag"]}
            for r in scored if r["flag"] and not r["closed or failed (primary)"]],
        "machine": v2.machine(),
    }
    v2.write_json(RESULTS_PATH, out)
    print(f"E={E} (nonprofit {E_np})  S={primary['sensitivity S']}  F={primary['false-alarm rate F']}  "
          f"J={primary['J']}  J 95%={primary.get('J 95% bootstrap')}  nonprofit J 95%={np_m.get('J 95% bootstrap')}")
    print("triggers:", triggers, "| passed:", passed)
    print("second verdict:", second["verdict"])
    print("anchor sensor:", anchor_out["primary coding"]["main test: does anchoring explain flagged survivors"]["verdict"],
          "|", anchor_out["primary coding"]["second test: anchored flag against classifier v3's flag"]["verdict"])


if __name__ == "__main__":
    main()
