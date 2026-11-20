"""
Item 16 (exploratory): the extractive-anchor predictions (RICD 17.7,
Catalog §10.5b.13d), checked on existing IPEDS data. A party that absorbs a
college's losses and builds dependence can extract later; if for-profit
system ("chain") campuses depend on such a parent, then, compared with
independent for-profit colleges:

  E1  early protection: chain campuses close less often in the first years
  E2  clustering: chain closures bunch in time, many campuses of one system
      closing in the same year (the parent failing), more than independent
      closures bunch
  E3  crossing curves: over a long enough horizon the chain campuses'
      cumulative closure rate catches up with and passes the independents'
  E4  extraction: chain campuses' instruction share of expenses falls over
      time relative to independents'

Frame: every for-profit institution (SECTOR 3, 6 or 9) active in HD2009.
Chain: a member of a multi-institution or multi-campus organization in
HD2009 (F1SYSTYP = 1), with its system named by F1SYSNAM, the definition
the v3 anchor sensor and its first trace used. Closure year: the first year
after an institution's last appearance in the header files 2009 onward
(an institution that reappears as active is not closed), or its DEATHYR if
earlier. Instruction share: instruction expenses (F3E01 through fiscal 2013,
F3E011 from fiscal 2014; the field was renamed, recorded as a possible
segment break) over total expenses (F3B02), fiscal 2010 to 2023.

This is exploratory: the outcomes are known. The predictions are tested
blind with the HD2026 retest.

Output: data/v3 exploratory/extractive anchor test.json

Usage (GitHub Actions only, via extractive_anchor_test.yml):
    cd src
    python "extractive anchor test.py"
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import v2_training_outcomes as coding

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "v3 exploratory" / "extractive anchor test.json"
FIRST, LAST = 2009, 2025
FIN = range(2010, 2024)
SEED, BOOT = 20261123, 2000
_s = importlib.util.spec_from_file_location("step1", HERE / "v4 step 1 calibrations.py")
s1 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(s1)
num = s1.num


def headers():
    present, files, missing = defaultdict(dict), [], []
    for y in range(FIRST, LAST + 1):
        try:
            hd = coding.download_hd(y)
        except SystemExit:
            missing.append(f"HD{y}")
            continue
        n = 0
        for r in s1.mc.rows(hd["csv"]):
            present[r["UNITID"]][y] = r
            n += 1
        files.append({k: v for k, v in hd.items() if k != "csv"} | {"institutions read": n})
        if n < 3000:
            raise SystemExit(f"HD{y} yielded {n} institutions; misread. Nothing recorded.")
    return present, files, missing


def closure_year(rows: dict, last_file: int):
    act = {y for y, r in rows.items() if r.get("ACT", "A").upper() in ("A", "R", "")}
    last = max(act) if act else min(rows)
    dy = num(rows[max(rows)].get("DEATHYR"))
    cy = last + 1 if last < last_file else None
    if dy and dy >= FIRST + 1 and (cy is None or dy < cy):
        cy = int(dy)
    return cy


def rate_curve(group, years):
    n = len(group)
    return {str(y): sum(1 for g in group if g["closed"] and g["closed"] <= y) / n for y in years} if n else {}


def main() -> None:
    present, files, missing = headers()
    last_file = max(int(f["table"][2:]) for f in files)
    frame = []
    for u, rows in present.items():
        r0 = rows.get(FIRST)
        if not r0 or r0.get("SECTOR") not in ("3", "6", "9"):
            continue
        frame.append({"unitid": u, "chain": r0.get("F1SYSTYP") == "1", "system": r0.get("F1SYSNAM", "").strip(),
                      "level": {"3": "four-year", "6": "two-year", "9": "less-than-two-year"}[r0["SECTOR"]],
                      "closed": closure_year(rows, last_file)})
    chain = [g for g in frame if g["chain"]]
    indep = [g for g in frame if not g["chain"]]
    years = list(range(FIRST + 1, last_file + 1))

    # E1 and E3: cumulative closure curves; early window 2010-2013; crossing year
    cc, ci = rate_curve(chain, years), rate_curve(indep, years)
    crossing = next((y for y in years if cc[str(y)] > ci[str(y)]), None)
    rng = np.random.default_rng(SEED)

    def boot_diff(y):
        d = []
        for _ in range(BOOT):
            a = rng.choice(len(chain), len(chain))
            b = rng.choice(len(indep), len(indep))
            ra = np.mean([chain[i]["closed"] is not None and chain[i]["closed"] <= y for i in a])
            rb = np.mean([indep[i]["closed"] is not None and indep[i]["closed"] <= y for i in b])
            d.append(ra - rb)
        return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]

    e1 = {"window": "closures 2010-2013", "chain": cc["2013"], "independent": ci["2013"],
          "difference (chain - independent)": cc["2013"] - ci["2013"], "95% interval": boot_diff(2013)}
    e3 = {"cumulative closure rate by year, chain": cc, "cumulative closure rate by year, independent": ci,
          "first year the chain curve is above the independent curve": crossing,
          f"difference at {last_file}": cc[str(last_file)] - ci[str(last_file)],
          f"95% interval at {last_file}": boot_diff(last_file)}

    # E2: clustering of closures in time within systems
    by_sys = defaultdict(list)
    for g in chain:
        if g["system"] and g["closed"]:
            by_sys[g["system"]].append(g["closed"])
    same_year = sum(max(Counter(v).values()) for v in by_sys.values() if len(v) >= 2)
    multi = sum(len(v) for v in by_sys.values() if len(v) >= 2)
    yc = Counter(g["closed"] for g in chain if g["closed"])
    yi = Counter(g["closed"] for g in indep if g["closed"])
    peak = lambda c: max(c.values()) / sum(c.values()) if c else None
    e2 = {"systems with two or more closed campuses": sum(1 for v in by_sys.values() if len(v) >= 2),
          "share of those systems' closures falling in the system's single busiest year": same_year / multi if multi else None,
          "share of all chain closures in the single busiest year": peak(yc),
          "share of all independent closures in the single busiest year": peak(yi),
          "chain closures by year": {str(k): v for k, v in sorted(yc.items())},
          "independent closures by year": {str(k): v for k, v in sorted(yi.items())},
          "largest systems by closed campuses": sorted(((s, len(v)) for s, v in by_sys.items()), key=lambda x: -x[1])[:10]}

    # E4: instruction share of expenses over fiscal years, chain against independent
    ids = {g["unitid"]: g["chain"] for g in frame}
    share = {"chain": defaultdict(list), "independent": defaultdict(list)}
    log = {}
    for f in FIN:
        a, b = (f - 1) % 100, f % 100
        t = s1.table(f"F{a:02d}{b:02d}_F3")
        log[str(f)] = "missing" if t is None else len(t)
        field = "F3E01" if f <= 2013 else "F3E011"
        for u, rows in (t or {}).items():
            if u not in ids:
                continue
            ins, tot = num(rows[0].get(field)), num(rows[0].get("F3B02"))
            if ins is not None and tot and tot > 0:
                share["chain" if ids[u] else "independent"][f].append(ins / tot)
    med = {k: {str(f): float(np.median(v[f])) for f in FIN if v[f]} for k, v in share.items()}

    def slope(m):
        xs = [int(k) for k in m]
        return float(np.polyfit(xs, [m[k] for k in m], 1)[0]) if len(xs) >= 3 else None
    e4 = {"median instruction share by fiscal year": med,
          "trend per year, chain": slope(med["chain"]), "trend per year, independent": slope(med["independent"]),
          "note": "instruction field renamed between fiscal 2013 (F3E01) and 2014 (F3E011); trends also reported within each segment",
          "trend per year within fiscal 2014-2023, chain": slope({k: v for k, v in med["chain"].items() if int(k) >= 2014}),
          "trend per year within fiscal 2014-2023, independent": slope({k: v for k, v in med["independent"].items() if int(k) >= 2014}),
          "finance files read": log}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "test": "Item 16 (exploratory): extractive-anchor predictions on for-profit institutions active in HD2009",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "header files": files, "header files not yet released": missing,
        "frame": {"for-profit institutions in HD2009": len(frame), "chain (system member)": len(chain),
                  "independent": len(indep),
                  "by level": {lv: {"chain": sum(1 for g in chain if g["level"] == lv),
                                    "independent": sum(1 for g in indep if g["level"] == lv)}
                               for lv in ("four-year", "two-year", "less-than-two-year")}},
        "E1 early protection": e1, "E2 clustering": e2, "E3 crossing curves": e3, "E4 instruction share": e4,
        "note": "Exploratory: the outcomes are already known. The predictions are tested blind with the HD2026 retest."},
        indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"E1": e1, "E3 crossing": crossing, "E4": {k: v for k, v in e4.items() if "trend" in k}}, indent=1))


if __name__ == "__main__":
    main()
