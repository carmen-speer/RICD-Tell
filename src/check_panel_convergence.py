"""
Pre-scoring measurement for the confirmatory test: how often does the
protocol's convergence check pass on the 54-institution validation
panel, under the confirmatory run's conditions, and does more sampling
effort change that?

WHY THIS EXISTS: `sampling protocol.md`'s insufficient-data rule skips
any institution whose fit shows a divergent transition or any
parameter with R-hat above 1.01. The first run of this script
(2026-11-12, production settings only) found 0 of 34 fitted panel
institutions meeting R-hat <= 1.01, so the rule as committed would skip
every confirmatory candidate. Only 3 panel closures were fitted in that
run, and all 3 converged worse than almost every stable institution,
which raises the possibility that poor convergence goes with distress.
This run answers two questions before the rule is revised:

1. Does more sampling effort (1000 draws, 1000 tuning steps, 4 chains)
   make R-hat <= 1.01 reachable, and does it change any institution's
   flag relative to production settings?
2. Do closures converge worse than stable institutions, once the panel
   closures are actually fitted?

The first run's 20 failures were all closed institutions whose sector
the College Scorecard lookup could not return. This version takes each
institution's sector from the IPEDS HD2019 header file, the same source
the confirmatory draw uses, and falls back to the College Scorecard
lookup only for an institution not in HD2019. An institution absent
from HD2019 has no FY2019 data to fit and is reported as such.

CONDITIONS: FY2019 data and earlier only (start_year 2013, end_year
2019, so the last finance file is F1819), target_accept 0.9, cores 1,
the Numba backend, random seed 7, at two sampler settings: production
(300/300/2) and high (1000/1000/4). Each fit's flag comes from the
frozen classifier fit on the panel, with the governance override not
applied, exactly as in the confirmatory run.

It touches no confirmatory institution, looks up no outcome, and never
writes to data/panel/panel.json, the dashboard, or anything under
data/confirmatory/. Results go to reports/panel_convergence/ and are
uploaded as a workflow artifact.

Usage (GitHub Actions only; needs network access to NCES and the
College Scorecard, and COLLEGE_SCORECARD_API_KEY):
    cd src
    python check_panel_convergence.py --shard 0 --of 18
    python check_panel_convergence.py --summarize ../reports/panel_convergence
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import importlib.util
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
SETTINGS = {
    "production": dict(n_draws=300, n_tune=300, n_chains=2),
    "high": dict(n_draws=1000, n_tune=1000, n_chains=4),
}
COMMON = dict(target_accept=0.9, cores=1, compile_mode="NUMBA", random_seed=7, debug_param_rhat=True)

# IPEDS SECTOR codes: 1/4/7 public, 2/5/8 private nonprofit, 3/6/9 for-profit.
HD_SECTOR_TO_PIPELINE = {"1": "public", "4": "public", "7": "public",
                         "2": "private", "5": "private", "8": "private",
                         "3": "forprofit", "6": "forprofit", "9": "forprofit"}

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


def hd2019_sectors() -> dict[str, str]:
    """UNITID -> pipeline sector, from HD2019, using the draw script's own downloader."""
    path = Path(__file__).resolve().parent / "draw confirmatory sample.py"
    spec = importlib.util.spec_from_file_location("draw_confirmatory_sample", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    csv_bytes, _ = mod.download_hd()
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("latin-1")))
    reader.fieldnames = [f.strip().lstrip("\ufeff").lstrip("ï»¿").upper() for f in reader.fieldnames]
    out = {}
    for row in reader:
        code = row["SECTOR"].strip()
        if code in HD_SECTOR_TO_PIPELINE:
            out[row["UNITID"].strip()] = HD_SECTOR_TO_PIPELINE[code]
    return out


def run_shard(shard: int, of: int) -> None:
    from classifier import RICDClassifier, load_panel
    from score_institution import compute_features_for_institution
    import fetch_live_data as fld

    panel = load_panel(PANEL_PATH)
    clf = RICDClassifier()
    clf.fit(panel)
    sectors = hd2019_sectors()
    mine = [inst for i, inst in enumerate(panel) if i % of == shard]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for inst in mine:
        unitid, name = inst.unitid, inst.name
        print(f"\n{'=' * 70}\n{name} ({unitid})\n{'=' * 70}", flush=True)
        row = {"unitid": unitid, "name": name, "panel_outcome": inst.outcome,
               "in HD2019": unitid in sectors, "fits": {}}

        sector = sectors.get(unitid) or fld.detect_sector(unitid)
        if sector is None:
            row["status"] = "no sector (not in HD2019, not in College Scorecard)"
            results.append(row)
            continue
        row["sector"] = sector

        for label, settings in SETTINGS.items():
            print(f"\n--- {label} settings: {settings} ---", flush=True)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(Tee(sys.stdout, buf)):
                    feats = compute_features_for_institution(
                        unitid, name, sector=sector,
                        start_year=START_YEAR_OVERRIDES.get(unitid, START_YEAR),
                        end_year=END_YEAR, **settings, **COMMON)
            except Exception as e:  # recorded, never retried or rescued
                row["fits"][label] = {"status": f"error: {type(e).__name__}: {e}", **parse_log(buf.getvalue())}
                continue
            fit = parse_log(buf.getvalue())
            if feats is None:
                fit["status"] = "insufficient_data" if fit["divergences"] is None else "fitted, no features"
            else:
                fit["status"] = "fitted"
                feats.governance_flag = False
                X = clf.scaler.transform(feats.to_vector().reshape(1, -1))
                fit["probability"] = float(clf.model.predict_proba(X)[0, 1])
                fit["flag"] = "high_risk" if int(clf.model.predict(X)[0]) == 1 else "stable"
            row["fits"][label] = fit
            if fit["status"] == "insufficient_data":
                break  # same data at any setting; no point refitting

        statuses = {f.get("status") for f in row["fits"].values()}
        row["status"] = "insufficient_data" if statuses == {"insufficient_data"} else "measured"
        results.append(row)
        (OUT_DIR / f"shard_{shard}_of_{of}.json").write_text(json.dumps(results, indent=2))

    path = OUT_DIR / f"shard_{shard}_of_{of}.json"
    path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {path} ({len(results)} institutions)")


