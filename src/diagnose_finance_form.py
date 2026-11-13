"""
Diagnostic: why do some confirmatory candidates fail with "insufficient
parsed finance data"? Fits no model, changes nothing, commits nothing,
and looks up no outcome.

Batch 2 of the confirmatory run recorded 43 candidates as failing the
data check with "insufficient parsed finance data" or "finance data
incomplete". Most are branch campuses (Penn State, Ohio University,
UConn, Kent State, Pitt and others), but the list also includes main
campuses such as UCLA, UC Irvine, Temple and Penn State's main campus.
There are two possible explanations, and they matter differently:

1. PARENT/CHILD REPORTING. IPEDS lets a system report finance for its
   campuses under one parent institution, in which case a campus has no
   finance row of its own. That is a genuine absence of the institution's
   own data, and the data check is right to skip it.

2. FORM MISMATCH. The pipeline chooses the finance form by sector
   (public -> F1A, the GASB form; private -> F2, the FASB form;
   for-profit -> F3). Some public institutions -- Pennsylvania's
   "state-related" universities are the best-known case -- file the
   FASB form F2 instead. Their data exists, but the pipeline looks for
   it in the wrong file. That would be a pipeline limitation, not a data
   gap, and skipping those institutions would bias the sample.

For every such candidate, this script reports its HD2019 finance
parent/child fields and, for each fiscal year in the scoring window,
which of the three finance files (F1A, F2, F3) contains a row for it.

Usage (GitHub Actions, via diagnose_finance_form.yml):
    cd src
    python diagnose_finance_form.py
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

import fetch_live_data as fld
import score_confirmatory as sc

FORMS = {"public": "F1A", "private": "F2", "forprofit": "F3"}
OUT = Path("../reports/finance_form")


def hd2019_rows(unitids: set[str]) -> dict[str, dict]:
    path = Path(__file__).resolve().parent / "draw confirmatory sample.py"
    spec = importlib.util.spec_from_file_location("draw_confirmatory_sample", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    csv_bytes, _ = mod.download_hd()
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("latin-1")))
    reader.fieldnames = [f.strip().lstrip("\ufeff").lstrip("ï»¿").upper() for f in reader.fieldnames]
    return {row["UNITID"].strip(): row for row in reader if row["UNITID"].strip() in unitids}


def main():
    evals = sc.load_evaluations()
    targets = {u: e for u, e in evals.items()
               if e["result"] == "fail" and "finance" in (e.get("gap") or "")}
    print(f"{len(targets)} candidates failed the data check on finance data.")

    hd = hd2019_rows(set(targets))
    years = list(range(sc.START_YEAR, sc.END_YEAR))
    present = {u: {} for u in targets}
    for sector, form in FORMS.items():
        for y in years:
            d = fld.download_ipeds_finance_bulk(y, dest_dir=Path("/tmp/finance_form") / sector, sector=sector)
            if d is None:
                print(f"Could not download {form} {y}")
                continue
            for f in Path(d).glob("*.csv"):
                with open(f, encoding="latin-1") as fh:
                    for row in csv.DictReader(fh):
                        u = (row.get("UNITID") or "").strip()
                        if u in present:
                            present[u].setdefault(form, []).append(y)

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for u, e in sorted(targets.items(), key=lambda kv: kv[1]["name"]):
        h = hd.get(u, {})
        r = {"unitid": u, "name": e["name"], "pipeline sector": e["sector"],
             "pipeline form": FORMS[e["sector"]], "gap": e.get("gap"),
             "HD2019 PRCH_F": h.get("PRCH_F"), "HD2019 IDX_F": h.get("IDX_F"),
             "HD2019 CONTROL": h.get("CONTROL"),
             "rows found by form": {k: sorted(v) for k, v in present[u].items()}}
        rows.append(r)
    (OUT / "finance_form.json").write_text(json.dumps(rows, indent=2))

    print("\nFINANCE FORM CHECK (pipeline years; 2018 = FY2019)")
    print("PRCH_F is HD2019's finance parent/child indicator; IDX_F is the parent's UNITID when reported by a parent.")
    print("=" * 118)
    print(f"{'Institution':40s} {'sector':>9s} {'uses':>4s} {'PRCH_F':>6s} {'IDX_F':>7s}  rows found (form: years)")
    for r in rows:
        found = "; ".join(f"{k}: {v[0]}-{v[-1]} ({len(v)})" for k, v in r["rows found by form"].items()) or "none"
        print(f"{r['name'][:40]:40s} {r['pipeline sector']:>9s} {r['pipeline form']:>4s} "
              f"{str(r['HD2019 PRCH_F']):>6s} {str(r['HD2019 IDX_F']):>7s}  {found}")
    print("=" * 118)
    mismatch = [r for r in rows if any(k != r["pipeline form"] for k in r["rows found by form"])]
    nowhere = [r for r in rows if not r["rows found by form"]]
    print(f"Rows found in a form other than the one the pipeline uses: {len(mismatch)}")
    print(f"No finance row in any form in any window year: {len(nowhere)}")


if __name__ == "__main__":
    main()
