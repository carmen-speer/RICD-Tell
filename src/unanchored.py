"""
The unanchored-against-anchored comparison: how each college would fare
without its anchors. Descriptive; exploratory where outcomes are known (the
closures are public). No model is fitted.

RICD Spine (Definitions 10.3a.7 and 10.3a.8): past break-even, the distance
to the point of no return is

    Delta_PNR(t) = R_avail(t) + A(t) - deltaR(t),

and collapse is guaranteed, absent a new anchor, once Delta_PNR <= 0.
Anchors move the point of no return, not the tipping point. In dollars, a
college without its anchors is its actual expendable reserves less every
external anchor dollar it received since the base year:

    R_unanchored(t) = R_avail(t) - sum over base < s <= t of A_ext(s)

It reaches its unanchored point of no return in the first year that this is
at or below zero while it is past break-even (spending above its own earned
income, item 23k's payer view). The Spine's literal form is reported
alongside: base-year reserves less the accumulated payer-view gap,

    Delta_literal(t) = R_avail(base) - sum over base < s <= t of gap(s),

which leaves out investment returns and capital gifts; where the two differ,
the difference is what those returns and gifts did. Both are given in
dollars and in years of operating expenses (item 23's common units).

Data decisions (approved November 27, 2026, before anything was built):
  reserves     expendable net assets, the standard ratio-analysis measure:
               public: unrestricted + restricted-expendable net position
               (F1A17 + F1A15); private nonprofit: unrestricted net assets
               + donor-restricted net assets less the permanent part, less
               property net of its debt (F2A04 + F2A05 - F2A05A - (F2A19 -
               F2A03A)), from fiscal 2008; for-profit: total equity less
               property net of its debt (F3A03 - (F3A01B - F3A02A)), from
               fiscal 2014
  pensions     public colleges: net pension liability and its deferrals
               (F1M02 + F1M03 - F1M04, from fiscal 2015) and retiree-health
               (OPEB) liability and its deferrals (F1M06 + F1M07 - F1M08,
               from fiscal 2019) added back as the headline, so the GASB 68
               and 75 changes cannot pose as a collapse; the unadjusted
               figure alongside
  anchors      external anchors as in item 23k: government appropriations,
               government student grants and gifts; the endowment draw
               stays as the college's own reserve (this differs from the
               Spine's A, which counts the endowment); a second variant
               removes appropriations and gifts only
  base year    fiscal 2008 for public and private nonprofit colleges,
               fiscal 2014 for for-profits
  method       actual reserves less anchors received (headline); the
               Spine's literal form alongside

A college's path runs over consecutive fiscal years with data from the base
year; a missing year ends it (censored there). Dollars are nominal within a
path, as in the accounts; anchor totals in results.json are also given in
fiscal 2024 dollars (CPI-U). Closures are read from the header files as
item 15c reads them.

Writes data/unanchored/:
  college_paths.csv    per college and fiscal year
  colleges.csv         per college: unanchored point-of-no-return year
                       (headline and variants), actual reserves at or below
                       zero, closure, anchors carried past the unanchored
                       point of no return
  results.json         by sector and overleverage class (item 15c), with
                       and without hospital colleges; files read

Usage (GitHub Actions only, via unanchored.yml):
    cd src
    python unanchored.py
"""
from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "data" / "unanchored"
CLASSES = ROOT / "data" / "anchor efficiency" / "college classes.csv"

_g = importlib.util.spec_from_file_location("gs", HERE / "grid_strain.py")
gs = importlib.util.module_from_spec(_g)
_g.loader.exec_module(gs)
et, ss, s1, oc, num = gs.et, gs.ss, gs.s1, gs.oc, gs.num

BASE = {"public": 2008, "private nonprofit": 2008, "for-profit": 2014}
LAST_FY = et.LAST_FY
VARIANTS = ("external anchors (headline)", "appropriations and gifts only")

BAL: dict = defaultdict(dict)