def passes(fit: dict | None) -> bool:
    if not fit or fit.get("divergences") is None:
        return False
    r = fit.get("rhat_max_free")
    return fit["divergences"] == 0 and r is not None and r <= RHAT_LIMIT


def summarize(directory: str) -> None:
    rows = []
    for p in sorted(Path(directory).rglob("shard_*.json")):
        rows.extend(json.loads(p.read_text()))
    rows.sort(key=lambda r: r["name"])

    def fmt(v, spec=".4f"):
        return "-" if v is None else format(v, spec)

    print("\nPANEL CONVERGENCE CHECK, FY2019 window, seed 7: production (300/300/2) vs high (1000/1000/4)")
    print("R-hat is the maximum over sampled parameters; 'pass' = 0 divergences and R-hat <= 1.01")
    print("=" * 118)
    print(f"{'Institution':32s} {'outcome':>7s} {'status':>17s} | {'P div':>5s} {'P rhat':>7s} {'P flag':>9s} "
          f"{'P pass':>6s} | {'H div':>5s} {'H rhat':>7s} {'H flag':>9s} {'H pass':>6s} | {'flags':>6s}")
    for r in rows:
        outcome = {1: "closed", 0: "stable"}.get(r.get("panel_outcome"), "?")
        P, H = r.get("fits", {}).get("production"), r.get("fits", {}).get("high")
        cells = []
        for f in (P, H):
            if f and f.get("divergences") is not None:
                cells += [str(f["divergences"]), fmt(f.get("rhat_max_free")), f.get("flag", "-"),
                          "yes" if passes(f) else "no"]
            else:
                cells += ["-", "-", "-", "-"]
        same = "-"
        if P and H and P.get("flag") and H.get("flag"):
            same = "same" if P["flag"] == H["flag"] else "DIFFER"
        status = r.get("status", "")[:17]
        print(f"{r['name'][:32]:32s} {outcome:>7s} {status:>17s} | {cells[0]:>5s} {cells[1]:>7s} {cells[2]:>9s} "
              f"{cells[3]:>6s} | {cells[4]:>5s} {cells[5]:>7s} {cells[6]:>9s} {cells[7]:>6s} | {same:>6s}")
    print("=" * 118)

    measured = [r for r in rows if r.get("status") == "measured"]
    print(f"Institutions in panel:                       {len(rows)}")
    print(f"Not in HD2019 (closed before the window):    {sum(1 for r in rows if not r.get('in HD2019'))}")
    print(f"Insufficient data in FY2019 window:          {sum(1 for r in rows if r.get('status') == 'insufficient_data')}")
    print(f"No sector found:                             {sum(1 for r in rows if str(r.get('status', '')).startswith('no sector'))}")
    print(f"Measured:                                    {len(measured)}")
    for label in SETTINGS:
        for name, outc in (("all", None), ("closed", 1), ("stable", 0)):
            sub = [r for r in measured if (outc is None or r.get("panel_outcome") == outc)
                   and r["fits"].get(label, {}).get("divergences") is not None]
            if not sub:
                continue
            k = sum(1 for r in sub if passes(r["fits"][label]))
            rh = sorted(r["fits"][label]["rhat_max_free"] for r in sub if r["fits"][label].get("rhat_max_free") is not None)
            med = rh[len(rh) // 2] if rh else None
            div = sum(1 for r in sub if r["fits"][label]["divergences"] > 0)
            print(f"  {label:10s} {name:6s}: pass {k:2d} / {len(sub):2d}; median R-hat {fmt(med)}; "
                  f"max R-hat {fmt(rh[-1] if rh else None)}; with divergences {div}")
    both = [r for r in measured if r["fits"].get("production", {}).get("flag") and r["fits"].get("high", {}).get("flag")]
    differ = [r["name"] for r in both if r["fits"]["production"]["flag"] != r["fits"]["high"]["flag"]]
    print(f"Flag same at both settings:                  {len(both) - len(differ)} / {len(both)}"
          + (f"  (differ: {', '.join(differ)})" if differ else ""))

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
