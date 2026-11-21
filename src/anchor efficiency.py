"""
Item 15c (exploratory where outcomes are known): overleverage, what
anchors buy, the strain on the grid, and the edge cases, under "anchor
efficiency protocol.md" (decisions A and B approved before anything was
computed).

Applies the frozen item-15 rule (src/ending types.py, imported unchanged)
to every public and private nonprofit college in the IPEDS frame, fiscal
2005 to 2024, and writes:

  college classes.csv     per college: years with data, years short beyond
                          its anchors, longest run, share of years; the same
                          for years held up by anchors; class (never short,
                          episodic, chronic, too short to classify); closure
  episodes.csv            per episode (first year g > 1 after a year at
                          g <= 1): start, anchored share at the start, anchor
                          dollars by source, outcome within five years
                          (recovered, still short, closed, censored)
  strain by source.csv    per sector, fiscal year and anchor source: the
                          dollars covering gaps, split by overleverage class,
                          the strain share (the part going to chronic
                          colleges), and the uncovered shortfall
  edge cases.json         the four lists of protocol section 6 from the v3
                          test (exploratory, outcomes known)
  results.json            summaries by sector, settings, files read

No model is fitted. For-profit colleges are left out (their anchor is not
observable in IPEDS).

Usage (GitHub Actions only, via anchor_efficiency.yml):
    cd src
    python "anchor efficiency.py"
"""
from __future__ import annotations

import csv
import datetime
import glob
import importlib.util
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "data" / "anchor efficiency"
V3 = ROOT / "data" / "v3"
CHRONIC_RUN = 3          # decision A
MIN_YEARS = 5            # fewer years of data: too short to classify
WINDOW = 5               # decision B: outcome read over the next five fiscal years
SHORT, HELD = "short beyond its anchors", "held up by anchors"

_e = importlib.util.spec_from_file_location("et", HERE / "ending types.py")
et = importlib.util.module_from_spec(_e)
_e.loader.exec_module(et)
oc = et.oc
SOURCES = et.SOURCES


def longest_run(years: list[int]) -> int:
    best = run = 0
    prev = None
    for y in sorted(years):
        run = run + 1 if prev is not None and y == prev + 1 else 1
        best = max(best, run)
        prev = y
    return best


def classify(n_years: int, short_years: list[int]) -> str:
    if n_years < MIN_YEARS:
        return "too short to classify"
    if not short_years:
        return "never short"
    return "chronic" if longest_run(short_years) >= CHRONIC_RUN else "episodic"


def episodes(ser: list[dict], closure_year: int | None) -> list[dict]:
    pts = [r for r in ser if r["valid"] and r["g"] is not None]
    pts.sort(key=lambda r: r["fy"])
    by = {r["fy"]: r for r in pts}
    out = []
    prev_ok = False
    i = 0
    while i < len(pts):
        r = pts[i]
        if r["g"] > 1 and prev_ok:
            t = r["fy"]
            window = [y for y in range(t + 1, t + WINDOW + 1)]
            outcome, end = None, None
            for y in window:
                if closure_year is not None and closure_year <= y:
                    outcome, end = "closed", y
                    break
                if y in by and (y + 1) in by and by[y]["g"] <= 1 and by[y + 1]["g"] <= 1 and y + 1 <= t + WINDOW:
                    outcome, end = "recovered", y
                    break
            if outcome is None:
                if t + WINDOW > et.LAST_FY:
                    outcome, end = "censored", et.LAST_FY
                else:
                    last = max((y for y in window if y in by), default=None)
                    outcome = "still short" if last is not None and by[last]["g"] > 1 else "no reading at the end"
                    end = t + WINDOW
            span = [by[y] for y in range(t, end + (0 if outcome == "recovered" else 1)) if y in by]
            dollars = {s: sum((x["anchors"] or {}).get(s, 0.0) for x in span) for s in SOURCES}
            out.append({"start": t, "outcome": outcome, "end": end, "anchored share at start": r["anchored share"],
                        "anchor dollars": dollars, "anchor dollars total": sum(dollars.values()),
                        "years in the episode with data": len(span)})
            # skip to the end of the episode before looking for the next one
            nxt = [k for k, x in enumerate(pts) if x["fy"] > end]
            i = nxt[0] if nxt else len(pts)
            prev_ok = outcome == "recovered"
            continue
        prev_ok = r["g"] <= 1
        i += 1
    return out


