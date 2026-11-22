"""
Item 22a, step four: the nursing test (protocols/nursing and pharmacy
protocol.md, sections 2 to 5, Amendment 1 and Amendment 2). Do registered-
nursing programs in the bottom decile on first-time NCLEX-RN pass rates
shrink severely more often than other programs?

Reads:
  data/item 22a/pass_rates.csv       the parsed board figures (step two)
  data/item 22a/name crosswalk.csv   programs matched to IPEDS unit IDs (step three)
  IPEDS Completions by program, C2008_A to C2024_A (first majors; CIP 51.3801
      from 2010, 51.1601 before; associate AWLEVEL 3, bachelor's AWLEVEL 5)
  IPEDS header files HD2013 onward, for the closure rule of ending types
      protocol.md (documented closures, grounds a or b, as in src/ending types.py)
The 2025 completions file (C2025_A) is never opened: whether NCES serves it
is recorded by a HEAD request only (Amendment 2, decision 4).

Order of work, so that nothing about the outcome shapes the units or flags:
  1. levels are set (Amendment 2, decision 1) from whether a unit has any
     first-major registered-nursing completions at each level in 2014 to
     2020, and written to data/item 22a/level_assignments.csv;
  2. the board rows are reduced to one row per unit, level and exam year
     (renamed programs counted once, decision 6; campuses combined,
     Amendment 1, decision 2), the 20-taker threshold applied (decision 9)
     and the flags set (deciles within state, level and exam year among the
     test's programs);
  3. only then are completions in y and y + 3 (and y + 4, report-only)
     compared and the verdict drawn.

Outputs:
  data/item 22a/level_assignments.csv   step 1
  data/item 22a/program_years.csv       one row per program-year in the test
  data/item 22a/results.json            the results, sources, leave-outs, verdict

Usage (GitHub Actions only, via item22a_test.yml):
    cd src
    python item22a_test.py
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import requests
from sklearn.metrics import roc_auc_score

import meta_channel as mc
import v2_training_outcomes as coding

HERE = Path(__file__).resolve().parent
DIR = HERE.parent / "data" / "item 22a"
_o = importlib.util.spec_from_file_location("oc", HERE / "openings and closures.py")
oc = importlib.util.module_from_spec(_o)
_o.loader.exec_module(oc)

SEED, BOOT, MIN_TAKERS, CUT, DECILE = 20261121, 2000, 20, 0.6, 10.0
C_FIRST, C_LAST = 2008, 2024              # completions years read (section 5); C2025 never opened
HD_FIRST, HD_LAST = 2013, 2026            # header files for the closure rule; files from 2025 may not be served
LEVEL_YEARS = range(2014, 2021)           # Amendment 2, decision 1
DEV, TEST = range(2015, 2018), range(2018, 2022)
AWLEVEL = {3: "associate", 5: "bachelor"}
diagnostics: dict = {}          # completions years that read as empty, with raw values to see why
MIN_C_ROWS, MIN_HD_ROWS = 100000, 3000


def rn_code(year: int) -> float:
    return 51.3801 if year >= 2010 else 51.1601


def clean(v: str) -> str:
    """A cell with any spreadsheet quoting removed (="51.3801", '51.3801)."""
    return (v or "").strip().lstrip("=").strip().strip('"').strip("'").strip()


def cip_digits(v: str) -> str:
    """A CIP code as six digits, whatever its written form (51.3801, 51.380100, 513801)."""
    v = clean(v)
    if "." in v:
        a, b = v.split(".", 1)
        return (a.zfill(2) + (b + "0000")[:4]) if a.isdigit() and b.isdigit() else ""
    return v[:6] if v.isdigit() and len(v) >= 6 else ""


def code_int(v: str) -> int | None:
    v = clean(v)
    try:
        return int(float(v))
    except ValueError:
        return None


def value(v: str) -> float | None:
    v = clean(v)
    try:
        return float(v)
    except ValueError:
        return None


# ------------------------------------------------------------------ reading IPEDS
def completions() -> tuple[dict, dict, list]:
    """For each year: the set of unit IDs in the file, and first-major RN completions by (unit, level)."""
    present, rn, files = {}, {}, []
    diagnostics.clear()
    for y in range(C_FIRST, C_LAST + 1):
        got = mc.fetch(f"C{y}_A.zip", True)
        name, text = mc.first_csv(got[0])
        rows = mc.rows(text)
        if len(rows) < MIN_C_ROWS:
            raise SystemExit(f"C{y}_A yielded {len(rows)} rows; misread. Nothing recorded.")
        code = rn_code(y)
        target = cip_digits(f"{code:.4f}")
        ids, by, sample = set(), defaultdict(float), []
        for r in rows:
            u = r.get("UNITID", "")
            if not u:
                continue
            ids.add(u)
            cip, major, aw = cip_digits(r.get("CIPCODE", "")), code_int(r.get("MAJORNUM", "")), code_int(r.get("AWLEVEL", ""))
            if cip == target and len(sample) < 25:
                sample.append({k: r.get(k, "") for k in ("UNITID", "CIPCODE", "MAJORNUM", "AWLEVEL", "CTOTALT", "CTOTALM", "CTOTALW")})
            if cip != target or major != 1 or aw not in AWLEVEL:
                continue
            t = value(r.get("CTOTALT", ""))
            if t is None:      # 2008 and 2009 give men and women only
                m, w = value(r.get("CTOTALM", "")), value(r.get("CTOTALW", ""))
                t = None if m is None and w is None else (m or 0) + (w or 0)
            if t is not None:
                by[(u, AWLEVEL[aw])] += t
        present[y], rn[y] = ids, dict(by)
        if len(by) < 1000:     # every year has well over 1,000 RN programs nationally; fewer is a misread
            diagnostics[str(y)] = {"csv": name, "headings": sorted(rows[0]) if rows else [],
                                   "unit-levels read": len(by), "rows with the RN code (first 25)": sample}
        files.append({"file": f"C{y}_A", "url": got[1], "csv": name, "zip sha256": hashlib.sha256(got[0]).hexdigest(),
                      "rows": len(rows), "CIP code": f"{code:.4f}", "units with RN first-major completions": len(by)})
        print(f"C{y}_A", len(rows), "rows;", len(by), "unit-levels with RN completions", flush=True)
    return present, rn, files


def c2025_served() -> dict:
    out = {}
    for base in mc.BASES:
        url = base + "C2025_A.zip"
        try:
            out[url] = requests.head(url, timeout=60, allow_redirects=True).status_code
        except requests.RequestException as e:
            out[url] = str(e)[:200]
    return {"HEAD status by address (file not opened)": out, "served": any(v == 200 for v in out.values())}


def headers(ids: set) -> tuple[dict, list, list]:
    rows, used, missing = defaultdict(dict), [], []
    for y in range(HD_FIRST, HD_LAST + 1):
        try:
            hd = coding.download_hd(y)
        except SystemExit:
            if y < 2025:
                raise SystemExit(f"HD{y} could not be downloaded; a gap mid-span would misdate closures. Nothing recorded.")
            missing.append(f"HD{y}")
            continue
        t, _ = oc.read_table(hd["csv"])
        if len(t) < MIN_HD_ROWS:
            raise SystemExit(f"HD{y} yielded {len(t)} institutions; misread. Nothing recorded.")
        for u in ids:
            if u in t:
                rows[u][y] = t[u]
        used.append({"file": f"HD{y}", "url": hd["url"], "zip sha256": hd["zip sha256"], "institutions read": len(t)})
    return rows, used, missing


def closure_year(ids: list[str], hd: dict, years: list) -> int | None:
    """Documented closure (grounds a or b, not a merger), as in src/ending types.py. For a joined series
    (several IDs over time), the ID present latest decides."""
    have = [u for u in ids if hd.get(u)]
    if not have:
        return None
    u = max(have, key=lambda i: max(hd[i]))
    e = oc.exit_of(u, hd[u], years)
    if not e or "year" not in e:
        return None
    g = e["grounds"]
    return e["year"] if ("a" in g or "b" in g) and "c" not in g else None


# ------------------------------------------------------------------ helpers
def edition_year(source: str) -> int:
    return max(int(x) for x in re.findall(r"(?:19|20)\d\d", source))


def percentile(values: dict, k) -> float:
    x = values[k]
    vs = list(values.values())
    return round(100 * (sum(v < x for v in vs) + 0.5 * sum(v == x for v in vs)) / len(vs), 1)


def num(v: str):
    v = (v or "").strip()
    return float(v) if v else None


# ------------------------------------------------------------------ main
def main() -> None:
    board = list(csv.DictReader(open(DIR / "pass_rates.csv", encoding="utf-8")))
    cw = {(r["state"], r["level"], r["board_section"], r["board_program"]): r
          for r in csv.DictReader(open(DIR / "name crosswalk.csv", encoding="utf-8"))}

    for stale in ("results.json", "program_years.csv", "level_assignments.csv", "completions_read_check.json"):
        (DIR / stale).unlink(missing_ok=True)      # no earlier output survives a new run
    present, rn, c_files = completions()
    if diagnostics:
        (DIR / "completions_read_check.json").write_text(json.dumps({
            "note": "Completions years that read as empty or nearly so. The test was not run and no result "
                    "was written; the raw values below show how these files write the fields the test reads.",
            "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "years": diagnostics, "sources": c_files}, indent=1) + "\n", encoding="utf-8")
        print("Completions misread in", sorted(diagnostics), "; test not run. See completions_read_check.json.")
        return
    served = c2025_served()

    def comp(unit: str, level: str, y: int):
        """Completions of a unit key (IDs joined by ';' form one series) at a level in year y;
        None if no ID of the unit is in that year's file."""
        ids = unit.split(";")
        if not any(i in present.get(y, ()) for i in ids):
            return None
        return sum(rn[y].get((i, level), 0.0) for i in ids)

    # ---- step 1: rows kept, and levels (Amendment 2, decision 1)
    # a unit ID that also appears in a joined series (IDs separated by ';') is read as that series
    joined = {i: c["unitid"] for c in cw.values() if ";" in c["unitid"] for i in c["unitid"].split(";")}
    left_out, kept = [], []
    for r in board:
        c = cw.get((r["state"], r["level"], r["board_section"], r["program"]))
        if c is None or not c["unitid"]:
            left_out.append({"state": r["state"], "program": r["program"], "exam year": r["exam_year"],
                             "reason": (c or {}).get("note", "") or "not matched"})
            continue
        kept.append((r, joined.get(c["unitid"], c["unitid"])))
    level_of, assignments = {}, []
    for unit in sorted({u for r, u in kept if not r["level"]}):
        has = {lv: any((comp(unit, lv, y) or 0) > 0 for y in LEVEL_YEARS) for lv in ("associate", "bachelor")}
        got = [lv for lv, h in has.items() if h]
        level_of[unit] = got[0] if len(got) == 1 else None
        assignments.append({"unitid": unit, "associate completions 2014-2020": has["associate"],
                            "bachelor completions 2014-2020": has["bachelor"],
                            "level": level_of[unit] or "left out (both levels or neither)"})
    with open(DIR / "level_assignments.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(assignments[0]) if assignments else ["unitid", "level"])
        w.writeheader()
        w.writerows(assignments)

    # ---- step 2: one row per unit, level and exam year
    groups = defaultdict(list)
    for r, unit in kept:
        lv = r["level"] or level_of.get(unit)
        if not lv:
            left_out.append({"state": r["state"], "program": r["program"], "exam year": r["exam_year"],
                             "reason": "no level from the board, and IPEDS shows both levels or neither (Amendment 2, decision 1)"})
            continue
        groups[(r["state"], unit, lv, int(r["exam_year"]))].append(r)
    # a board name "appears in" an edition if that edition gives it for any year
    in_edition = defaultdict(set)
    for r in board:
        for src in r["sources"].split("; "):
            in_edition[(r["state"], src)].add(r["program"])
    renamed_dropped, units = [], {}
    for key, rs in groups.items():
        srcs = {s for r in rs for s in r["sources"].split("; ")}
        newest = max(srcs, key=edition_year)
        keep = [r for r in rs if r["program"] in in_edition[(key[0], newest)]]
        renamed_dropped += [{"state": key[0], "unitid": key[1], "level": key[2], "exam year": key[3],
                             "board name dropped": r["program"], "newest edition": newest} for r in rs if r not in keep]
        st = key[0]
        rates = [num(r["pass_rate"]) for r in keep]
        tested = [num(r["tested"]) for r in keep]
        if st == "OK":
            rate, n = sum(rates) / len(rates), None            # unweighted mean (Amendment 1, decision 2)
        elif all(t is not None for t in tested):
            n = sum(tested)
            rate = 100 * sum(p * t / 100 for p, t in zip(rates, tested)) / n if n else None
        elif len(keep) == 1:
            rate, n = rates[0], None                           # broken count: printed rate alone (decision 9)
        else:
            left_out.append({"state": st, "program": "; ".join(r["program"] for r in keep), "exam year": key[3],
                             "reason": "campuses to combine, one without a usable count"})
            continue
        notes = sorted({r["note"] for r in keep if "October" in r["note"]})
        units[key] = {"rate": rate, "tested": n, "board programs": [r["program"] for r in keep],
                      "exam year note": "; ".join(notes)}

    # threshold (decision 9): takers in exam year e, or completions in e where no count is given
    test_units = {}
    for (st, unit, lv, e), u in units.items():
        if u["rate"] is None:
            continue
        if u["tested"] is not None:
            size, basis = u["tested"], "first-time takers"
        else:
            size, basis = comp(unit, lv, e), "IPEDS completions (no count given)"
        if size is None or size < MIN_TAKERS:
            continue
        test_units[(st, unit, lv, e)] = u | {"threshold size": size, "threshold basis": basis}
    pools = defaultdict(dict)
    for (st, unit, lv, e), u in test_units.items():
        pools[(st, lv, e)][unit] = u["rate"]
    for (st, unit, lv, e), u in test_units.items():
        p = percentile(pools[(st, lv, e)], unit)
        u.update(percentile=p, flagged=p <= DECILE, score=100 - p, pool=len(pools[(st, lv, e)]))

    # ---- step 3: outcomes
    hd_ids = {i for (_, unit, _, _) in test_units for i in unit.split(";")}
    hd, hd_files, hd_missing = headers(hd_ids)
    hd_years = sorted({y for rows in hd.values() for y in rows} | {int(f["file"][2:]) for f in hd_files})

    def national(lv: str, y: int, h: int) -> float | None:
        a, b = rn[y], rn.get(y + h)
        if b is None:
            return None
        both = [u for (u, l), v in a.items() if l == lv and v > 0 and (u, lv) in b]
        den = sum(a[(u, lv)] for u in both)
        return sum(b[(u, lv)] for u in both) / den if den else None

    nat = {(lv, y, h): national(lv, y, h) for lv in ("associate", "bachelor") for y in list(DEV) + list(TEST)
           for h in (3, 4) if y + h <= C_LAST}
    rows, zero_base, missing_later = [], [], []
    for (st, unit, lv, e), u in sorted(test_units.items()):
        y = e + 1
        if y not in DEV and y not in TEST:
            continue
        c0 = comp(unit, lv, y)
        if c0 is None:
            missing_later.append({"state": st, "unitid": unit, "level": lv, "base year": y, "why": "unit not in the base year's file"})
            continue
        if c0 == 0:
            zero_base.append({"state": st, "unitid": unit, "level": lv, "base year": y, "board programs": u["board programs"]})
            continue
        cy = closure_year(unit.split(";"), hd, hd_years)
        out = {}
        for h in (3, 4):
            if y + h > C_LAST or nat.get((lv, y, h)) is None:
                out[h] = None
                continue
            closed = cy is not None and y < cy <= y + h
            c1 = comp(unit, lv, y + h)
            if closed:
                out[h] = (True, True)
            elif c1 is None:
                out[h] = None              # missing for another reason: left out of that year
            else:
                out[h] = ((c1 / c0) / nat[(lv, y, h)] <= CUT, False)
        if out[3] is None:
            missing_later.append({"state": st, "unitid": unit, "level": lv, "base year": y,
                                  "why": "unit not in the y + 3 file and no documented closure"})
            continue
        rows.append({"state": st, "unitid": unit, "level": lv, "exam year": e, "base year": y,
                     "board programs": " | ".join(u["board programs"]), "pass rate": round(u["rate"], 2),
                     "threshold size": u["threshold size"], "threshold basis": u["threshold basis"],
                     "decile pool": u["pool"], "percentile": u["percentile"], "flagged": u["flagged"],
                     "score": u["score"], "completions y": c0,
                     "completions y+3": comp(unit, lv, y + 3), "national ratio y+3": round(nat[(lv, y, 3)], 4),
                     "closure year (header file)": cy, "shrink 3 years": out[3][0], "closed in 3-year window": out[3][1],
                     "shrink 4 years (report-only)": None if out[4] is None else out[4][0],
                     "exam year note": u["exam year note"]})

    rng = np.random.default_rng(SEED)

    def summary(sel, key="shrink 3 years"):
        sel = [r for r in sel if r[key] is not None]
        f = [r for r in sel if r["flagged"]]
        o = [r for r in sel if not r["flagged"]]
        res = {"program-years": len(sel), "programs": len({(r["state"], r["unitid"], r["level"]) for r in sel}),
               "flagged program-years": len(f), "flagged that shrank": sum(r[key] for r in f),
               "other program-years": len(o), "others that shrank": sum(r[key] for r in o)}
        if not f or not o or not any(r[key] for r in o):
            return res | {"note": "a group is empty or has no shrinkage; ratio not computed"}
        rf, ro = res["flagged that shrank"] / len(f), res["others that shrank"] / len(o)
        idx = defaultdict(list)
        for i, r in enumerate(sel):
            idx[(r["state"], r["unitid"], r["level"])].append(i)
        progs = sorted(idx)
        yv = np.array([r[key] for r in sel], int)
        s = np.array([r["score"] for r in sel], float)
        fl = np.array([r["flagged"] for r in sel], bool)
        rr, aucs = [], []
        for _ in range(BOOT):
            ii = np.concatenate([idx[progs[k]] for k in rng.integers(0, len(progs), len(progs))])
            yf, yo = yv[ii][fl[ii]], yv[ii][~fl[ii]]
            if len(yf) and len(yo) and yo.mean() > 0:
                rr.append(yf.mean() / yo.mean())
            if 0 < yv[ii].sum() < len(ii):
                aucs.append(roc_auc_score(yv[ii], s[ii]))
        auc = roc_auc_score(yv, s) if 0 < yv.sum() < len(yv) else None
        return res | {"shrinkage rate, flagged": rf, "shrinkage rate, others": ro,
                      "rate ratio": rf / ro if ro else None,
                      "rate ratio 95% interval (programs resampled)": [float(np.percentile(rr, 2.5)), float(np.percentile(rr, 97.5))] if rr else None,
                      "AUC of the continuous score": auc,
                      "AUC 95% interval": [float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))] if aucs else None}

    dev = [r for r in rows if r["base year"] in DEV]
    test = [r for r in rows if r["base year"] in TEST]
    if not test or not dev:
        raise SystemExit(f"Development has {len(dev)} and test {len(test)} program-years; something upstream "
                         "misread. No result written.")
    t = summary(test)
    ci = t.get("rate ratio 95% interval (programs resampled)")
    verdict = ("supported" if ci and ci[0] > 1 else "in the predicted direction" if (t.get("rate ratio") or 0) > 1
               else "not supported")
    cuts = np.percentile([r["completions y"] for r in test], [100 / 3, 200 / 3]) if test else [0, 0]
    out = {
        "test": "Item 22a, nursing: bottom-decile first-time NCLEX-RN pass rates and severe program shrinkage",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict, nursing (test period, three-year outcome)": verdict,
        "verdict, pharmacy": "not run here: prospective from base year 2023 (Amendment 2, decision 4; to-do 22b)",
        "development (base years 2015-2017, Florida from 2017; reported only)": summary(dev),
        "test (base years 2018-2021)": t,
        "test, by state": {st: summary([r for r in test if r["state"] == st]) for st in sorted({r["state"] for r in test})},
        "test, by level": {lv: summary([r for r in test if r["level"] == lv]) for lv in ("associate", "bachelor")},
        "test, by tercile of base-year completions": {
            name: summary([r for r in test if lo <= r["completions y"] < hi])
            for name, lo, hi in (("smallest third", 0, cuts[0]), ("middle third", cuts[0], cuts[1]), ("largest third", cuts[1], 1e9))},
        "development, by state": {st: summary([r for r in dev if r["state"] == st]) for st in sorted({r["state"] for r in dev})},
        "four-year outcome (report-only; base years with y + 4 <= 2024)": {
            "development": summary(dev, "shrink 4 years (report-only)"),
            "test": summary(test, "shrink 4 years (report-only)")},
        "test without the closed institutions' windows (check)": summary([r for r in test if not r["closed in 3-year window"]]),
        "test-period shrinkage, by program and year": [
            {k: r[k] for k in ("state", "unitid", "level", "base year", "board programs", "flagged", "closed in 3-year window")}
            for r in test if r["shrink 3 years"]],
        "national ratios (all U.S. programs of the level reporting both years)": {
            f"{lv} {y} to {y + h}": v for (lv, y, h), v in sorted(nat.items())},
        "levels set from IPEDS (Amendment 2, decision 1)": Counter(a["level"] for a in assignments),
        "board names dropped as renamed (Amendment 2, decision 6)": renamed_dropped,
        "program-years left out: zero completions in the base year (decision 9)": zero_base,
        "program-years left out: unit missing in y or y + 3 with no documented closure": missing_later,
        "board rows left out before the test (crosswalk and level)": left_out,
        "Texas exam years changed (October to September, aligned)": sorted({r["exam year"] for r in rows if r["exam year note"]}),
        "practical nursing (NCLEX-PN)": "no PN pass rates were parsed (step two read RN tables only); nothing reported",
        "2025 completions file": served,
        "sources": {"completions": c_files, "header files": hd_files, "header files not served": hd_missing},
        "settings": {"minimum first-time takers": MIN_TAKERS, "bottom decile": DECILE, "relative shrink cut": CUT,
                     "bootstrap": BOOT, "seed": SEED, "level years": [LEVEL_YEARS[0], LEVEL_YEARS[-1]]},
        "limitations": ["Four states are not the nation (section 6).",
                        "Completions trail admissions; the four-year outcome is reported beside the three-year one (section 4).",
                        "Program-years of one program are not independent; intervals resample programs."],
    }
    (DIR / "results.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    with open(DIR / "program_years.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["state"])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"verdict": verdict, "test": t, "development": out["development (base years 2015-2017, Florida from 2017; reported only)"]}, indent=1))


if __name__ == "__main__":
    main()
