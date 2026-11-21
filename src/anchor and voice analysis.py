"""
Item 15b (exploratory): the anchor-and-voice analysis, under
"anchor and voice protocol.md" (sections 6, Amendments 1 to 6).

Reads only files already committed in data/anchor and voice/ and
data/ending types/; downloads nothing. Voice is read from voice coded.csv,
fixed before any outcome was recorded; outcomes are read from
case outcomes.csv.

  P1  ending type (shock, drift) by anchoring at onset (anchored, unanchored):
      each cell's shares of rescue, reorganization and closure, cases and
      matched closures together. Supported if shock-with-anchors has the
      highest rescue-or-reorganization share and drift-without-anchors the
      highest closure share.
  P2  among drift-type rows: rescue-or-reorganization share with aligned voice
      in the window against without, Fisher's exact test (two-sided), exact
      95% intervals. Report-only splits: by anchoring; without Martin
      University (unclassified on anchoring).
  P3  report-only: gifts and appropriations in the two fiscal years after the
      announcement (the fiscal year containing it and the next) against the
      two before (the window-end year and the one before), by ending type.
  S1  reversed closures and near-closures (California College of the Arts
      left out, Amendment 6): share with a positive margin (self-covering or
      held up by anchors) in the last fiscal year before the statement.
  S2  drift-type matched closures: share whose margin was gone (short beyond
      its anchors) in the last fiscal year of their window, against S1's share
      with the margin gone.
  S3  lasting rescues against rescue attempts that ended in closure: positive
      margin at the statement, compared directly.
  S4  every public and private nonprofit closure in data/ending types/
      closures.csv with an ending type and an anchoring class: drift-type
      share among anchored against unanchored, Fisher's exact test. Converted
      colleges (Amendment 5's list) are left out; the count with them is
      reported beside it. Anchoring at onset is recomputed from the committed
      closures files by section 3's rule and checked against the matched
      closures already measured by "anchor and voice.py"; any disagreement
      is listed.

Rescue counts only a lasting rescue; a rescue attempt that ended in
closure counts as closure (Amendment 2); pending outcomes are left out of
every count (Amendment 1). Mixed, too-short and unclassified rows are
reported in their own rows, never dropped (a case unclassified on ending
type needs no recorded outcome; without one it is listed as not recorded).
Where the margin year has no
data, the last fiscal year with data inside the window is used and its year
recorded; with none, the row is unmeasured.

Outputs, in data/anchor and voice/:
  analysis rows.csv       every row entering P1 or P2, with its coding
  analysis results.json   P1 to P3 and S1 to S4, counts, intervals, cases listed

Usage (GitHub Actions, via anchor_and_voice_analysis.yml, or locally):
    cd src
    python "anchor and voice analysis.py"
"""
from __future__ import annotations

import csv
import datetime
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import beta, fisher_exact

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "anchor and voice"
ENDING = HERE.parent / "data" / "ending types"
LAST_FY = 2024
CLASSIFIED = ("drift-type", "shock-type", "mixed")
POSITIVE = ("self-covering", "held up by anchors")
GONE = ("short beyond its anchors",)
NO_QUALIFYING_STATEMENT = {"California College of the Arts"}   # Amendment 6, part 4
UNCLASSIFIED_MATCH = {"Martin University"}
OUTCOMES = ("lasting rescue", "rescue attempt then closure", "reorganization", "closure", "pending")
ANCHOR_SOURCES = ("federal appropriations", "state appropriations", "local appropriations", "gifts")


def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def interval(k: int, n: int) -> list | None:
    """Exact (Clopper-Pearson) 95% interval for k of n."""
    if n == 0:
        return None
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return [round(lo, 4), round(hi, 4)]


def share(k: int, n: int) -> dict:
    return {"count": k, "of": n, "share": round(k / n, 4) if n else None, "exact 95% interval": interval(k, n)}


def fisher(a: int, b: int, c: int, d: int) -> float | None:
    if min(a + b, c + d, a + c, b + d) == 0:
        return None
    return round(float(fisher_exact([[a, b], [c, d]])[1]), 4)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def outcome_class(o: str) -> str | None:
    """Rescue, reorganization or closure for P1 and P2 (Amendments 1 and 2); None if pending."""
    return {"lasting rescue": "rescue", "reorganization": "reorganization", "closure": "closure",
            "rescue attempt then closure": "closure"}.get(o)


