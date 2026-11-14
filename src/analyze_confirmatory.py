"""
Analyzes the 300-institution confirmatory test, exactly as specified in
"sampling protocol.md" at the root of this repository. Read that file
first -- this script implements its outcome definition, its
pre-specified measures, its contingency triggers and its
critical-slowing-down comparator rule, and changes none of them.

It runs in two steps, which the workflow analyze_confirmatory.yml runs
as two separate jobs, each ending in its own commit, so the order is
visible in the repository's history:

1. comparator. Computes the critical-slowing-down comparator for every
   scored institution from FY2009-FY2019 data only, and commits the
   flags to "data/confirmatory/comparator flags.json". Nothing in this
   step opens any file from after fiscal year 2019.

2. outcomes. Refuses to run unless the comparator flags are already
   committed. Then it downloads every IPEDS header (HD) file released
   after fiscal year 2019, records each institution's outcome under the
   protocol's definition, and computes every pre-specified measure and
   trigger. It writes "data/confirmatory/outcomes.csv" (one row per
   institution looked up) and "data/confirmatory/results.json".

IMPLEMENTATION DETAILS THE PROTOCOL LEAVES OPEN, fixed here before any
outcome is looked up:

- Comparator with missing years: the 6-year rolling window slides over
  the years present, in order, so each window holds 6 observed values
  and no value is interpolated. The straight-line trend is fitted
  against fiscal year over the years present.
- Lag-1 autocorrelation in a window is the Pearson correlation between
  each value and the next one in that window. Variance is the
  population variance (Kendall's tau is unaffected by the choice).
  Kendall's tau is tau-b against window order. If either tau is
  undefined (a window with no variation), the comparator is recorded as
  not computable for that institution.
- Outcome codes: CLOSEDAT counts when it holds a date (any value other
  than blank or a negative IPEDS code such as -2, "not applicable");
  DEATHYR and MERGEID count when they hold a positive number.
- An institution that disappears from later HD files without any of
  the three is surviving under the definition as written; such
  institutions are listed separately, with their flags, and are not
  reclassified.
- Bootstrap for J: institutions are resampled with replacement; a
  resample with no closures or no survivors has no J and is dropped,
  and the number dropped is reported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_confirmatory as sc  # noqa: E402

ROOT = sc.ROOT
CONF = ROOT / "data" / "confirmatory"
COMPARATOR_PATH = CONF / "comparator flags.json"
OUTCOMES_PATH = CONF / "outcomes.csv"
RESULTS_PATH = CONF / "results.json"

FIRST_HD_YEAR = 2020          # the first header file released after FY2019
LAST_HD_YEAR_TRIED = 2026     # later years are tried and recorded as not found
MIN_YEARS = 8                 # of 11
ROLL = 6
BOOT_N = 10_000
BOOT_SEED = 20261112
Z = 1.959963984540054


# ------------------------------------------------------------ sample

def scored_institutions() -> list[dict]:
    """Every finalized, filled slot, with its seed-7 flag, in slot order."""
    out = {}
    for f in sorted(sc.SCORES_DIR.glob("batch_*.json")):
        for s in json.loads(f.read_text())["finalized slots"]:
            if s.get("unitid"):
                out[s["slot"]] = s
    rows = [out[k] for k in sorted(out)]
    assert len({r["unitid"] for r in rows}) == len(rows), "an institution fills two slots"
    return rows


def skipped_institutions(scored_ids: set[str]) -> list[dict]:
    """Every institution skipped for insufficient data in a finalized slot's record."""
    out = {}
    with open(sc.DRAW_LOG_PATH, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["status"] != "skipped at scoring" or not r["reason"].startswith("insufficient data"):
                continue
            if r["unitid"] in scored_ids or r["unitid"] in out:
                continue
            check = "stability" if "stability check" in r["reason"] else "data"
            out[r["unitid"]] = {"unitid": r["unitid"], "name": r["name"], "sector": r["sector"],
                                "state": r["state"], "slot": int(r["slot"]),
                                "failed check": check, "reason": r["reason"].rsplit("; batch", 1)[0]}
    return list(out.values())


# ------------------------------------------------------- comparator

def csd_indicators(years: list[int], values: list[float]) -> dict:
    from scipy.stats import kendalltau
    n = len(values)
    rec = {"years used": n}
    if n < MIN_YEARS:
        rec["computable"] = False
        rec["why not"] = f"only {n} of 11 years present (needs {MIN_YEARS})"
        return rec
    x = np.asarray(years, float)
    y = np.asarray(values, float)
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    var, ac1 = [], []
    for i in range(n - ROLL + 1):
        w = resid[i:i + ROLL]
        var.append(float(np.var(w)))
        a, b = w[:-1], w[1:]
        ac1.append(float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else float("nan"))
    idx = list(range(len(var)))
    tv = kendalltau(idx, var).statistic if len(set(var)) > 1 else float("nan")
    ta = (kendalltau(idx, ac1).statistic
          if not any(math.isnan(v) for v in ac1) and len(set(ac1)) > 1 else float("nan"))
    rec.update(windows=len(var), variance=var, lag1_autocorrelation=ac1,
               tau_variance=None if math.isnan(tv) else float(tv),
               tau_autocorrelation=None if math.isnan(ta) else float(ta))
    if math.isnan(tv) or math.isnan(ta):
        rec["computable"] = False
        rec["why not"] = "a trend is undefined (no variation across windows)"
        return rec
    rec["computable"] = True
    rec["flag"] = bool(tv > 0 and ta > 0)
    return rec


def cmd_comparator(compact: str, finance: str) -> None:
    sc.verify_frozen()
    import fetch_live_data as fld
    fld.use_bulk_scorecard(compact)
    evals = sc.load_evaluations()
    window = [f"{y}-{str(y + 1)[2:]}" for y in range(sc.START_YEAR, sc.END_YEAR)]
    fiscal = [y + 1 for y in range(sc.START_YEAR, sc.END_YEAR)]

    manifest = json.loads((Path(finance) / "manifest.json").read_text())
    # Batch 1 predates the finance-file cache and recorded no hashes; every
    # later batch recorded the SHA-256 of each copy it scored from.
    finance_check = {}
    for bf in sorted(sc.SCORES_DIR.glob("batch_*.json")):
        recorded = json.loads(bf.read_text()).get("finance files (sha256)")
        if recorded is None:
            finance_check[bf.name] = "no finance hashes recorded"
            continue
        finance_check[bf.name] = {
            "identical": sum(1 for k in manifest if recorded.get(k) == manifest[k]),
            "different": sorted(k for k in manifest if k in recorded and recorded[k] != manifest[k]),
            "not recorded in that batch": sorted(k for k in manifest if k not in recorded)}

    records = []
    for s in scored_institutions():
        u = s["unitid"]
        ev = evals.get(u, {})
        form = ev.get("finance form sector", ev.get("sector", s["sector"]))
        E, _, _, Wt, mask, _ = fld.parse_live_finance(u, window, Path(finance) / form, sector=form)
        yrs, margin = [], []
        for fy, ok, rev, exp in zip(fiscal, mask, E, Wt):
            if ok and not math.isnan(rev) and not math.isnan(exp) and exp != 0:
                yrs.append(fy)
                margin.append(float((rev - exp) / exp))
        enr_y, enr = [], []
        for fy, cal in zip(fiscal, range(sc.START_YEAR, sc.END_YEAR)):
            try:
                v = fld._bulk_scorecard_fields(u, cal)[f"{cal}.student.size"]
            except KeyError:
                v = None
            if v is not None:
                enr_y.append(fy)
                enr.append(float(v))
        records.append({
            "slot": s["slot"], "unitid": u, "name": s["name"], "finance form": form,
            "operating margin": {"fiscal years": yrs, "values": margin, **csd_indicators(yrs, margin)},
            "enrollment (secondary, not used in R4)": {"fiscal years": enr_y, "values": enr,
                                                       **csd_indicators(enr_y, enr)},
        })
        om = records[-1]["operating margin"]
        print(f"{u} {s['name'][:40]:40s} years={om['years used']:2d} "
              f"flag={om.get('flag', 'not computable')}")

    flagged = sum(1 for r in records if r["operating margin"].get("flag"))
    computable = sum(1 for r in records if r["operating margin"]["computable"])
    out = {
        "protocol": "sampling protocol.md, section 'Critical-slowing-down comparator: flag rule'",
        "written at (UTC)": datetime.now(timezone.utc).isoformat(),
        "note": "Computed from FY2009-FY2019 data only, before any outcome was looked up. "
                "No file from after fiscal year 2019 was opened.",
        "implementation details": __doc__.split("IMPLEMENTATION DETAILS")[1].split('"""')[0].strip(),
        "frozen file hashes": sc.verify_frozen(),
        "finance files": {"count": len(manifest),
                          "compared with each scoring batch's copies": finance_check},
        "scored institutions": len(records),
        "comparator computable": computable,
        "comparator flagged": flagged,
        "institutions": records,
    }
    COMPARATOR_PATH.write_text(json.dumps(out, indent=1))
    print(f"\nComparator: computable for {computable} of {len(records)}; flagged {flagged}.")
    for name, chk in finance_check.items():
        if isinstance(chk, dict) and chk["different"]:
            print(f"Finance files that differ from {name}'s copies:", ", ".join(chk["different"]))


# --------------------------------------------------------- outcomes

def committed(path: Path) -> str:
    rel = str(path.relative_to(ROOT))
    h = subprocess.run(["git", "log", "-1", "--format=%H %cI", "--", rel], cwd=ROOT,
                       capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if not h or dirty:
        raise SystemExit(f"{rel} is not committed. The comparator must be committed before any "
                         "outcome is looked up; run the comparator step first.")
    return h


def download_hd(year: int):
    import requests
    table = f"HD{year}"
    for url in (f"https://nces.ed.gov/ipeds/datacenter/data/{table}.zip",
                f"https://nces.ed.gov/ipeds/complete-data-files/{table}.zip"):
        for attempt in range(4):
            try:
                resp = requests.get(url, timeout=180)
                if resp.status_code == 404:
                    break
                resp.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    names = sorted((n for n in zf.namelist() if n.lower().endswith(".csv")),
                                   key=lambda n: ("_rv" in n.lower(), len(n)))
                    if not names:
                        break
                    data = zf.read(names[0])
                return {"table": table, "url": url, "file": names[0],
                        "zip sha256": hashlib.sha256(resp.content).hexdigest(), "csv": data}
            except Exception as e:  # retried, then the next address
                print(f"{table}: {type(e).__name__}: {e} (attempt {attempt + 1}, {url})")
    return None


def positive_number(v: str) -> bool:
    try:
        return float(v) > 0
    except ValueError:
        return False


def has_date(v: str) -> bool:
    v = v.strip()
    if not v:
        return False
    try:
        return float(v) >= 0  # a bare number that is not a negative code
    except ValueError:
        return True           # a date string such as 6/30/2021


def wilson(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return [c - h, c + h]


def measures(flag: np.ndarray, closed: np.ndarray) -> dict:
    E = int(closed.sum())
    N = len(flag)
    tp = int((flag & closed).sum())
    fp = int((flag & ~closed).sum())
    nflag = tp + fp
    S = tp / E if E else None
    F = fp / (N - E) if N - E else None
    prec = tp / nflag if nflag else None
    rate = E / N if N else None
    J = (S - F) if S is not None and F is not None else None
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
    J_ci = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))] if boots else [None, None]
    return {"N": N, "E (closed or merged)": E, "flagged": nflag,
            "true positives": tp, "false positives": fp,
            "sensitivity S": S, "S 95% Wilson": wilson(tp, E),
            "false-alarm rate F": F, "F 95% Wilson": wilson(fp, N - E),
            "precision": prec, "precision 95% Wilson": wilson(tp, nflag),
            "closure rate": rate, "lift": (prec / rate) if prec is not None and rate else None,
            "J": J, "J 95% bootstrap": J_ci, "bootstrap resamples dropped (no J)": dropped}


