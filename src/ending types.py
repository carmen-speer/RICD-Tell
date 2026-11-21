"""
Item 15 (exploratory): ending types, drift-type against shock-type
approaches to collapse, under "ending types protocol.md" (committed before
any finance, enrollment or closure value was read).

For every degree-granting college in the IPEDS header files from HD2005,
and every fiscal year 2005 onward, reads:

  W       total expenses less depreciation (protocol Amendment 3)
                                   F1D02 / F2B02 / F3B02 (F3D09 fallback, flagged), less
                                   F1C194 or F1C19DP / F2E135 / F3E075 (flagged where missing)
  E_exch  net tuition and fees plus sales and services of auxiliary
          enterprises (protocol Amendment 1)
                                   F1B01 + F1B05 / F2D01 + F2D12 / F3D01 + F3D07
  N       12-month FTE enrollment  EFTEUG + EFTEGD (EFIA, IPEDS-estimated)
  A       anchor capacity, by source (federal, state, local appropriations;
          gifts; endowment spending), as section 7 of the protocol fixes:
            public            F1B10, F1B11, F1B12, F1B16 (no endowment)
            private nonprofit F2D02, F2D03, F2D04; F2D08A + F2D09 from fiscal
                              2008, F2D08 + F2D09 before (flagged: includes
                              grants and contracts); F2H03C from fiscal 2020,
                              0.045 x F2H01 before (flagged: estimate)
            for-profit        not observable (missing, never zero)

and computes coverage c = W / E_exch, gap coverage g = W / (E_exch + A + O),
with O other operating income (protocol Amendment 2),
each college-year's state (self-covering, held up by anchors, short beyond
its anchors), the anchored share A / (W - E_exch) and its split by source
(who carries the strain), and the sectors' totals by source each year.

Then, for Sweet Briar College (window ends fiscal 2015, the closure
announcement), the University of Phoenix (all campuses named "University
of Phoenix" summed; approach to date, no type), and every college with a
documented closure 2005 onward (grounds a or b of the tracker's outcome
coding; combined into another institution, ground c, and disappearances
with no record, ground d, are not closures and are counted separately),
decomposes the change in log g (primary) and log c (check) over the window
into a drift part, a jump part and a gap part, and classifies the approach
as shock-type, drift-type, mixed or too short to classify (protocol
section 5).

Exploratory: the outcomes are known. The rule is frozen for the retest.

Outputs, in data/ending types/:
  results.json                       summary counts, settings, files read
  closures.csv                       one row per documented closure
  named cases.json                   Sweet Briar and Phoenix: series and decompositions
  closures series.csv                every measured college-year (closures and named cases)
  strain by source, sector totals.csv

Usage (GitHub Actions only, via ending_types.yml):
    cd src
    python "ending types.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import v2_training_outcomes as coding

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "data" / "ending types"
FIRST_FY, LAST_FY = 2005, 2024          # finance: F0405 (fiscal 2005) to F2324 (fiscal 2024)
FIRST_HD, LAST_HD = 2005, 2026
MIN_FIN_ROWS, MIN_F1A_ROWS, MIN_HD_ROWS, MIN_EF_ROWS = 1000, 500, 3000, 3000
SWEET_BRIAR = "Sweet Briar College"
SWEET_BRIAR_LAST_FY = 2015
PHOENIX_PREFIX = "University of Phoenix"
DRAW = 0.045                             # pre-2020 endowment draw estimate
GIFTS_ALONE_FROM = 2008                  # F2D08A first reported (F0708)
SPENDING_FROM = 2020                     # F2H03C first reported (F1920)
JUMP_SDS = 3.0
MIN_CHANGES = 5

_s = importlib.util.spec_from_file_location("step1", HERE / "v4 step 1 calibrations.py")
s1 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(s1)
_o = importlib.util.spec_from_file_location("oc", HERE / "openings and closures.py")
oc = importlib.util.module_from_spec(_o)
_o.loader.exec_module(oc)
num = s1.num

SECTOR = {"1": "public", "2": "private nonprofit", "3": "for-profit"}
SOURCES = ("federal appropriations", "state appropriations", "local appropriations", "gifts", "endowment spending")


# ------------------------------------------------------------------ reading
def headers() -> tuple[dict, dict, list]:
    tables, used, missing = {}, {}, []
    for y in range(FIRST_HD, LAST_HD + 1):
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
        tables[y] = t
        used[f"HD{y}"] = {"url": hd["url"], "zip sha256": hd["zip sha256"], "institutions read": len(t)}
    return tables, used, missing


def first(row: dict, *codes) -> float | None:
    vals = [num(row.get(c)) for c in codes]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def finance(log: dict) -> dict:
    """{unitid: {fy: record}} from the three forms."""
    out: dict = defaultdict(dict)
    for fy in range(FIRST_FY, LAST_FY + 1):
        a, b = (fy - 1) % 100, fy % 100
        for form in ("F1A", "F2", "F3"):
            name = f"F{a:02d}{b:02d}_{form}"
            t = s1.table(name)
            if t is None:
                log[name] = "not served"
                if fy < LAST_FY:
                    raise SystemExit(f"{name} not served; a gap mid-span. Nothing recorded.")
                continue
            if len(t) < (MIN_FIN_ROWS if form != "F1A" else MIN_F1A_ROWS):
                raise SystemExit(f"{name}: only {len(t)} rows read. Nothing recorded.")
            log[name] = len(t)
            for u, rows in t.items():
                r = rows[0]
                rec = {"form": form, "flags": []}
                if form == "F1A":
                    tot, oth = num(r.get("F1B25")), num(r.get("F1B24"))
                    rev = (tot - (oth or 0.0) - (num(r.get("F1B17")) or 0.0)) if tot is not None else None
                    rec |= {"W": num(r.get("F1D02")), "E": first(r, "F1B01", "F1B05"), "R": rev,
                            "federal appropriations": num(r.get("F1B10")), "state appropriations": num(r.get("F1B11")),
                            "local appropriations": num(r.get("F1B12")), "gifts": num(r.get("F1B16")),
                            "endowment begin": None, "spending": None}
                elif form == "F2":
                    if fy >= GIFTS_ALONE_FROM:
                        gifts = first(r, "F2D08A", "F2D09")
                    else:
                        gifts = first(r, "F2D08", "F2D09")
                        rec["flags"].append("gifts include grants and contracts")
                    tot = num(r.get("F2D16"))
                    rev = (tot - (num(r.get("F2D10")) or 0.0)) if tot is not None else None
                    rec |= {"W": num(r.get("F2B02")), "E": first(r, "F2D01", "F2D12"), "R": rev,
                            "federal appropriations": num(r.get("F2D02")), "state appropriations": num(r.get("F2D03")),
                            "local appropriations": num(r.get("F2D04")), "gifts": gifts,
                            "endowment begin": num(r.get("F2H01")),
                            "spending": (abs(num(r.get("F2H03C"))) if num(r.get("F2H03C")) is not None else None)
                                        if fy >= SPENDING_FROM else None}
                else:
                    w = num(r.get("F3B02"))
                    if w is None or w == 0:
                        w = num(r.get("F3D09"))
                        if w is not None:
                            rec["flags"].append("expenses from total revenues (F3D09)")
                    tot = num(r.get("F3D09"))
                    rev = (tot - (num(r.get("F3D05")) or 0.0)) if tot is not None else None
                    rec |= {"W": w, "E": first(r, "F3D01", "F3D07"), "R": rev}
                # Amendment 3: total expenses less depreciation (a non-cash cost)
                dep_codes = {"F1A": ("F1C194", "F1C19DP"), "F2": ("F2E135",), "F3": ("F3E075",)}[form]
                dep = next((v for c in dep_codes if (v := num(r.get(c))) is not None), None)
                if rec.get("W") is not None:
                    if dep is not None:
                        rec["W"] = rec["W"] - dep
                    else:
                        rec["flags"].append("depreciation not reported; total expenses include it")
                out[u][fy] = rec
        print("finance", fy, flush=True)
    return out


def enrollment(log: dict) -> dict:
    out: dict = defaultdict(dict)
    for fy in range(FIRST_FY, LAST_FY + 1):
        name = f"EFIA{fy}"
        t = s1.table(name)
        if t is None:
            log[name] = "not served"
            if fy < LAST_FY:
                raise SystemExit(f"{name} not served; a gap mid-span. Nothing recorded.")
            continue
        if len(t) < MIN_EF_ROWS:
            raise SystemExit(f"{name}: only {len(t)} rows read. Nothing recorded.")
        log[name] = len(t)
        for u, rows in t.items():
            n = first(rows[0], "EFTEUG", "EFTEGD")
            if n is not None and n > 0:
                out[u][fy] = n
    return out


# ------------------------------------------------------------------ measures
def anchors(rec: dict, sector: str) -> tuple[dict | None, list]:
    """Anchor dollars by source, or None where not observable."""
    if sector == "for-profit":
        return None, []
    flags = []
    parts = {s: (rec.get(s) or 0.0) for s in ("federal appropriations", "state appropriations", "local appropriations", "gifts")}
    parts["endowment spending"] = 0.0
    if sector == "private nonprofit" and rec.get("form") == "F2":
        if rec.get("spending") is not None:
            parts["endowment spending"] = rec["spending"]
        elif rec.get("endowment begin"):
            parts["endowment spending"] = DRAW * rec["endowment begin"]
            flags.append("endowment spending estimated (4.5% of beginning value)")
    return parts, flags


def year_record(u: str, fy: int, fin: dict, ef: dict, sector: str) -> dict | None:
    rec = fin.get(u, {}).get(fy)
    if rec is None:
        return None
    W, E, N = rec.get("W"), rec.get("E"), ef.get(u, {}).get(fy)
    if W is None or E is None or W <= 0 or E <= 0:
        return {"fy": fy, "W": W, "E": E, "N": N, "valid": False}
    parts, flags = anchors(rec, sector)
    flags = rec["flags"] + flags
    A = sum(parts.values()) if parts is not None else None
    # other operating income (Amendment 2): operating revenue less exchange and the anchors inside it
    R = rec.get("R")
    O = None
    if R is not None:
        inside = (A - parts["endowment spending"]) if parts is not None else 0.0
        O = R - E - inside
        if O < 0:
            flags.append("other operating income below zero, set to zero")
            O = 0.0
    else:
        flags.append("total revenue missing; other operating income not counted")
    c = W / E
    g = W / (E + A + (O or 0.0)) if A is not None else None
    state = ("self-covering" if c <= 1 else
             None if g is None else "held up by anchors" if g <= 1 else "short beyond its anchors")
    gap = W - E - (O or 0.0)
    share = (A / gap) if (A is not None and gap > 0) else None
    by_source = {s: parts[s] / gap for s in SOURCES} if (parts is not None and gap > 0) else None
    return {"fy": fy, "W": W, "E": E, "N": N, "A": A, "O": O, "anchors": parts, "c": c, "g": g, "state": state,
            "anchored share": share, "anchored share by source": by_source, "flags": flags, "valid": True}


def robust_sd(xs: list[float]) -> float:
    m = statistics.median(xs)
    return 1.4826 * statistics.median([abs(x - m) for x in xs])


def decompose(series: list[dict], ratio: str, start: int, end: int, use_anchor_jumps: bool) -> dict:
    """Protocol section 5 over fiscal years start..end (inclusive)."""
    pts = [r for r in series if r["valid"] and start <= r["fy"] <= end and r[ratio] is not None and r[ratio] > 0]
    pts.sort(key=lambda r: r["fy"])
    out = {"window": [start, end], "years with data": [r["fy"] for r in pts]}
    if len(pts) < 2:
        return out | {"type": "too short to classify", "reason": "fewer than two years with data"}
    total = math.log(pts[-1][ratio]) - math.log(pts[0][ratio])
    steps, gap_part = [], 0.0
    for p, q in zip(pts, pts[1:]):
        d = math.log(q[ratio]) - math.log(p[ratio])
        if q["fy"] - p["fy"] != 1:
            gap_part += d
            continue
        dn = (math.log(q["N"]) - math.log(p["N"])) if (p.get("N") and q.get("N")) else None
        da = (math.log(q["A"]) - math.log(p["A"])) if (use_anchor_jumps and p.get("A") and q.get("A")) else None
        steps.append({"fy": q["fy"], "change": d, "dlogN": dn, "dlogA": da})
    jumps = set()
    tests = {}
    for key in ("dlogN",) + (("dlogA",) if use_anchor_jumps else ()):
        xs = [s[key] for s in steps if s[key] is not None]
        if len(xs) < MIN_CHANGES:
            tests[key] = {"changes": len(xs), "status": "too few changes"}
            continue
        med, rsd = statistics.median(xs), robust_sd(xs)
        cut = med - JUMP_SDS * rsd
        hit = [s["fy"] for s in steps if s[key] is not None and s[key] < cut]
        tests[key] = {"changes": len(xs), "median": med, "robust sd": rsd, "threshold": cut, "jump years": hit,
                      "status": "robust sd zero: any fall below the median lies beyond it" if rsd == 0 else "ok"}
        jumps.update(hit)
    jump_part = {s["fy"]: s["change"] for s in steps if s["fy"] in jumps}
    drift_part = sum(s["change"] for s in steps if s["fy"] not in jumps)
    out |= {"total change in log": total, "drift part": drift_part, "jump part by year": jump_part,
            "gap part": gap_part, "jump tests": tests}
    if tests.get("dlogN", {}).get("status") == "too few changes":
        return out | {"type": "too short to classify", "reason": f"fewer than {MIN_CHANGES} year-to-year changes"}
    if total <= 0:
        return out | {"type": "no rise over the window", "reason": "the ratio did not rise; shares undefined"}
    shares = {"drift": drift_part / total, "gap": gap_part / total,
              "largest single jump": max(jump_part.values()) / total if jump_part else 0.0}
    out["shares of the whole change"] = shares
    if shares["gap"] > 0.5:
        t = "too short to classify"
        out["reason"] = "gap part exceeds half the change"
    elif shares["largest single jump"] > 0.5:
        t = "shock-type"
    elif shares["drift"] > 0.5:
        t = "drift-type"
    else:
        t = "mixed"
    return out | {"type": t}


def windows(series: list[dict], end_cap: int, no_cross: str = "closed without crossing") -> dict:
    """Primary and check windows (protocol section 4)."""
    valid = [r for r in series if r["valid"] and r["fy"] <= end_cap]
    if not valid:
        return {"primary": {"type": "too short to classify", "group": "no year with data", "reason": "no year with data"},
                "check": {"type": "too short to classify", "group": "no year with data", "reason": "no year with data"}}
    t0, last = valid[0]["fy"], valid[-1]["fy"]
    observable = any(r["g"] is not None for r in valid)
    ratio = "g" if observable else "c"
    cross = next((r["fy"] for r in valid if r[ratio] is not None and r[ratio] > 1), None)
    if cross is None:
        prim = decompose(series, ratio, t0, last, observable) | {"crossing": None, "group": no_cross}
    elif cross == t0:
        prim = {"crossing": cross, "group": "past the crossing at the start", "type": "not classified",
                "reason": "already past the crossing in the first year with data; see the check measure"}
    else:
        prim = decompose(series, ratio, t0, cross, observable) | {"crossing": cross, "group": "crossed"}
    prim["measure"] = "gap coverage g" if observable else "coverage c (anchor not observable)"
    if cross is not None and any("estimated" in f for r in valid if r["fy"] == cross for f in r["flags"]):
        prim["flag"] = "crossing year uses the pre-2020 endowment estimate"
    if cross is not None and any("grants and contracts" in f for r in valid if r["fy"] == cross for f in r["flags"]):
        prim["flag gifts"] = "crossing year uses gifts that include grants and contracts"
    ccross = next((r["fy"] for r in valid if r["c"] > 1), None)
    if ccross is None:
        chk = decompose(series, "c", t0, last, False) | {"crossing": None, "group": no_cross}
    elif ccross == t0:
        chk = decompose(series, "c", t0, last, False) | {"crossing": ccross, "group": "past c = 1 at the start; window to the end"}
    else:
        chk = decompose(series, "c", t0, ccross, False) | {"crossing": ccross, "group": "crossed"}
    return {"primary": prim, "check": chk}


def phoenix_shape(agg: list[dict]) -> dict | str:
    """The decomposition of Phoenix's approach to date, reported as a shape, never as a collapse type."""
    if len(agg) < 2:
        return "no data"
    d = decompose(agg, "c", agg[0]["fy"], agg[-1]["fy"], False)
    d["what the rule would read (not a collapse type; Phoenix has not closed)"] = d.pop("type")
    return d


