"""
Diagnostic, panel only, for choosing the confirmatory test's FY2019
window and confirming its enrollment data source, before the protocol
is amended. Fits the model but changes nothing and commits nothing.

Background (2026-11-12): at a six-year window ending in FY2019
(2013-2018 in the pipeline's year labels) every panel institution was
flagged high_risk, Harvard and Princeton included, and 20 of the 23
panel closures could not be scored at all because the College Scorecard
API has no record for them (src/diagnose_window_data.py). The panel's
own features were computed over 2005-06 through 2022-23.

This run, for every panel institution:

1. BULK SOURCE CHECK. Reads enrollment, completion, tuition and
   admission rate from the compact bulk Scorecard file
   (build_scorecard_compact.py) and, wherever the API also has a
   record, compares the two year by year for 2005-2018. They should
   agree exactly; this checks that switching sources changes where the
   numbers come from, not what they are. Also records how far back each
   institution's unbroken run of complete bulk years ending in 2018
   reaches, so closures' coverage is visible.

2. WINDOW CHOICE. Scores the institution through the live pipeline with
   the bulk source, at three windows ending in FY2019 -- starting 2005
   (the panel's own start, 14 years), 2008 (11 years, the length the
   weekly live scoring uses) and 2013 (6 years, the window already
   shown to flag everything) -- at production settings (300/300/2,
   target_accept 0.9, cores 1, Numba, seed 7), and reports each window's
   flags against the panel's recorded outcomes.

This is an in-sample check: the classifier was trained on these
institutions. It cannot validate a window; it can show that a window is
broken (flagging everything, or nothing), which is what it is for. No
confirmatory institution is touched and no outcome is looked up beyond
the panel's own recorded outcomes. Results go to reports/window_choice/.

Usage (GitHub Actions only, via diagnose_window_choice.yml):
    cd src
    python diagnose_window_choice.py --compact ../work/scorecard_compact.csv --shard 0 --of 18
    python diagnose_window_choice.py --summarize ../reports/window_choice_all
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from pathlib import Path

PANEL_PATH = "../data/panel/panel.json"
OUT_DIR = Path("../reports/window_choice")
END_YEAR = 2019
WINDOWS = (2005, 2008, 2013)
COMPARE_YEARS = range(2005, 2019)
SAMPLER = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9,
               cores=1, compile_mode="NUMBA", random_seed=7)
INSUFF_RE = re.compile(r"^(INSUFFICIENT [A-Z ]+?):", re.M)


def compare_with_api(unitid: str) -> dict:
    import fetch_live_data as fld
    fields = [f"{y}.{api}" for y in COMPARE_YEARS for api in fld.BULK_TO_API.values()]
    try:
        api = fld.fetch_scorecard_fields(unitid, fields)
    except ValueError:
        return {"api record": False}
    except Exception as e:
        return {"api record": None, "api error": f"{type(e).__name__}: {e}"}
    compared, mismatches = 0, []
    for y in COMPARE_YEARS:
        try:
            bulk = fld._bulk_scorecard_fields(unitid, y)
        except KeyError:
            continue
        for key, bv in bulk.items():
            av = api.get(key)
            if av is None and bv is None:
                continue
            compared += 1
            if av is None or bv is None or abs(float(av) - bv) > 1e-6 * max(1.0, abs(bv)):
                mismatches.append({"field": key, "api": av, "bulk": bv})
    return {"api record": True, "values compared": compared, "mismatches": mismatches[:10],
            "mismatch count": len(mismatches)}


def bulk_run_start(unitid: str, sector: str) -> int | None:
    import fetch_live_data as fld
    start = None
    for y in range(2018, 1995, -1):
        try:
            f = fld._bulk_scorecard_fields(unitid, y)
        except KeyError:
            break
        need = ["student.size", "completion.completion_rate_4yr_150nt", "cost.tuition.in_state"]
        if sector != "forprofit":
            need.append("admissions.admission_rate.overall")
        if not all(f.get(f"{y}.{n}") is not None for n in need):
            break
        start = y
    return start


def run_shard(compact: str, shard: int, of: int) -> None:
    import fetch_live_data as fld
    from classifier import RICDClassifier, load_panel
    from score_institution import compute_features_for_institution
    from check_panel_convergence import hd2019_sectors, Tee

    fld.use_bulk_scorecard(compact)
    panel = load_panel(PANEL_PATH)
    clf = RICDClassifier()
    clf.fit(panel)
    sectors = hd2019_sectors()
    mine = [inst for i, inst in enumerate(panel) if i % of == shard]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"shard_{shard}_of_{of}.json"
    results = []

    for inst in mine:
        print(f"\n{'=' * 70}\n{inst.name} ({inst.unitid})\n{'=' * 70}", flush=True)
        sector = sectors.get(inst.unitid) or "private"
        row = {"unitid": inst.unitid, "name": inst.name, "panel_outcome": inst.outcome,
               "sector": sector, "bulk run start": bulk_run_start(inst.unitid, sector),
               "api comparison": compare_with_api(inst.unitid), "windows": {}}
        for start in WINDOWS:
            print(f"\n--- window {start}-{END_YEAR - 1} ---", flush=True)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(Tee(sys.stdout, buf)):
                    feats = compute_features_for_institution(
                        inst.unitid, inst.name, sector=sector, start_year=start, end_year=END_YEAR, **SAMPLER)
            except Exception as e:
                row["windows"][start] = {"status": f"error: {type(e).__name__}: {e}"}
                continue
            if feats is None:
                reasons = INSUFF_RE.findall(buf.getvalue())
                row["windows"][start] = {"status": "insufficient data",
                                         "reason": reasons[0].lower() if reasons else "no features"}
                continue
            feats.governance_flag = False
            X = clf.scaler.transform(feats.to_vector().reshape(1, -1))
            row["windows"][start] = {
                "status": "scored",
                "probability": float(clf.model.predict_proba(X)[0, 1]),
                "flag": "high_risk" if int(clf.model.predict(X)[0]) == 1 else "stable",
            }
        results.append(row)
        path.write_text(json.dumps(results, indent=2))
    path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {path} ({len(results)} institutions)")


def summarize(directory: str) -> None:
    rows = []
    for p in sorted(Path(directory).rglob("shard_*.json")):
        rows.extend(json.loads(p.read_text()))
    rows.sort(key=lambda r: (r["panel_outcome"] != 1, r["name"]))

    print("\nWINDOW CHOICE, FY2019 end, bulk Scorecard source, production settings, seed 7")
    print("Cells: probability and flag (H = high_risk, s = stable), or the reason it could not be scored")
    print("=" * 120)
    print(f"{'Institution':28s} {'outcome':>7s} {'bulk from':>9s} {'API':>5s} {'API diffs':>9s} | "
          + " | ".join(f"{'from ' + str(w):>22s}" for w in WINDOWS))
    for r in rows:
        outcome = {1: "closed", 0: "stable"}.get(r["panel_outcome"], "?")
        cmp_ = r["api comparison"]
        api = {True: "yes", False: "none", None: "err"}[cmp_.get("api record")]
        diffs = str(cmp_.get("mismatch count", "-")) if cmp_.get("api record") else "-"
        cells = []
        for w in WINDOWS:
            c = r["windows"].get(str(w)) or r["windows"].get(w) or {}
            if c.get("status") == "scored":
                cells.append(f"{c['probability']:.3f} {'H' if c['flag'] == 'high_risk' else 's'}")
            else:
                cells.append((c.get("reason") or c.get("status") or "-")[:22])
        print(f"{r['name'][:28]:28s} {outcome:>7s} {str(r['bulk run start'] or '-'):>9s} {api:>5s} {diffs:>9s} | "
              + " | ".join(f"{c:>22s}" for c in cells))
    print("=" * 120)

    for w in WINDOWS:
        def cell(r):
            return r["windows"].get(str(w)) or r["windows"].get(w) or {}
        closed = [r for r in rows if r["panel_outcome"] == 1]
        stable = [r for r in rows if r["panel_outcome"] == 0]
        cs = [r for r in closed if cell(r).get("status") == "scored"]
        ss = [r for r in stable if cell(r).get("status") == "scored"]
        cf = sum(1 for r in cs if cell(r)["flag"] == "high_risk")
        sf = sum(1 for r in ss if cell(r)["flag"] == "high_risk")
        correct = cf + (len(ss) - sf)
        n = len(cs) + len(ss)
        print(f"Window from {w}: scored {len(cs)}/{len(closed)} closed, {len(ss)}/{len(stable)} stable; "
              f"closed flagged {cf}/{len(cs)}, stable flagged {sf}/{len(ss)}; "
              f"in-sample accuracy {correct}/{n}" + (f" ({100 * correct / n:.1f}%)" if n else ""))

    with_api = [r for r in rows if r["api comparison"].get("api record")]
    total = sum(r["api comparison"].get("values compared", 0) for r in with_api)
    bad = sum(r["api comparison"].get("mismatch count", 0) for r in with_api)
    print(f"Bulk vs API: {len(with_api)} institutions with an API record, {total} values compared, {bad} mismatches")
    closed = [r for r in rows if r["panel_outcome"] == 1]
    print(f"Closures with bulk data in an unbroken run ending 2018: {sum(1 for r in closed if r['bulk run start'])} / {len(closed)}")

    (Path(directory) / "summary.json").write_text(json.dumps(rows, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact")
    ap.add_argument("--shard", type=int)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--summarize")
    a = ap.parse_args()
    if a.summarize:
        summarize(a.summarize)
    else:
        run_shard(a.compact, a.shard or 0, a.of)


if __name__ == "__main__":
    main()