def edge_cases(classes: dict) -> dict:
    outcomes_path, batches = V3 / "test outcomes.json", sorted(glob.glob(str(V3 / "test scores" / "batch_*.json")))
    if not outcomes_path.exists() or not batches:
        return {"note": "v3 test files not found"}
    outcome = {x["unitid"]: x["closed or failed (primary)"] for x in json.loads(outcomes_path.read_text())["institutions"]}
    rows = [r for b in batches for r in json.loads(Path(b).read_text())["results"]
            if r.get("status") == "scored" and r.get("score") is not None and r["unitid"] in outcome]

    def item(r):
        c = classes.get(r["unitid"], {})
        return {"unitid": r["unitid"], "name": r["name"], "sector": r["sector"], "closed or failed": outcome[r["unitid"]],
                "v3 flag": r["flag"], "anchored flag": r["anchored flag"], "size-and-sector flag": r["baseline flag"],
                "overleverage class": c.get("class", "not measured (for-profit or no record)"),
                "anchored share, latest year": c.get("anchored share, latest year")}
    lists = {
        "1. closures the tracker caught that size and sector missed":
            [item(r) for r in rows if outcome[r["unitid"]] and r["anchored flag"] and not r["baseline flag"]],
        "2. closures size and sector caught that the tracker missed":
            [item(r) for r in rows if outcome[r["unitid"]] and r["baseline flag"] and not r["anchored flag"]],
        "3. flagged by size and sector, not flagged by the tracker once anchors were counted":
            [item(r) for r in rows if r["baseline flag"] and not r["anchored flag"]],
        "4. flag cleared by the anchor sensor, closed anyway":
            [item(r) for r in rows if r["flag"] and not r["anchored flag"] and outcome[r["unitid"]]],
    }
    summary = {k: {"colleges": len(v), "closed": sum(x["closed or failed"] for x in v)} for k, v in lists.items()}
    return {"note": "Exploratory: v3 test flags at the committed cut points against outcomes already known. "
                    "The tracker's flag here is the anchored flag (its reading after the anchor sensor).",
            "summary": summary, "lists": lists}