# ------------------------------------------------------------------ main
def main() -> None:
    hd, hd_used, hd_missing = headers()
    years = sorted(hd)
    log: dict = {}
    fin = finance(log)
    ef = enrollment(log)

    present = defaultdict(dict)
    for y, t in hd.items():
        for u, r in t.items():
            present[u][y] = r
    frame = {u: rows for u, rows in present.items() if any(oc.in_frame(r) for r in rows.values())}

    def sector_of(rows):
        for y in sorted(rows, reverse=True):
            s = rows[y].get("CONTROL", "")
            if s in SECTOR:
                return SECTOR[s]
        return None

    # sectors' totals by source, every college in the frame
    totals = defaultdict(lambda: defaultdict(float))
    series_all = {}
    for u, rows in frame.items():
        sec = sector_of(rows)
        if sec is None:
            continue
        ser = [r for fy in range(FIRST_FY, LAST_FY + 1) if (r := year_record(u, fy, fin, ef, sec))]
        series_all[u] = ser
        for r in ser:
            if not r["valid"]:
                continue
            k = (sec, r["fy"])
            totals[k]["colleges"] += 1
            totals[k]["W"] += r["W"]
            totals[k]["E"] += r["E"]
            totals[k]["O"] += r["O"] or 0.0
            if r["anchors"] is not None:
                for s in SOURCES:
                    totals[k][s] += r["anchors"][s]
            if r["state"]:
                totals[k][r["state"]] += 1

    # exits, coded as in the tracker's outcome coding
    exits, how = {}, Counter()
    for u, rows in frame.items():
        e = oc.exit_of(u, rows, years)
        if not e or "year" not in e or e["year"] < FIRST_HD:
            continue
        g = e["grounds"]
        kind = ("combined into another institution" if "c" in g else
                "documented closure" if ("a" in g or "b" in g) else "disappeared with no record")
        exits[u] = {"year": e["year"], "how": kind}
        how[(sector_of(rows), kind)] += 1

    closures = []
    for u, e in exits.items():
        if e["how"] != "documented closure":
            continue
        rows = frame[u]
        sec = sector_of(rows)
        last_rec = rows[max(y for y in rows if y <= e["year"])] if any(y <= e["year"] for y in rows) else rows[min(rows)]
        w = windows(series_all.get(u, []), min(e["year"], LAST_FY))
        closures.append({"unitid": u, "name": last_rec.get("INSTNM", ""), "sector": sec,
                         "level": oc.LEVEL.get(last_rec.get("SECTOR", ""), ""), "closure year (header file)": e["year"],
                         "primary": w["primary"], "check": w["check"]})

    # named cases
    def find(pred):
        return sorted({u for u, rows in frame.items() if any(pred(r.get("INSTNM", "")) for r in rows.values())})

    sb = find(lambda n: n.strip().lower() == SWEET_BRIAR.lower())
    named = {}
    if len(sb) != 1:
        named["Sweet Briar College"] = {"error": f"expected one unit ID, found {sb}"}
    else:
        u = sb[0]
        named["Sweet Briar College"] = {"unitid": u, "series": series_all.get(u, []),
                                        **windows(series_all.get(u, []), SWEET_BRIAR_LAST_FY, "no crossing by fiscal 2015")}
    ph = find(lambda n: n.strip().startswith(PHOENIX_PREFIX))
    agg = []
    campuses = {}
    for fy in range(FIRST_FY, LAST_FY + 1):
        recs = [r for u in ph for r in series_all.get(u, []) if r["fy"] == fy and r["valid"]]
        hdy = hd.get(fy)
        campuses[str(fy)] = sum(1 for u in ph if hdy and u in hdy and hdy[u].get("ACT", "A").upper() in ("A", "R", ""))
        if not recs:
            continue
        W, E = sum(r["W"] for r in recs), sum(r["E"] for r in recs)
        Ns = [r["N"] for r in recs if r["N"]]
        agg.append({"fy": fy, "W": W, "E": E, "N": sum(Ns) if len(Ns) == len(recs) else None, "A": None, "c": W / E, "g": None,
                    "valid": True, "flags": [], "reporting units": len(recs)})
    named["University of Phoenix (all units, summed)"] = {
        "unitids": ph, "campuses active in the header file each year": campuses, "series": agg,
        "approach to date (coverage c; no collapse type, since it has not closed)": phoenix_shape(agg)}

    # ------------------------------------------------------------------ write
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tally = defaultdict(Counter)
    for c in closures:
        for m in ("primary", "check"):
            tally[f"{m}: {c['sector']}"][c[m]["type"]] += 1
            tally[f"{m}: {c['sector']} (group)"][c[m].get("group", "")] += 1
    results = {
        "note": "Item 15, exploratory (outcomes known), under ending types protocol.md. Rule frozen for the retest.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "settings": {"fiscal years": [FIRST_FY, LAST_FY], "jump threshold (robust sd)": JUMP_SDS,
                     "fewest year-to-year changes": MIN_CHANGES, "pre-2020 endowment draw": DRAW},
        "header files used": hd_used, "header files not served": hd_missing, "finance and enrollment files": log,
        "exits from the frame since 2005, by sector and kind (only documented closures are classified)":
            {f"{s} | {k}": v for (s, k), v in sorted(how.items(), key=lambda x: (str(x[0][0]), x[0][1]))},
        "gap (protocol section 6)": "Colleges that combined into another institution or disappeared with no "
            "record are not classified; for-profit rates are of documented closures only.",
        "documented closures classified": len(closures),
        "types by measure and sector": {k: dict(v) for k, v in sorted(tally.items())},
        "named cases": {k: {kk: vv for kk, vv in v.items() if kk != "series"} for k, v in named.items()},
    }
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    (OUT_DIR / "named cases.json").write_text(json.dumps(named, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    with open(OUT_DIR / "closures.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["unitid", "name", "sector", "level", "closure year", "primary measure", "primary group",
                    "primary crossing", "primary type", "primary drift share", "primary largest jump share",
                    "primary gap share", "primary flags", "check group", "check crossing", "check type",
                    "check drift share", "check largest jump share"])
        for c in sorted(closures, key=lambda c: (c["sector"] or "", c["closure year (header file)"], c["name"])):
            p, k = c["primary"], c["check"]
            ps, ks = p.get("shares of the whole change", {}), k.get("shares of the whole change", {})
            w.writerow([c["unitid"], c["name"], c["sector"], c["level"], c["closure year (header file)"],
                        p.get("measure", ""), p.get("group", ""), p.get("crossing", ""), p["type"],
                        ps.get("drift", ""), ps.get("largest single jump", ""), ps.get("gap", ""),
                        "; ".join(x for x in (p.get("flag", ""), p.get("flag gifts", "")) if x),
                        k.get("group", ""), k.get("crossing", ""), k["type"], ks.get("drift", ""),
                        ks.get("largest single jump", "")])

    measured = [c["unitid"] for c in closures] + (sb if len(sb) == 1 else []) + ph
    with open(OUT_DIR / "closures series.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["unitid", "fiscal year", "W total expenses", "E net tuition and auxiliary sales", "N FTE", "A anchors", "O other operating income", "c", "g",
                    "state", "anchored share"] + [f"share: {s}" for s in SOURCES] + ["flags"])
        for u in measured:
            for r in series_all.get(u, []):
                if not r["valid"]:
                    continue
                bs = r["anchored share by source"] or {}
                w.writerow([u, r["fy"], r["W"], r["E"], r["N"], r["A"], r["O"], r["c"], r["g"], r["state"] or "",
                            r["anchored share"] if r["anchored share"] is not None else ""]
                           + [bs.get(s, "") for s in SOURCES] + ["; ".join(r["flags"])])

    with open(OUT_DIR / "strain by source, sector totals.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cols = ["colleges", "W", "E", "O"] + list(SOURCES) + ["self-covering", "held up by anchors", "short beyond its anchors"]
        w.writerow(["sector", "fiscal year"] + cols + ["gap W - E - O"] + [f"share of gap: {s}" for s in SOURCES])
        for (sec, fy), t in sorted(totals.items()):
            gap = t["W"] - t["E"] - t["O"]
            w.writerow([sec, fy] + [int(t.get(c, 0)) if c in ("colleges", "self-covering", "held up by anchors",
                        "short beyond its anchors") else t.get(c, 0) for c in cols] + [gap]
                       + [(t[s] / gap if gap > 0 and sec != "for-profit" else "") for s in SOURCES])

    print(json.dumps({k: results[k] for k in ("documented closures classified", "types by measure and sector")}, indent=1))
    print(f"Wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