def bal_hook(orig):
    """Read the balance-sheet lines from the same download item 15 makes."""
    def table(name):
        t = orig(name)
        if t is None or "_" not in name or not name.startswith("F"):
            return t
        stem, form = name.split("_", 1)
        if form not in ("F1A", "F2", "F3") or len(stem) != 5:
            return t
        fy = 2000 + int(stem[3:5])
        for u, rows in t.items():
            r = rows[0]
            g = lambda c: num(r.get(c))
            rec = {"flags": []}
            if form == "F1A":
                un, rx = g("F1A17"), g("F1A15")
                if un is None and rx is None:
                    continue
                base = (un or 0.0) + (rx or 0.0)
                pens = ((g("F1M02") or 0.0) + (g("F1M03") or 0.0) - (g("F1M04") or 0.0)) if fy >= 2015 else 0.0
                opeb = ((g("F1M06") or 0.0) + (g("F1M07") or 0.0) - (g("F1M08") or 0.0)) if fy >= 2019 else 0.0
                if fy == 2015:
                    rec["flags"].append("fiscal 2015 pension line is the additional pension liability")
                if fy == 2018:
                    rec["flags"].append("retiree-health liability on the books but not reported in IPEDS until fiscal 2019")
                rec |= {"reserves (unadjusted)": base, "reserves": base + pens + opeb,
                        "pension and retiree-health add-back": pens + opeb}
            elif form == "F2":
                un, rt, perm = g("F2A04"), g("F2A05"), g("F2A05A")
                ppe, debt = g("F2A19"), g("F2A03A")
                if un is None or ppe is None:
                    continue
                v = un + ((rt or 0.0) - (perm or 0.0)) - (ppe - (debt or 0.0))
                rec |= {"reserves (unadjusted)": v, "reserves": v, "pension and retiree-health add-back": 0.0}
            else:
                eq, ppe, debt = g("F3A03"), g("F3A01B"), g("F3A02A")
                if eq is None or ppe is None:
                    continue
                v = eq - (ppe - (debt or 0.0))
                rec |= {"reserves (unadjusted)": v, "reserves": v, "pension and retiree-health add-back": 0.0}
            BAL[u][fy] = rec
        return t
    return table


def anchors_of(p: dict, rec: dict, ex: dict, sec: str) -> dict:
    """External anchor dollars, both variants, from item 23k's payer record."""
    ext = p["paid by federal"] + p["paid by state"] + p["paid by local"] + p["paid by gifts"]
    if sec == "for-profit":
        appro_gifts = (sum(ex[f"{lv} appropriations (for-profit form)"] for lv in ("federal", "state", "local"))
                       + ex["gifts (for-profit form)"])
    else:
        a = rec["anchors"] or {}
        appro_gifts = (a.get("federal appropriations", 0.0) + a.get("state appropriations", 0.0)
                       + a.get("local appropriations", 0.0) + a.get("gifts", 0.0))
    return {"external anchors (headline)": ext, "appropriations and gifts only": appro_gifts}


def path_for(series: dict, sec: str) -> list[dict] | None:
    """Consecutive fiscal years from the base year; a missing year ends the path."""
    b = BASE[sec]
    if b not in series:
        return None
    pts, fy = [], b
    while fy in series and fy <= LAST_FY:
        pts.append(series[fy])
        fy += 1
    base = pts[0]
    cum = {v: 0.0 for v in VARIANTS}
    cum_gap = 0.0
    out = []
    for i, p in enumerate(pts):
        if i > 0:
            for v in VARIANTS:
                cum[v] += p["anchors"][v]
            cum_gap += p["gap"]
        row = {"fy": p["fy"], "W": p["W"], "gap": p["gap"], "past break-even": p["gap"] > 0,
               "reserves": p["reserves"], "reserves (unadjusted)": p["reserves (unadjusted)"],
               "anchors": p["anchors"], "cumulative anchors": dict(cum),
               "unanchored": {v: p["reserves"] - cum[v] for v in VARIANTS},
               "unanchored (unadjusted reserves)": p["reserves (unadjusted)"] - cum[VARIANTS[0]],
               "literal": base["reserves"] - cum_gap, "flags": p["flags"]}
        row["in years"] = {k: (row["unanchored"][k] / p["W"]) if p["W"] else None for k in VARIANTS}
        row["actual in years"] = p["reserves"] / p["W"] if p["W"] else None
        out.append(row)
    return out


