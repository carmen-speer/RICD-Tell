"""
Item 15b (exploratory): the anchor-and-voice cases, under
"anchor and voice protocol.md" (with Amendments 1 to 5, committed before
any case was classified or any voice record read).

This script does the measuring half of the case study; the voice records
and outcomes are case research, recorded by hand afterwards. It:

  1. builds the case list from data/anchor and voice/tracker entries.csv
     (mergers, acquisitions, consolidations and affiliations; plain
     closures are not cases; the acquiring partner of a merger is dropped,
     Amendment 1) and data/anchor and voice/reversal cases.csv (reversed
     closures and near-closures, Amendments 2 and 3);
  2. matches each case to its IPEDS unit ID by name (and state where the
     entry gives one); ambiguous and unmatched names are listed, never
     guessed;
  3. measures every college with the frozen rule of "ending types
     protocol.md" (Amendments 1 to 3), using that script's own code and
     settings, unchanged ("src/ending types.py" is imported, not copied);
  4. for each case: the ending type with the window ending at the fiscal
     year before the announcement (protocol section 2); for mergers, the
     distress check (held up by anchors or short beyond its anchors in at
     least one of the three fiscal years before the announcement); the
     onset year and its rule (section 3); the anchored share at onset
     against the median of all colleges of the same sector and year with
     c > 1 (section 3);
  5. draws two matched closures per eligible case, without replacement,
     seed 20261121 (section 2): same sector (public or private nonprofit),
     a documented closure classified (drift-type, shock-type or mixed) on
     the same measure as the case, nearest in 12-month FTE at onset
     (log distance), then nearest in onset year; exact ties are broken by
     the seeded draw. Closures that are themselves cases are left out of
     the pool.

Nothing here reads an outcome or a voice record.

Outputs, in data/anchor and voice/:
  cases measured.csv     one row per case
  matched closures.csv   two rows per eligible case
  sector medians.csv     median anchored share by sector and fiscal year (c > 1)
  case series.csv        every fiscal year of every matched case (for P3, report-only)
  name matching.csv      every case name, its match status and unit ID(s)
  name candidates.csv    for each unresolved name, header-file units sharing its distinctive words
  results.json           counts, settings, files read

Usage (GitHub Actions only, via anchor_and_voice.yml):
    cd src
    python "anchor and voice.py"
"""
from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "anchor and voice"
SEED = 20261121
MATCHES_PER_CASE = 2
DISTRESS_YEARS = 3
CLASSIFIED = ("drift-type", "shock-type", "mixed")
DISTRESS_STATES = ("held up by anchors", "short beyond its anchors")

_e = importlib.util.spec_from_file_location("et", HERE / "ending types.py")
et = importlib.util.module_from_spec(_e)
_e.loader.exec_module(et)
oc = et.oc

# The acquiring partner's own row in the 2018 reprint (Amendment 1: only the
# absorbed or acquired college is a case). Each is identified from the
# partner's own entry in the same table.
ACQUIRERS = {
    "Abraham Baldwin Agricultural College",        # absorbed Bainbridge State College
    "Berklee College of Music",                    # absorbed The Boston Conservatory
    "Boston University (campus or program)",       # absorbed Wheelock College
    "Clarkson University",                         # absorbed Union Graduate College
    "Georgia Southern University",                 # absorbed Armstrong State University
    "Georgia State University",                    # absorbed Georgia Perimeter College
    "Hope International University",               # absorbed Nebraska Christian College
    "Maine College of Art",                        # absorbed Salt Institute of Documentary Studies
    "Piedmont International University",           # absorbed Southeastern Bible College and John Wesley College
    "Thomas Jefferson University",                 # absorbed Philadelphia University
    "New England College",                         # absorbed New Hampshire Institute of Art
}
# The 2018 reprint's Pacific Northwest College of Art row is the partner of
# Oregon College of Art and Craft; its own 2020 row (absorbed by Willamette)
# is a case.
ACQUIRER_ROWS = {("reprint 2018-11-20", "Pacific Northwest College of Art")}

STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
    "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
    "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
PLAIN_CLOSURE = re.compile(r"^(closed|closure|campus closure|branch campus closure|ceased|ends degree)", re.I)