def main() -> None:
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

    classes, eps, names = {}, [], {}
    strain = defaultdict(lambda: defaultdict(float))
    for u, rows in frame.items():
        sec = sector_of(rows)
        if sec not in ("public", "private nonprofit"):
            continue
        ser = [r for fy in range(et.FIRST_FY, et.LAST_FY + 1) if (r := et.year_record(u, fy, fin, ef, sec))]
        valid = [r for r in ser if r["valid"] and r["g"] is not None]
        if not valid:
            continue
        names[u] = rows[max(rows)].get("INSTNM", "")
        short = [r["fy"] for r in valid if r["state"] == SHORT]
        held = [r["fy"] for r in valid if r["state"] == HELD]
        cls = classify(len(valid), short)
        latest = max(valid, key=lambda r: r["fy"])
        classes[u] = {"unitid": u, "name": names[u], "sector": sec, "years with data": len(valid),
                      "first year": valid[0]["fy"], "last year": latest["fy"],
                      "years short beyond anchors": len(short), "longest run short": longest_run(short),
                      "share of years short": round(len(short) / len(valid), 4),
                      "years held up by anchors": len(held), "longest run held up": longest_run(held),
                      "share of years held up": round(len(held) / len(valid), 4), "class": cls,
                      "anchored share, latest year": latest["anchored share"],
                      "documented closure (header-file year)": closure.get(u, "")}
        for ep in episodes(ser, closure.get(u)):
            eps.append({"unitid": u, "name": names[u], "sector": sec, "class": cls, **ep})
        for r in valid:
            gap = r["W"] - r["E"] - (r["O"] or 0.0)
            k = (sec, r["fy"])
            if gap > 0 and r["anchors"] is not None:
                for s in SOURCES:
                    strain[k][f"{s} | {cls}"] += r["anchors"][s]
                    strain[k][f"{s} | all"] += r["anchors"][s]
            if r["state"] == SHORT:
                strain[k]["uncovered shortfall"] += gap - (r["A"] or 0.0)
                strain[k][f"uncovered shortfall | {cls}"] += gap - (r["A"] or 0.0)

    OUT.mkdir(parents=True, exist_ok=True)
    cc = list(next(iter(classes.values())))
    with open(OUT / "college classes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cc)
        w.writeheader()
        w.writerows(sorted(classes.values(), key=lambda r: (r["sector"], r["name"])))
    with open(OUT / "episodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["unitid", "name", "sector", "class", "start", "end", "outcome", "anchored share at start",
                    "years in the episode with data", "anchor dollars total"] + [f"anchor dollars: {s}" for s in SOURCES])
        for e in eps:
            w.writerow([e["unitid"], e["name"], e["sector"], e["class"], e["start"], e["end"], e["outcome"],
                        e["anchored share at start"], e["years in the episode with data"], e["anchor dollars total"]]
                       + [e["anchor dollars"][s] for s in SOURCES])
    with open(OUT / "strain by source.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sector", "fiscal year", "source", "dollars covering gaps (all)", "to chronic colleges",
                    "to episodic colleges", "to never-short colleges", "strain share (chronic / all)",
                    "uncovered shortfall (all)", "uncovered shortfall (chronic)"])
        for (sec, fy), d in sorted(strain.items()):
            for s in SOURCES:
                tot = d[f"{s} | all"]
                w.writerow([sec, fy, s, tot, d[f"{s} | chronic"], d[f"{s} | episodic"], d[f"{s} | never short"],
                            (d[f"{s} | chronic"] / tot) if tot > 0 else "", d["uncovered shortfall"],
                            d["uncovered shortfall | chronic"]])

    # summaries
    summ = {}
    for sec in ("public", "private nonprofit"):
        cs = [c for c in classes.values() if c["sector"] == sec]
        cnt = Counter(c["class"] for c in cs)
        closed = Counter(c["class"] for c in cs if c["documented closure (header-file year)"] != "")
        es = [e for e in eps if e["sector"] == sec]
        oc_cnt = Counter(e["outcome"] for e in es)
        dollars = defaultdict(float)
        for e in es:
            dollars[e["outcome"]] += e["anchor dollars total"]
        tot = sum(dollars.values())
        shares = [e["anchored share at start"] for e in es if e["anchored share at start"] is not None]
        cuts = statistics.quantiles(shares, n=3) if len(shares) >= 3 else None
        thirds = defaultdict(Counter)
        for e in es:
            if cuts and e["anchored share at start"] is not None and e["outcome"] != "censored":
                t = "lowest third" if e["anchored share at start"] <= cuts[0] else (
                    "middle third" if e["anchored share at start"] <= cuts[1] else "highest third")
                thirds[t][e["outcome"]] += 1
        rec = oc_cnt["recovered"]
        summ[sec] = {
            "colleges by class": dict(cnt),
            "closure rate by class (documented closures)": {k: round(closed[k] / v, 4) for k, v in cnt.items() if v},
            "episodes by outcome": dict(oc_cnt),
            "share of episode anchor dollars by outcome": {k: round(v / tot, 4) for k, v in dollars.items()} if tot else {},
            "anchor dollars per recovered episode": (tot / rec) if rec else None,
            "anchored-share thirds at the start (cut points)": cuts,
            "outcomes by anchored-share third (censored left out)": {k: dict(v) for k, v in thirds.items()},
        }
    edges = edge_cases(classes)
    (OUT / "edge cases.json").write_text(json.dumps(edges, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    results = {
        "note": "Item 15c under anchor efficiency protocol.md. Descriptive; exploratory where outcomes are known. "
                "Public endowments are left out of anchor capacity (protocol section 8), so public anchors are "
                "slightly understated.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "settings": {"chronic run (years)": CHRONIC_RUN, "fewest years to classify": MIN_YEARS,
                     "episode window (years)": WINDOW, "ending-types rule": "ending types.py, unchanged"},
        "by sector": summ, "edge cases (counts)": edges.get("summary"),
        "header files used": hd_used, "header files not served": hd_missing, "finance and enrollment files": log,
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"by sector": summ, "edge cases": edges.get("summary")}, indent=1, default=str))


if __name__ == "__main__":
    main()