def first_cross(path: list[dict], key) -> int | None:
    for r in path:
        if r["past break-even"] and key(r) <= 0:
            return r["fy"]
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cpi = ss.CPI_FY
    to24 = {fy: cpi[2024] / cpi[fy] for fy in cpi}
    s1.table = bal_hook(gs.hooked_table(s1.table))

    hd, hd_used, hd_missing = et.headers()
    years = sorted(hd)
    log: dict = {}
    fin = et.finance(log)
    ef = et.enrollment(log)

    present = defaultdict(dict)
    for y, t in hd.items():
        for u, r in t.items():
            present[u][y] = r
    frame = {u: rows for u, rows in present.items() if any(oc.in_frame(r) for r in rows.values())}

    def sector_of(rows):
        for y in sorted(rows, reverse=True):
            s = rows[y].get("CONTROL", "")
            if s in et.SECTOR:
                return et.SECTOR[s]
        return None

    closure = {}
    for u, rows in frame.items():
        e = oc.exit_of(u, rows, years)
        if e and "year" in e and ("a" in e["grounds"] or "b" in e["grounds"]) and "c" not in e["grounds"]:
            closure[u] = e["year"]
    classes = {}
    if CLASSES.exists():
        with open(CLASSES, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                classes[row["unitid"]] = row["class"]

    colleges, path_rows = [], []
    for u, rows in frame.items():
        sec = sector_of(rows)
        if sec is None:
            continue
        series = {}
        for fy in range(BASE[sec], LAST_FY + 1):
            rec = et.year_record(u, fy, fin, ef, sec)
            ex = gs.EXTRA.get(u, {}).get(fy)
            bal = BAL.get(u, {}).get(fy)
            if not rec or not rec["valid"] or ex is None or bal is None:
                continue
            p = gs.payer_record(rec, ex, sec, None, None)
            series[fy] = {"fy": fy, "W": p["W"], "gap": p["gap (payer view)"], "reserves": bal["reserves"],
                          "reserves (unadjusted)": bal["reserves (unadjusted)"],
                          "anchors": anchors_of(p, rec, ex, sec), "flags": p["flags"] + bal["flags"]}
        path = path_for(series, sec)
        if not path:
            continue
        name = rows[max(rows)].get("INSTNM", "")
        hosp = any((gs.EXTRA[u][fy]["hospital spending"] or 0) > 0 for fy in series)
        cross = {v: first_cross(path, lambda r, v=v: r["unanchored"][v]) for v in VARIANTS}
        cross_un = first_cross(path, lambda r: r["unanchored (unadjusted reserves)"])
        cross_lit = first_cross(path, lambda r: r["literal"])
        actual = first_cross(path, lambda r: r["reserves"])
        c0 = cross[VARIANTS[0]]
        carried = sum(r["anchors"][VARIANTS[0]] * to24[r["fy"]] for r in path if c0 is not None and r["fy"] >= c0)
        last = path[-1]
        colleges.append({
            "unitid": u, "name": name, "sector": sec, "class (item 15c)": classes.get(u, "not classified"),
            "hospital college": hosp, "base year": path[0]["fy"], "last year in path": last["fy"],
            "reserves at base (nominal $)": round(path[0]["reserves"]),
            "reserves at base, years of spending": round(path[0]["actual in years"], 3) if path[0]["actual in years"] is not None else "",
            "unanchored point of no return (headline)": c0 or "",
            "unanchored point of no return (appropriations and gifts only)": cross[VARIANTS[1]] or "",
            "unanchored point of no return (unadjusted public reserves)": cross_un or "",
            "Spine literal form crosses": cross_lit or "",
            "actual reserves at or below zero past break-even": actual or "",
            "unanchored distance at the last year, years of spending":
                round(last["in years"][VARIANTS[0]], 3) if last["in years"][VARIANTS[0]] is not None else "",
            "anchors carried from the unanchored point of no return on (fiscal 2024 $)": round(carried),
            "documented closure (header-file year)": closure.get(u, ""),
        })
        for r in path:
            path_rows.append([u, name, sec, r["fy"], round(r["W"]), round(r["gap"]), round(r["reserves"]),
                              round(r["reserves (unadjusted)"]),
                              round(r["anchors"][VARIANTS[0]]), round(r["anchors"][VARIANTS[1]]),
                              round(r["cumulative anchors"][VARIANTS[0]]), round(r["unanchored"][VARIANTS[0]]),
                              round(r["unanchored"][VARIANTS[1]]), round(r["literal"]),
                              (round(r["in years"][VARIANTS[0]], 4) if r["in years"][VARIANTS[0]] is not None else ""),
                              "; ".join(sorted(set(r["flags"])))])

    with open(OUT / "college_paths.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["unitid", "name", "sector", "fiscal year", "spending W", "payer-view gap", "reserves",
                    "reserves (unadjusted)", "external anchors", "appropriations and gifts",
                    "cumulative external anchors since base", "unanchored reserves (headline)",
                    "unanchored reserves (appropriations and gifts only)", "Spine literal form",
                    "unanchored, years of spending", "flags"])
        w.writerows(path_rows)
    with open(OUT / "colleges.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(colleges[0]))
        w.writeheader()
        w.writerows(sorted(colleges, key=lambda c: (c["sector"], c["name"])))

    def summary(cs: list[dict]) -> dict:
        n = len(cs)
        if not n:
            return {}
        def rate(pred, base=None):
            pool = [c for c in cs if (base is None or base(c))]
            k = sum(1 for c in pool if pred(c))
            return {"colleges": len(pool), "count": k, "share": round(k / len(pool), 4) if pool else None}
        closed = lambda c: c["documented closure (header-file year)"] != ""
        cross = lambda c: c["unanchored point of no return (headline)"] != ""
        yrs = [c["unanchored point of no return (headline)"] for c in cs if cross(c)]
        carried = [c["anchors carried from the unanchored point of no return on (fiscal 2024 $)"] for c in cs if cross(c)]
        alive = [c for c in cs if cross(c) and not closed(c)]
        return {
            "colleges": n,
            "would reach the point of no return without their anchors (headline)": rate(cross),
            "same, appropriations and gifts only": rate(lambda c: c["unanchored point of no return (appropriations and gifts only)"] != ""),
            "same, unadjusted public reserves": rate(lambda c: c["unanchored point of no return (unadjusted public reserves)"] != ""),
            "Spine literal form crosses": rate(lambda c: c["Spine literal form crosses"] != ""),
            "actual reserves reached zero past break-even (with anchors)": rate(lambda c: c["actual reserves at or below zero past break-even"] != ""),
            "median year of the unanchored point of no return": statistics.median(yrs) if yrs else None,
            "closure rate, colleges that would cross without anchors": rate(closed, cross),
            "closure rate, colleges that would not": rate(closed, lambda c: not cross(c)),
            "past the unanchored point of no return and still open": len(alive),
            "anchors carried from the unanchored point of no return on, total (fiscal 2024 $)": round(sum(carried)),
            "anchors carried, per college still open (median, fiscal 2024 $)":
                statistics.median([c["anchors carried from the unanchored point of no return on (fiscal 2024 $)"] for c in alive]) if alive else None,
        }

    res = {}
    for scope in ("all colleges", "without hospital colleges"):
        for sec in BASE:
            cs = [c for c in colleges if c["sector"] == sec and not (scope != "all colleges" and c["hospital college"])]
            res.setdefault(scope, {})[sec] = {"all classes": summary(cs)}
            if sec != "for-profit":
                for cls in ("chronic", "episodic", "never short"):
                    res[scope][sec][cls] = summary([c for c in cs if c["class (item 15c)"] == cls])
    flags = Counter(fl for r in path_rows for fl in (r[-1].split("; ") if r[-1] else []))
    results = {
        "note": ("Unanchored-against-anchored comparison, descriptive; exploratory where outcomes are known. A college "
                 "reaches its unanchored point of no return in the first year its expendable reserves, less every "
                 "external anchor dollar received since the base year, are at or below zero while it spends more than "
                 "it earns on its own. The endowment draw counts as the college's own reserve, not an anchor, which "
                 "differs from the Spine's A. Public reserves add back pension and retiree-health liabilities net of "
                 "their deferrals (GASB 68 and 75); the unadjusted figure is alongside."),
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "settings": {"base fiscal year": BASE, "variants": VARIANTS},
        "results": res,
        "flags (college-years)": dict(flags),
        "header files used": hd_used, "header files not served": hd_missing, "finance and enrollment files": log,
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps(res["without hospital colleges"], indent=1, default=str)[:5000])


if __name__ == "__main__":
    main()