# ------------------------------------------------------------------ helpers
def norm(name: str) -> str:
    s = name.lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\bsaint\b", "st", s)
    s = re.sub(r"\bst\.", "st", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\bthe\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fy_before(date: str) -> tuple[int | None, str]:
    """The last fiscal year (July to June) that ended before an announcement date."""
    d = (date or "").strip()
    m = re.match(r"^(\d{4})(?:-(\d{2}))?", d)
    if not m:
        return None, "no date"
    y, mo = int(m.group(1)), m.group(2)
    if mo is None:
        return y - 1, "year only: fiscal year ending the June before that year"
    return (y if int(mo) >= 7 else y - 1), "from the month"


def program_not_institution(name: str) -> bool:
    return bool(re.search(r"\((campus or program|undergraduate program)\)|campus$", name, re.I))


# ------------------------------------------------------------------ cases
def read_cases() -> list[dict]:
    cases = []
    with open(DATA / "tracker entries.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ev = r["event as listed"]
            if PLAIN_CLOSURE.match(ev) and "affiliated" not in ev.lower():
                continue
            if r["institution"] in ACQUIRERS or (r["source"], r["institution"]) in ACQUIRER_ROWS:
                continue
            cases.append({"group": "merger or acquisition", "source": r["source"], "name": r["institution"],
                          "state": r["state or region"], "announced": r["announced"], "event": ev,
                          "partner": r["partner"], "link": r["link"]})
    with open(DATA / "reversal cases.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cases.append({"group": "reversed closure or near-closure", "source": r["found in"], "name": r["institution"],
                          "state": r["state"], "announced": r["date of statement"], "event": r["reversal"],
                          "partner": "", "link": r["source"], "flags": r["flags"]})
    return cases


STOP = {"college", "university", "of", "and", "institute", "school", "state", "community", "st", "at",
        "county", "in", "for", "the", "center", "campus"}
CROSSWALK = "name crosswalk.csv"


def read_crosswalk() -> dict:
    """Hand resolutions of names the automatic match could not settle (unit ID, or a reason there is none)."""
    path = DATA / CROSSWALK
    out = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[(r["source"], r["name"])] = r
    return out


def match_names(cases: list[dict], frame: dict) -> list[dict]:
    index = defaultdict(set)
    names_of = defaultdict(set)
    for u, rows in frame.items():
        for r in rows.values():
            n = r.get("INSTNM", "")
            index[norm(n)].add(u)
            names_of[u].add(n)
    cross = read_crosswalk()
    candidates = []
    for c in cases:
        x = cross.get((c["source"], c["name"]))
        if x:
            ids = [i for i in (x["unitid"] or "").split(";") if i]
            c["match"] = "resolved by hand (name crosswalk.csv)" + (f": {x['note']}" if x.get("note") else "")
            c["unitids"] = ids if all(i in frame for i in ids) else []
            if ids and not c["unitids"]:
                c["match"] += "; unit ID not in the frame"
            continue
        if program_not_institution(c["name"]):
            c["match"], c["unitids"] = "a campus or program, not a separate institution in IPEDS", []
            continue
        hits = set(index.get(norm(c["name"]), set()))
        st = STATES.get(c["state"])
        if st and len(hits) > 1:
            in_state = {u for u in hits if any(r.get("STABBR") == st for r in frame[u].values())}
            hits = in_state or hits
        if len(hits) == 1:
            c["match"], c["unitids"] = "matched by name" + (" and state" if st else ""), sorted(hits)
            continue
        if hits:
            c["match"], c["unitids"] = "ambiguous: more than one unit ID; to be resolved by hand", sorted(hits)
        else:
            c["match"], c["unitids"] = "not found by name; to be resolved by hand", []
        # candidates for the hand resolution: units whose name holds every distinctive word, else any
        words = [w for w in norm(c["name"]).split() if w not in STOP and len(w) > 2]
        pool = [u for u, ns in names_of.items() if words and any(all(w in norm(n).split() for w in words) for n in ns)]
        if not pool:
            pool = [u for u, ns in names_of.items() if any(w in norm(n).split() for n in ns for w in words)]
        for u in sorted(pool)[:40]:
            yrs = sorted(frame[u])
            stabbr = sorted({r.get("STABBR", "") for r in frame[u].values()})
            candidates.append({"case": c["name"], "case state or region": c["state"], "source": c["source"],
                               "candidate unitid": u, "candidate names": " | ".join(sorted(names_of[u])),
                               "state": ";".join(stabbr), "first header year": yrs[0], "last header year": yrs[-1]})
    return candidates


# ------------------------------------------------------------------ main
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

    series_all, sector = {}, {}
    for u, rows in frame.items():
        sec = sector_of(rows)
        if sec is None:
            continue
        sector[u] = sec
        series_all[u] = [r for fy in range(et.FIRST_FY, et.LAST_FY + 1) if (r := et.year_record(u, fy, fin, ef, sec))]

    # sector medians of the anchored share, every college with c > 1 (section 3)
    pool = defaultdict(list)
    for u, ser in series_all.items():
        for r in ser:
            if r["valid"] and r["c"] > 1 and r["anchored share"] is not None:
                pool[(sector[u], r["fy"])].append(r["anchored share"])
    medians = {k: statistics.median(v) for k, v in pool.items() if v}

    def onset(w: dict, fallback: int | None) -> tuple[int | None, str]:
        p, c = w["primary"], w["check"]
        if p.get("group") == "crossed" and p.get("crossing"):
            return p["crossing"], "crossing year on the primary measure"
        if c.get("group") == "crossed" and c.get("crossing"):
            return c["crossing"], "crossing year on the check measure"
        return fallback, "last fiscal year before the announcement"

    def at(u: str, fy: int | None) -> dict | None:
        return next((r for r in series_all.get(u, []) if r["fy"] == fy and r["valid"]), None) if fy else None

    def describe(u: str, cap: int, fallback: int | None) -> dict:
        w = et.windows(series_all.get(u, []), cap, "no crossing before the announcement")
        t_on, rule = onset(w, fallback)
        measure = "primary" if w["primary"].get("type") in CLASSIFIED else "check" if w["check"].get("type") in CLASSIFIED else None
        rec = at(u, t_on)
        share = rec["anchored share"] if rec else None
        med = medians.get((sector.get(u), t_on))
        anchored = ("unclassified on anchoring" if share is None or med is None or (rec and rec["c"] <= 1)
                    else "anchored" if share >= med else "unanchored")
        return {"window": w, "onset": t_on, "onset rule": rule, "measure": measure, "record": rec,
                "anchored share": share, "sector median": med, "anchoring": anchored,
                "FTE at onset": rec["N"] if rec else None}

    # cases
    cases = read_cases()
    candidates = match_names(cases, frame)
    case_ids = set()
    for c in cases:
        ann = c["announced"]
        if ann.strip().upper() == "TBD" and c["source"].startswith("reprint 2018"):
            ann = "2018"   # listed as pending in the November 2018 reprint: announced by 2018
        fy, how = fy_before(ann)
        if ann != c["announced"]:
            how += "; TBD in the 2018 reprint, read as announced by 2018"
        c["window end"], c["window end rule"] = fy, how
        if len(c["unitids"]) != 1:
            continue
        u = c["unitids"][0]
        case_ids.add(u)
        c["sector"] = sector.get(u)
        cap = min(fy, et.LAST_FY) if fy else et.LAST_FY
        c |= describe(u, cap, cap if fy else None)
        if c["group"] == "merger or acquisition":
            states = [r["state"] for r in series_all.get(u, []) if r["valid"] and fy and fy - DISTRESS_YEARS < r["fy"] <= fy]
            c["distress check"] = ("passes" if any(s in DISTRESS_STATES for s in states) else
                                   "no year with data" if not states else "fails: not a case")

    # documented closures, classified the same way as in item 15 (end at the closure year)
    closures, converted = [], []
    for u, rows in frame.items():
        e = oc.exit_of(u, rows, years)
        if not e or "year" not in e or e["year"] < et.FIRST_HD:
            continue
        g = e["grounds"]
        if "c" in g or not ("a" in g or "b" in g):
            continue
        if sector.get(u) not in ("public", "private nonprofit") or u in case_ids:
            continue
        # Amendment 5: a closure listed as for-profit in any header year (a conversion)
        # has no observable anchor of the public or nonprofit kind; left out of the pool
        if any(r.get("CONTROL", "") == "3" for r in rows.values()):
            last = rows[max(rows)]
            converted.append({"unitid": u, "name": last.get("INSTNM", ""), "sector at closure": sector[u],
                              "for-profit header years": ";".join(str(y) for y in sorted(rows) if rows[y].get("CONTROL", "") == "3"),
                              "closure year": e["year"]})
            continue
        # onset fallback for a closure: the end of its item-15 window (its closure year,
        # capped at the last finance year), standing in for the announcement date that
        # IPEDS does not record
        d = describe(u, min(e["year"], et.LAST_FY), min(e["year"], et.LAST_FY))
        if d["onset rule"].startswith("last fiscal year"):
            d["onset rule"] = "end of the item-15 window (closure year, capped at the last finance year)"
        if d["measure"] is None or not d["FTE at onset"] or d["onset"] is None:
            continue
        last = rows[max(y for y in rows if y <= e["year"])] if any(y <= e["year"] for y in rows) else rows[min(rows)]
        closures.append({"unitid": u, "name": last.get("INSTNM", ""), "sector": sector[u], "closure year": e["year"],
                         "type": d["window"][d["measure"]]["type"], **d})

    # matched draw (section 2), deterministic order, seeded tie-breaks
    rng = random.Random(SEED)
    used, matched = set(), []
    eligible = [c for c in cases if len(c["unitids"]) == 1 and c.get("sector") in ("public", "private nonprofit")
                and c.get("measure") and c.get("FTE at onset") and c.get("onset")
                and c.get("distress check", "passes") == "passes"]
    for c in sorted(eligible, key=lambda c: (c["name"], c["unitids"][0])):
        cand = [k for k in closures if k["unitid"] not in used and k["sector"] == c["sector"] and k["measure"] == c["measure"]]
        keyed = [(abs(math.log(k["FTE at onset"]) - math.log(c["FTE at onset"])), abs(k["onset"] - c["onset"]), rng.random(), k)
                 for k in cand]
        keyed.sort(key=lambda t: t[:3])
        for dist, dyear, _, k in keyed[:MATCHES_PER_CASE]:
            used.add(k["unitid"])
            matched.append({"case": c["name"], "case unitid": c["unitids"][0], "closure unitid": k["unitid"],
                            "closure": k["name"], "sector": k["sector"], "closure year": k["closure year"],
                            "measure": k["measure"], "ending type": k["type"], "onset": k["onset"],
                            "onset rule": k["onset rule"], "FTE at onset": round(k["FTE at onset"], 1),
                            "log FTE distance": round(dist, 4), "onset year distance": dyear,
                            "anchored share at onset": k["anchored share"], "sector median": k["sector median"],
                            "anchoring": k["anchoring"]})

    # ------------------------------------------------------------------ write
    DATA.mkdir(parents=True, exist_ok=True)

    def typ(c, m):
        return c.get("window", {}).get(m, {}).get("type", "")

    def cross(c, m):
        return c.get("window", {}).get(m, {}).get("crossing", "")

    cols = ["group", "source", "name", "state", "announced", "event", "partner", "match", "unitid", "sector",
            "window end (fiscal year)", "window end rule", "primary type", "primary crossing", "check type",
            "check crossing", "measure used", "onset", "onset rule", "FTE at onset", "anchored share at onset",
            "sector median", "anchoring", "distress check (mergers)", "matched closures drawn", "flags", "link"]
    with open(DATA / "cases measured.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for c in cases:
            n = sum(1 for m in matched if m["case"] == c["name"] and c["unitids"] and m["case unitid"] == c["unitids"][0])
            flags = [c.get("flags", "")] + (c.get("record") or {}).get("flags", [])
            w.writerow([c["group"], c["source"], c["name"], c["state"], c["announced"], c["event"], c["partner"],
                        c["match"], ";".join(c["unitids"]), c.get("sector", ""), c["window end"] or "",
                        c["window end rule"], typ(c, "primary"), cross(c, "primary"), typ(c, "check"), cross(c, "check"),
                        c.get("measure") or "", c.get("onset") or "", c.get("onset rule", ""),
                        round(c["FTE at onset"], 1) if c.get("FTE at onset") else "",
                        c.get("anchored share") if c.get("anchored share") is not None else "",
                        c.get("sector median") if c.get("sector median") is not None else "",
                        c.get("anchoring", ""), c.get("distress check", ""), n,
                        "; ".join(x for x in flags if x), c["link"]])
    with open(DATA / "matched closures.csv", "w", newline="", encoding="utf-8") as f:
        mcols = list(matched[0]) if matched else ["case"]
        w = csv.DictWriter(f, fieldnames=mcols)
        w.writeheader()
        w.writerows(matched)
    with open(DATA / "sector medians.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sector", "fiscal year", "colleges with c > 1 and an anchored share", "median anchored share"])
        for (s, fy), v in sorted(pool.items()):
            w.writerow([s, fy, len(v), medians[(s, fy)]])
    with open(DATA / "case series.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case", "unitid", "fiscal year", "W", "E", "N", "A", "O", "c", "g", "state", "anchored share"]
                   + [f"anchor: {s}" for s in et.SOURCES] + ["flags"])
        for c in cases:
            if len(c["unitids"]) != 1:
                continue
            for r in series_all.get(c["unitids"][0], []):
                if not r["valid"]:
                    continue
                w.writerow([c["name"], c["unitids"][0], r["fy"], r["W"], r["E"], r["N"], r["A"], r["O"], r["c"], r["g"],
                            r["state"], r["anchored share"]]
                           + [(r["anchors"] or {}).get(s, "") if r["anchors"] else "" for s in et.SOURCES]
                           + ["; ".join(r["flags"])])
    with open(DATA / "converted closures left out.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["unitid", "name", "sector at closure", "for-profit header years", "closure year"])
        w.writeheader()
        w.writerows(sorted(converted, key=lambda r: r["name"]))
    with open(DATA / "name matching.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "state or region", "source", "match", "unitids", "names in the header files"])
        for c in cases:
            names = sorted({frame[u][y].get("INSTNM", "") for u in c["unitids"] for y in frame[u]})
            w.writerow([c["name"], c["state"], c["source"], c["match"], ";".join(c["unitids"]), " | ".join(names)])

    with open(DATA / "name candidates.csv", "w", newline="", encoding="utf-8") as f:
        cc = ["case", "case state or region", "source", "candidate unitid", "candidate names", "state",
              "first header year", "last header year"]
        w = csv.DictWriter(f, fieldnames=cc)
        w.writeheader()
        w.writerows(candidates)
    tally = Counter(c["match"].split(":")[0] for c in cases)
    results = {
        "note": "Item 15b, exploratory, under anchor and voice protocol.md (Amendments 1 to 5). Measures only: "
                "no outcome or voice record is read here.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "settings": {"seed": SEED, "matched closures per case": MATCHES_PER_CASE,
                     "distress check years": DISTRESS_YEARS, "ending-type rule": "ending types.py, unchanged"},
        "cases": len(cases), "name matching": dict(tally),
        "cases by group and distress check": {f"{g} | {d}": n for (g, d), n in sorted(Counter(
            (c["group"], c.get("distress check", "n/a")) for c in cases).items())},
        "eligible for the matched draw": len(eligible), "matched closures drawn": len(matched),
        "closure pool (public and nonprofit, classified, not a case)": len(closures),
        "converted closures left out of the pool (Amendment 5)": len(converted),
        "cases by ending type (measure used)": dict(Counter(
            (c["window"][c["measure"]]["type"] if c.get("measure") else "not classified") for c in cases if c.get("window"))),
        "cases by anchoring at onset": dict(Counter(c.get("anchoring", "not measured") for c in cases)),
        "header files used": hd_used, "header files not served": hd_missing, "finance and enrollment files": log,
    }
    (DATA / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: results[k] for k in ("cases", "name matching", "eligible for the matched draw", "matched closures drawn")}, indent=1))
    print(f"Wrote {DATA}")


if __name__ == "__main__":
    main()