def cmd_outcomes() -> None:
    sc.verify_frozen()
    comp_commit = committed(COMPARATOR_PATH)
    comp = json.loads(COMPARATOR_PATH.read_text())
    scored = scored_institutions()
    scored_ids = {s["unitid"] for s in scored}
    skipped = skipped_institutions(scored_ids)
    all_ids = scored_ids | {s["unitid"] for s in skipped}

    # Every post-2019 header file NCES publishes.
    files, seen = [], {}
    for year in range(FIRST_HD_YEAR, LAST_HD_YEAR_TRIED + 1):
        got = download_hd(year)
        if got is None:
            print(f"HD{year}: not published (or not reachable); recorded as not found.")
            files.append({"table": f"HD{year}", "found": False})
            continue
        reader = csv.DictReader(io.StringIO(got["csv"].decode("latin-1")))
        reader.fieldnames = [f.strip().lstrip("\ufeff").lstrip("ï»¿").upper() for f in reader.fieldnames]
        cols = [c for c in ("CLOSEDAT", "DEATHYR", "MERGEID") if c in reader.fieldnames]
        n = 0
        for row in reader:
            u = row["UNITID"].strip()
            if u not in all_ids:
                continue
            n += 1
            seen.setdefault(u, {})[year] = {c: (row.get(c) or "").strip() for c in cols}
        files.append({"table": got["table"], "found": True, "url": got["url"], "file": got["file"],
                      "zip sha256": got["zip sha256"], "outcome columns present": cols,
                      "sample institutions in it": n})
        print(f"{got['table']}: {n} sample institutions; columns {cols}")
    found_years = [int(f["table"][2:]) for f in files if f["found"]]
    if not found_years:
        raise SystemExit("No post-2019 header file could be downloaded. Nothing written.")
    latest = max(found_years)

    def outcome(u: str) -> dict:
        hist = seen.get(u, {})
        ev = []
        for y in sorted(hist):
            r = hist[y]
            if has_date(r.get("CLOSEDAT", "")):
                ev.append(f"HD{y} CLOSEDAT={r['CLOSEDAT']}")
            if positive_number(r.get("DEATHYR", "")):
                ev.append(f"HD{y} DEATHYR={r['DEATHYR']}")
            if positive_number(r.get("MERGEID", "")):
                ev.append(f"HD{y} MERGEID={r['MERGEID']}")
        return {"closed or merged": bool(ev), "evidence": "; ".join(ev),
                "last HD file present": f"HD{max(hist)}" if hist else "none after HD2019",
                "vanished without a closure, deletion or merger record":
                    (not ev) and (latest not in hist)}

    comp_by = {r["unitid"]: r["operating margin"] for r in comp["institutions"]}
    rows = []
    for s in scored:
        o = outcome(s["unitid"])
        c = comp_by.get(s["unitid"], {})
        rows.append({"group": "scored", "slot": s["slot"], "unitid": s["unitid"], "name": s["name"],
                     "sector": s["sector"], "state": s["state"],
                     "tracker probability": round(s["probability"], 4),
                     "tracker flag": s["flag"],
                     "comparator": ("flagged" if c.get("flag") else "not flagged")
                     if c.get("computable") else "not computable",
                     "skip reason": "", **o})
    for s in skipped:
        o = outcome(s["unitid"])
        rows.append({"group": f"skipped ({s['failed check']} check)", "slot": s["slot"],
                     "unitid": s["unitid"], "name": s["name"], "sector": s["sector"],
                     "state": s["state"], "tracker probability": "", "tracker flag": "",
                     "comparator": "", "skip reason": s["reason"], **o})
    with open(OUTCOMES_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    sr = [r for r in rows if r["group"] == "scored"]
    flag = np.array([r["tracker flag"] == "high_risk" for r in sr])
    closed = np.array([r["closed or merged"] for r in sr])
    tracker = measures(flag, closed)

    comp_rows = [r for r in sr if r["comparator"] != "not computable"]
    cf = np.array([r["comparator"] == "flagged" for r in comp_rows])
    cc = np.array([r["closed or merged"] for r in comp_rows])
    ctf = np.array([r["tracker flag"] == "high_risk" for r in comp_rows])
    comparator = measures(cf, cc) if comp_rows else None
    tracker_same_set = measures(ctf, cc) if comp_rows else None

    E = tracker["E (closed or merged)"]
    lo = tracker["J 95% bootstrap"][0]
    S, F = tracker["sensitivity S"], tracker["false-alarm rate F"]
    underpowered = E < 10
    triggers = {
        "underpowered (E below 10)": underpowered,
        "R1 no discrimination (J lower bound <= 0)": None if underpowered else (lo is None or lo <= 0),
        "R2 low sensitivity (S < 0.50)": None if underpowered else (S is not None and S < 0.50),
        "R3 excess false alarms (F > 0.30)": F is not None and F > 0.30,
        "R4 no advantage over critical slowing down (comparator J >= tracker J)":
            None if underpowered or not comp_rows or comparator["J"] is None
            else comparator["J"] >= tracker_same_set["J"],
    }
    passed = (not underpowered and lo is not None and lo > 0
              and S is not None and S >= 0.50 and F is not None and F <= 0.30)

    def rate(group_rows):
        k = sum(1 for r in group_rows if r["closed or merged"])
        n = len(group_rows)
        return {"N": n, "closed or merged": k, "rate": k / n if n else None, "95% Wilson": wilson(k, n)}

    skip_rows = [r for r in rows if r["group"].startswith("skipped")]
    broken = {"scored": rate(sr), "all skipped for insufficient data": rate(skip_rows),
              "skipped:
