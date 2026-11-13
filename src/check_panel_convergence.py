"""
Pre-scoring measurement for the confirmatory test: how often does the
protocol's convergence check pass on the 54-institution validation
panel, under the exact conditions the confirmatory run will use?

WHY THIS EXISTS: `sampling protocol.md`'s insufficient-data rule skips
any institution whose fit shows a divergent transition or any
parameter with R-hat above 1.01. At production settings (300 draws,
300 tuning steps, 2 chains), R-hat above 1.01 has already been seen on
known-stable panel institutions (score_institution.py's own docstring,
2026-09-15) and on Thomas Aquinas and Wittenberg under every fix tried
(README, Known Gaps). If the check fails for a large share of
institutions, it would tilt the confirmatory sample toward
easy-to-fit institutions and could exhaust slots' 25 backups. This
script measures that on the panel only, so any revision to the rule
can be made before a single confirmatory institution is scored. It
touches no confirmatory institution and looks up no outcome.

CONDITIONS, matching the protocol's "Frozen scoring configuration":
FY2019 data and earlier only (start_year 2013, end_year 2019, so the
last finance file is F1819), 300/300/2, target_accept 0.9, cores 1,
the Numba backend, random seed 7. Only the convergence check is
measured here (one fit per institution), not the three-seed stability
check.

WHAT IT REPORTS, per institution: whether data was sufficient; the
divergence count; the maximum R-hat over every posterior variable
(what score_institution.py's CONVERGENCE line reports); and the
maximum R-hat over free (sampled) parameters only, since the protocol
says "any parameter" and Deterministics only inherit their R-hat from
the free parameters. The summary counts passes under both readings.

It never writes to data/panel/panel.json, the dashboard, or anything
under data/confirmatory/. Results go to reports/panel_convergence/ and
are uploaded as a workflow artifact.

Usage (GitHub Actions only; needs network access to NCES and the
College Scorecard, and COLLEGE_SCORECARD_API_KEY):
    cd src
    python check_panel_convergence.py --shard 0 --of 3
    python check_panel_convergence.py --summarize ../reports/panel_convergence
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
OUT_DIR = Path("../reports/panel_convergence")

START_YEAR = 2013
END_YEAR = 2019  # range(2013, 2019) -> last finance file F1819, i.e. FY2019
START_YEAR_OVERRIDES = {
    "484613": 2014,  # University of Phoenix-Arizona (see score_batch.py)
}
RHAT_LIMIT = 1.01

CONV_RE = re.compile(r"CONVERGENCE: (\d+) divergences, max rhat=([0-9.]+|nan|inf)")
PARAM_RE = re.compile(r"^  ([* ]) (\S+)\s+max_rhat=([0-9.]+|nan|inf)", re.M)


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def parse_log(text: str) -> dict:
    out = {"divergences": None, "rhat_max_all": None, "rhat_max_free": None}
    m = CONV_RE.search(text)
    if m:
        out["divergences"] = int(m.group(1))
        out["rhat_max_all"] = float(m.group(2))
    free = [float(v) for mark, _, v in PARAM_RE.findall(text) if mark == "*"]
    if free:
        out["rhat_max_free"] = max(free)
    return out


def run_shard(shard: int, of: int) -> None:
    from classifier import load_panel
    from score_institution import compute_features_for_institution
    import fetch_live_data as fld

    panel = load_panel(PANEL_PATH)
    mine = [inst for i, inst in enumerate(panel) if i % of == shard]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for inst in mine:
        unitid, name = inst.unitid, inst.name
        print(f"\n{'=' * 70}\n{name} ({unitid})\n{'=' * 70}", flush=True)
        row = {"unitid": unitid, "name": name, "panel_outcome": inst.outcome}

        sector = fld.detect_sector(unitid)
        if sector is None:
            row["status"] = "sector_detection_failed"
            results.append(row)
            continue
        row["sector"] = sector

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(Tee(sys.stdout, buf)):
                features = compute_features_for_institution(
                    unitid, name, sector=sector,
                    start_year=START_YEAR_OVERRIDES.get(unitid, START_YEAR),
                    end_year=END_YEAR,
                    n_draws=300, n_tune=300, n_chains=2, target_accept=0.9,
                    cores=1, compile_mode="NUMBA", random_seed=7,
                    debug_param_rhat=True,
                )
        except Exception as e:  # recorded, never retried or rescued
            row["status"] = f"error: {type(e).__name__}: {e}"
            row.update(parse_log(buf.getvalue()))
            results.append(row)
            continue

        row.update(parse_log(buf.getvalue()))
        row["features_returned"] = features is not None
        if features is None and row["divergences"] is None:
            row["status"] = "insufficient_data"
        else:
            row["status"] = "fitted"
        results.append(row)

    path = OUT_DIR / f"shard_{shard}_of_{of}.json"
    path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {path} ({len(results)} institutions)")


def passes(row: dict, key: str) -> bool:
    r = row.get(key)
    return (row.get("divergences") == 0 and r is not None and r <= RHAT_LIMIT)


def summarize(directory: str) -> None:
    rows = []
    for p in sorted(Path(directory).rglob("shard_*.json")):
        rows.extend(json.loads(p.read_text()))
    rows.sort(key=lambda r: r["name"])

    fitted = [r for r in rows if r.get("status") == "fitted"]
    no_data = [r for r in rows if r.get("status") == "insufficient_data"]
    other = [r for r in rows if r.get("status") not in ("fitted", "insufficient_data")]

    print("\nPANEL CONVERGENCE CHECK (FY2019 window, production settings, seed 7)")
    print("=" * 100)
    print(f"{'Institution':45s} {'outcome':>7s} {'status':>18s} {'div':>4s} "
          f"{'rhat all':>9s} {'rhat free':>9s} {'pass all':>8s} {'pass free':>9s}")
    for r in rows:
        def fmt(v):
            return "-" if v is None else f"{v:.4f}"
        status = r.get("status", "")[:18]
        div = "-" if r.get("divergences") is None else str(r["divergences"])
        pa = "yes" if passes(r, "rhat_max_all") else ("no" if r.get("status") == "fitted" else "-")
        pf = "yes" if passes(r, "rhat_max_free") else ("no" if r.get("status") == "fitted" else "-")
        outcome = {1: "closed", 0: "stable"}.get(r.get("panel_outcome"), "?")
        print(f"{r['name'][:45]:45s} {outcome:>7s} {status:>18s} {div:>4s} "
              f"{fmt(r.get('rhat_max_all')):>9s} {fmt(r.get('rhat_max_free')):>9s} {pa:>8s} {pf:>9s}")

    n = len(fitted)
    n_div0 = sum(1 for r in fitted if r.get("divergences") == 0)
    n_all = sum(1 for r in fitted if passes(r, "rhat_max_all"))
    n_free = sum(1 for r in fitted if passes(r, "rhat_max_free"))
    print("=" * 100)
    print(f"Institutions in panel:                 {len(rows)}")
    print(f"Insufficient data in FY2019 window:    {len(no_data)}")
    print(f"Errors / sector detection failures:    {len(other)}")
    print(f"Fitted:                                {n}")
    if n:
        print(f"  Zero divergences:                    {n_div0} / {n} ({100 * n_div0 / n:.1f}%)")
        print(f"  Pass (R-hat <= 1.01, all variables): {n_all} / {n} ({100 * n_all / n:.1f}%)")
        print(f"  Pass (R-hat <= 1.01, free params):   {n_free} / {n} ({100 * n_free / n:.1f}%)")
    for label, outc in (("closed", 1), ("stable", 0)):
        sub = [r for r in fitted if r.get("panel_outcome") == outc]
        if sub:
            k = sum(1 for r in sub if passes(r, "rhat_max_free"))
            print(f"  Pass (free params), panel {label:6s}:   {k} / {len(sub)}")

    combined = Path(directory) / "summary.json"
    combined.write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {combined}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--summarize")
    a = ap.parse_args()
    if a.summarize:
        summarize(a.summarize)
    else:
        run_shard(a.shard or 0, a.of)


if __name__ == "__main__":
    main()