def main() -> None:
    cases = read(DATA / "cases measured.csv")
    matched = read(DATA / "matched closures.csv")
    voice = {r["college"]: r for r in read(DATA / "voice coded.csv")}
    outcomes = {r["name"]: r for r in read(DATA / "case outcomes.csv")}
    series = defaultdict(dict)
    for r in read(DATA / "case series.csv"):
        series[r["unitid"]][int(r["fiscal year"])] = r
    cseries = defaultdict(dict)
    for r in read(ENDING / "closures series.csv"):
        cseries[r["unitid"]][int(r["fiscal year"])] = r
    medians = {(r["sector"], int(r["fiscal year"])): float(r["median anchored share"])
               for r in read(DATA / "sector medians.csv")}
    converted = {r["unitid"] for r in read(DATA / "converted closures left out.csv")}
    reversal_outcomes = {r["institution"]: r["outcome under Amendments 1 to 3"] for r in read(DATA / "reversal cases.csv")}

    bad = [k for k, r in outcomes.items() if r["outcome"] not in OUTCOMES]
    if bad:
        raise SystemExit(f"Outcomes not in {OUTCOMES}: {bad}")

    # ---------------------------------------------------------- rows for P1 and P2
    rows, missing = [], []
    for c in cases:
        if len(c["unitid"].split(";")) != 1 or not c["unitid"]:
            continue
        if c["group"] == "merger or acquisition" and c["distress check (mergers)"] != "passes":
            continue
        m = c["measure used"]
        etype = c[f"{m} type"] if m else "not classified"
        o = outcomes.get(c["name"])
        if o is None:
            if etype in CLASSIFIED:
                missing.append(c["name"])
                continue
            o = {"outcome": "not recorded"}   # unclassified on ending type: outcome needed only for its own row
        v = voice.get(c["name"])
        rows.append({"name": c["name"], "unitid": c["unitid"], "role": "case", "group": c["group"],
                     "ending type": etype, "anchoring": c["anchoring"] or "unclassified on anchoring",
                     "voice": v["voice in the window"] if v else "not searched",
                     "outcome": o["outcome"], "outcome class": outcome_class(o["outcome"]) or ("pending" if o["outcome"] == "pending" else "not recorded"),
                     "window end": c["window end (fiscal year)"]})
    if missing:
        raise SystemExit(f"No outcome recorded in case outcomes.csv for {len(missing)} cases: {missing}")
    for m in matched:
        v = voice.get(m["closure"])
        rows.append({"name": m["closure"], "unitid": m["closure unitid"], "role": "matched closure",
                     "group": "matched closure", "ending type": m["ending type"],
                     "anchoring": m["anchoring"] or "unclassified on anchoring",
                     "voice": v["voice in the window"] if v else "not searched",
                     "outcome": "closure", "outcome class": "closure",
                     "window end": min(int(m["closure year"]), LAST_FY)})
    drift_unsearched = [r["name"] for r in rows if r["ending type"] == "drift-type" and r["voice"] == "not searched"]
    if drift_unsearched:
        raise SystemExit(f"Drift-type rows with no voice coding: {drift_unsearched}")

    known = [r for r in rows if r["outcome class"] not in ("pending", "not recorded")]

    # ---------------------------------------------------------- P1
    def cell(rs):
        n = len(rs)
        k = Counter(r["outcome class"] for r in rs)
        return {"rows": n, "rescue": share(k["rescue"], n), "reorganization": share(k["reorganization"], n),
                "closure": share(k["closure"], n),
                "rescue or reorganization": share(k["rescue"] + k["reorganization"], n),
                "colleges": sorted(f"{r['name']} ({r['role']}; {r['outcome']})" for r in rs)}
    p1 = {}
    for et in ("shock-type", "drift-type"):
        for an in ("anchored", "unanchored"):
            p1[f"{et}, {an}"] = cell([r for r in known if r["ending type"] == et and r["anchoring"] == an])
    others = [r for r in known if not (r["ending type"] in ("shock-type", "drift-type") and r["anchoring"] in ("anchored", "unanchored"))]
    p1_other = {k: cell([r for r in others if f"{r['ending type']}, {r['anchoring']}" == k])
                for k in sorted({f"{r['ending type']}, {r['anchoring']}" for r in others})}
    rr = {k: v["rescue or reorganization"]["share"] for k, v in p1.items() if v["rows"]}
    cl = {k: v["closure"]["share"] for k, v in p1.items() if v["rows"]}
    p1_supported = (len(rr) == 4 and rr["shock-type, anchored"] == max(rr.values())
                    and cl["drift-type, unanchored"] == max(cl.values()))

    # ---------------------------------------------------------- P2
    def p2_table(rs):
        a = [r for r in rs if r["voice"] == "aligned"]
        s = [r for r in rs if r["voice"] != "aligned"]
        ok = lambda g: sum(1 for r in g if r["outcome class"] in ("rescue", "reorganization"))
        return {"with aligned voice": share(ok(a), len(a)), "without (silence or normalization)": share(ok(s), len(s)),
                "Fisher exact p, two-sided": fisher(ok(a), len(a) - ok(a), ok(s), len(s) - ok(s)),
                "colleges with aligned voice": sorted(f"{r['name']} ({r['role']}; {r['outcome']}; {r['anchoring']})" for r in a)}
    drift = [r for r in known if r["ending type"] == "drift-type"]
    p2 = {"all drift-type rows": p2_table(drift),
          "report-only: without Martin University (unclassified on anchoring)":
              p2_table([r for r in drift if r["name"] not in UNCLASSIFIED_MATCH]),
          "report-only: anchored only": p2_table([r for r in drift if r["anchoring"] == "anchored"]),
          "report-only: unanchored only": p2_table([r for r in drift if r["anchoring"] == "unanchored"]),
          "drift-type rows left out as pending": sorted(r["name"] for r in rows
                                                        if r["ending type"] == "drift-type" and r["outcome class"] == "pending")}

    # ---------------------------------------------------------- P3 (report-only)
    p3_rows = []
    for r in rows:
        if r["role"] != "case" or not r["window end"]:
            continue
        we, s = int(r["window end"]), series.get(r["unitid"], {})
        def tot(fy):
            x = s.get(fy)
            if not x:
                return None
            vals = [num(x.get(f"anchor: {k}")) for k in ANCHOR_SOURCES]
            return sum(v for v in vals if v is not None)
        before = [t for t in (tot(we - 1), tot(we)) if t is not None]
        after = [t for t in (tot(we + 1), tot(we + 2)) if t is not None]
        ratio = (statistics.mean(after) / statistics.mean(before)) if before and after and statistics.mean(before) > 0 else None
        p3_rows.append({"name": r["name"], "ending type": r["ending type"], "years before": [we - 1, we],
                        "years after": [we + 1, we + 2], "mean before": round(statistics.mean(before)) if before else None,
                        "mean after": round(statistics.mean(after)) if after else None,
                        "after over before": round(ratio, 3) if ratio is not None else None})
    p3 = {"by ending type": {et: {"cases with both periods": len(v), "median after over before":
                                  round(statistics.median(v), 3) if v else None}
                             for et in ("shock-type", "drift-type", "mixed")
                             for v in [[x["after over before"] for x in p3_rows if x["ending type"] == et and x["after over before"] is not None]]},
          "cases": p3_rows}

    # ---------------------------------------------------------- margins (S1 to S3)
    def margin(ser: dict, end: int) -> tuple[str, int | None]:
        for fy in range(end, end - 3, -1):
            x = ser.get(fy)
            if x and x.get("state"):
                st = x["state"]
                return ("positive" if st in POSITIVE else "gone" if st in GONE else "unmeasured"), fy
        return "unmeasured", None

    rev = []
    for c in cases:
        if c["group"] != "reversed closure or near-closure" or c["name"] in NO_QUALIFYING_STATEMENT or not c["window end (fiscal year)"]:
            continue
        mg, fy = margin(series.get(c["unitid"], {}), int(c["window end (fiscal year)"]))
        # outcome from case outcomes.csv, else from reversal cases.csv (a reversal
        # unclassified on ending type, such as Sweet Briar, is still an S1 and S3 case)
        o = outcomes.get(c["name"], {}).get("outcome", "") or reversal_outcomes.get(c["name"], "")
        rev.append({"name": c["name"], "margin": mg, "fiscal year read": fy,
                    "window end": int(c["window end (fiscal year)"]), "outcome": o})
    s1_meas = [r for r in rev if r["margin"] != "unmeasured"]
    s1 = {"positive margin": share(sum(r["margin"] == "positive" for r in s1_meas), len(s1_meas)),
          "margin gone": share(sum(r["margin"] == "gone" for r in s1_meas), len(s1_meas)),
          "unmeasured": [r["name"] for r in rev if r["margin"] == "unmeasured"], "cases": rev,
          "left out (no qualifying statement, Amendment 6)": sorted(NO_QUALIFYING_STATEMENT)}

    s2_rows = []
    for m in matched:
        if m["ending type"] != "drift-type":
            continue
        mg, fy = margin(cseries.get(m["closure unitid"], {}), min(int(m["closure year"]), LAST_FY))
        s2_rows.append({"name": m["closure"], "margin": mg, "fiscal year read": fy, "closure year": int(m["closure year"])})
    s2_meas = [r for r in s2_rows if r["margin"] != "unmeasured"]
    g2, g1 = sum(r["margin"] == "gone" for r in s2_meas), sum(r["margin"] == "gone" for r in s1_meas)
    s2 = {"margin gone": share(g2, len(s2_meas)), "S1 margin gone, for comparison": share(g1, len(s1_meas)),
          "Fisher exact p, two-sided (descriptive)": fisher(g2, len(s2_meas) - g2, g1, len(s1_meas) - g1),
          "unmeasured": [r["name"] for r in s2_rows if r["margin"] == "unmeasured"], "closures": s2_rows}

    lasting = [r for r in s1_meas if r["outcome"] == "lasting rescue"]
    attempt = [r for r in s1_meas if r["outcome"] == "rescue attempt then closure"]
    pl, pa = sum(r["margin"] == "positive" for r in lasting), sum(r["margin"] == "positive" for r in attempt)
    s3 = {"lasting rescues with a positive margin": share(pl, len(lasting)),
          "rescue attempts then closure with a positive margin": share(pa, len(attempt)),
          "Fisher exact p, two-sided": fisher(pl, len(lasting) - pl, pa, len(attempt) - pa),
          "pending, left out": sorted(r["name"] for r in rev if r["outcome"] == "pending")}

    # ---------------------------------------------------------- S4
    matched_anch = {m["closure unitid"]: m["anchoring"] for m in matched}
    s4_rows, disagree = [], []
    for k in read(ENDING / "closures.csv"):
        if k["sector"] not in ("public", "private nonprofit"):
            continue
        meas = "primary" if k["primary type"] in CLASSIFIED else "check" if k["check type"] in CLASSIFIED else None
        if not meas:
            continue
        cap = min(int(k["closure year"]), LAST_FY)
        if k["primary group"] == "crossed" and k["primary crossing"]:
            on = int(k["primary crossing"])
        elif k["check group"] == "crossed" and k["check crossing"]:
            on = int(k["check crossing"])
        else:
            on = cap
        x = cseries.get(k["unitid"], {}).get(on)
        sh, med = (num(x["anchored share"]) if x else None), medians.get((k["sector"], on))
        if sh is None or med is None or (x and (num(x["c"]) or 0) <= 1):
            an = "unclassified on anchoring"
        else:
            an = "anchored" if sh >= med else "unanchored"
        if k["unitid"] in matched_anch and matched_anch[k["unitid"]] != an:
            disagree.append({"unitid": k["unitid"], "name": k["name"], "recomputed": an, "measured": matched_anch[k["unitid"]]})
        s4_rows.append({"unitid": k["unitid"], "type": k[f"{meas} type"], "anchoring": an,
                        "converted": k["unitid"] in converted})

    def s4_table(rs):
        rs = [r for r in rs if r["anchoring"] in ("anchored", "unanchored") and r["type"] in ("drift-type", "shock-type")]
        a = [r for r in rs if r["anchoring"] == "anchored"]
        u = [r for r in rs if r["anchoring"] == "unanchored"]
        da, du = sum(r["type"] == "drift-type" for r in a), sum(r["type"] == "drift-type" for r in u)
        return {"anchored closures, drift-type share": share(da, len(a)),
                "unanchored closures, drift-type share": share(du, len(u)),
                "Fisher exact p, two-sided": fisher(da, len(a) - da, du, len(u) - du)}
    s4 = {"converted colleges left out": s4_table([r for r in s4_rows if not r["converted"]]),
          "report-only: converted colleges included": s4_table(s4_rows),
          "mixed closures (own row)": dict(Counter(r["anchoring"] for r in s4_rows if r["type"] == "mixed")),
          "unclassified on anchoring": sum(r["anchoring"] == "unclassified on anchoring" for r in s4_rows),
          "check against the matched closures measured by anchor and voice.py":
              {"matched closures compared": sum(1 for r in s4_rows if r["unitid"] in matched_anch),
               "disagreements": disagree}}

    # ---------------------------------------------------------- write
    cols = ["name", "unitid", "role", "group", "ending type", "anchoring", "voice", "outcome", "outcome class", "window end"]
    with open(DATA / "analysis rows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    results = {
        "note": "Item 15b, exploratory, under anchor and voice protocol.md (sections 6; Amendments 1 to 6). "
                "Voice read from voice coded.csv (fixed before outcomes were recorded); outcomes from case outcomes.csv.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "rows": {"total": len(rows), "with a known outcome": len(known),
                 "by role": dict(Counter(r["role"] for r in rows)),
                 "by ending type": dict(Counter(r["ending type"] for r in known)),
                 "by voice": dict(Counter(r["voice"] for r in known))},
        "P1": {"cells": p1, "other rows (own rows)": p1_other, "supported": p1_supported},
        "P2": p2, "P3 (report-only)": p3, "S1": s1, "S2": s2, "S3": s3, "S4": s4,
    }
    (DATA / "analysis results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"P1 supported": p1_supported, "P2": p2["all drift-type rows"],
                      "S4 disagreements": len(disagree)}, indent=1))


if __name__ == "__main__":
    main()
