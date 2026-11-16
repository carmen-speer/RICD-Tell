"""
A second candidate for the meta channel P_m: the thickness of each
institution's administrative layer, from the same IPEDS Human Resources
"Employees by Assigned Position" files (EAP) that meta_channel.py reads.

Why. The meta layer is the layer that stands between what an institution
says about itself and what it does: it writes the official account,
interprets the operational reality upward and decides what passes between
the two. In a college that is the administrative class, as distinct from
the instructional staff who do the operational work. The hypothesis to be
tested is that the thinner this layer, the healthier the institution (the
less resource debt it carries); so the candidate meta-channel value is
1 - (the administrative share), and higher means thinner.

What is measured. Since fall 2012 the EAP files break staff down by
federal occupational category (EAPCAT). Each category used here is found
by its label in that year's data dictionary, never by an assumed code:

  management           "Management occupations" (the old "executive,
                       administrative and managerial" group)
  business             "Business and financial operations occupations"
  community/legal/media  "Community, social service, legal, arts, design,
                       entertainment, sports, and media occupations"
                       (counselors, development and alumni officers,
                       attorneys, writers and editors, communications)
  office support       "Office and administrative support occupations"
  student affairs      "Student and academic affairs and other education
                       services occupations" (librarians excluded)
  instructional        "Instructional staff, total"

Two shares are computed, each on full-time-equivalent staff (full-time
plus one third of part-time, the IPEDS convention), and also on headcount:

  core  = (management + business + community/legal/media)
          / (those + instructional)
  broad = (core categories + office support + student affairs)
          / (those + instructional)

The core share is the closest match to the administrative and
"other professional" class (excluding information technology, research
and health staff, whose work is not administrative mediation); the broad
share adds the support staff that administration commands. A category
whose label cannot be matched to exactly one code in some year is
recorded as unresolved for that year, with the dictionary's full label
table, and the shares that need it are not computed for that year; the
run does not guess.

No closure outcome is read here, and nothing frozen uses these files. The
hypothesis itself is tested separately ("administrative layer test.py"),
on the development institutions only, so that the prospective retest can
still test it blind.

Usage (GitHub Actions only, via administrative_layer.yml):
    cd src
    python "administrative layer.py" --first 2012
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re

import v2_common as v2
import meta_channel as mc

LAYER_PATH = mc.OUT_DIR / "administrative layer.json"
CHECK_PATH = mc.OUT_DIR / "administrative layer check.json"
PT_WEIGHT = 1 / 3          # IPEDS full-time-equivalent convention
JUMP = 0.20
EXCLUDE = ("faculty status", "tenure", "medical", "with faculty", "without faculty", "new hire")

CATEGORIES = {
    "management": lambda l: l.startswith("management occupations") or l == "management",
    "business": lambda l: "business and financial operations" in l,
    "community/legal/media": lambda l: "community" in l and "legal" in l,
    "office support": lambda l: "office and administrative support" in l,
    "student affairs": lambda l: "student and academic affairs" in l and "librar" not in l,
    "instructional": lambda l: l in mc.WANTED,
}
CORE = ("management", "business", "community/legal/media")
BROAD = CORE + ("office support", "student affairs")


def resolve(labels: dict[str, str]) -> tuple[dict[str, dict], dict[str, list]]:
    found, unresolved = {}, {}
    for name, match in CATEGORIES.items():
        hits = [(c, l) for c, l in labels.items()
                if match(mc.norm(l)) and not any(x in l.lower() for x in EXCLUDE)]
        if len(hits) == 1:
            found[name] = {"EAPCAT": hits[0][0], "label": hits[0][1]}
        else:
            unresolved[name] = hits
    return found, unresolved


def read_year(year: int, required: bool) -> dict | None:
    got = mc.fetch(f"EAP{year}.zip", required)
    if got is None:
        return None
    data, url = got
    dict_got = mc.fetch(f"EAP{year}_Dict.zip", True)
    labels = mc.eapcat_labels(dict_got[0])
    if not labels:
        raise SystemExit(f"EAP{year}: no EAPCAT codes were read from the data dictionary. Nothing recorded.")
    found, unresolved = resolve(labels)
    by_code = {v["EAPCAT"]: k for k, v in found.items()}
    name, text = mc.first_csv(data)
    values = {}
    for r in mc.rows(text):
        cat = by_code.get(r.get("EAPCAT"))
        if not cat or not r.get("UNITID"):
            continue
        ft, pt = mc.number(r.get("EAPFT")), mc.number(r.get("EAPPT"))
        if ft is None and pt is None:
            continue
        values.setdefault(r["UNITID"], {})[cat] = [int(ft or 0), int(pt or 0)]
    return {"file": {"table": f"EAP{year}", "url": url, "csv": name,
                     "zip sha256": hashlib.sha256(data).hexdigest(), "dictionary url": dict_got[1],
                     "categories": found,
                     "unresolved categories": {k: [{"EAPCAT": c, "label": l} for c, l in v]
                                               for k, v in unresolved.items()},
                     "dictionary labels": labels if unresolved else "all categories resolved"},
            "values": values}


def shares(rec: dict, cats: tuple, fte: bool) -> float | None:
    """Administrative share of (cats + instructional); None where a needed category is missing."""
    w = PT_WEIGHT if fte else 1.0
    size = lambda c: rec[c][0] + w * rec[c][1]
    if "instructional" not in rec:
        return None
    admin = sum(size(c) for c in cats if c in rec)
    total = admin + size("instructional")
    return admin / total if total > 0 else None


def checks(years: dict, sec: dict) -> dict:
    fy = sorted(years)
    latest = fy[-1]
    usable = lambda y, cats: all(c in years[y]["file"]["categories"] for c in cats + ("instructional",))
    out = {"years read (fall)": fy, "fiscal years they are assigned to": [y + 1 for y in fy],
           "categories resolved per year": {str(y): sorted(years[y]["file"]["categories"]) for y in fy}}
    for label, cats in (("core", CORE), ("broad", BROAD)):
        per_year, ratio_flip = {}, {}
        series = {}
        for y in fy:
            if not usable(y, cats):
                per_year[str(y)] = "not computed: a needed category was not resolved this year"
                continue
            s = {u: shares(r, cats, True) for u, r in years[y]["values"].items()}
            s = {u: v for u, v in s.items() if v is not None}
            series[y] = s
            per_year[str(y)] = {"institutions": len(s), "share (FTE)": mc.quantiles(list(s.values()))}
            ratio_flip[str(y)] = round(sum(v > 0.5 for v in s.values()) / len(s), 4) if s else None
        block = {"per year": per_year,
                 "fraction of institutions where administrative staff outnumber instructional staff (FTE)": ratio_flip}
        if latest in series:
            block[f"by sector, fall {latest} (sector from {sec['file']})"] = {
                name: mc.quantiles([v for u, v in series[latest].items() if sec["sector"].get(u) == code])
                for code, name in mc.SECTOR_NAMES.items()}
        moves, jumps, pairs = [], 0, 0
        ys = sorted(series)
        for a, b in zip(ys, ys[1:]):
            for u in series[a].keys() & series[b].keys():
                d = abs(series[b][u] - series[a][u])
                moves.append(d)
                pairs += 1
                jumps += d >= JUMP
        block["year-to-year change in an institution's share"] = {
            "pairs": pairs, "change": mc.quantiles(moves), f"changes of {JUMP} or more": jumps,
            f"share of changes of {JUMP} or more": round(jumps / pairs, 4) if pairs else None}
        if ys:
            last11 = ys[-11:]
            block["coverage of the tracker's institutions"] = {
                name: {"institutions": len(ids),
                       "with a value in the latest year": sum(u in series[ys[-1]] for u in ids),
                       f"with values in all of fall {last11[0]}-{last11[-1]}":
                           sum(all(u in series[y] for y in last11) for u in ids)}
                for name, ids in mc.frames().items()}
        out[f"{label} administrative share"] = block
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2012)
    a = ap.parse_args()
    if a.first < 2012:
        raise SystemExit("Files before fall 2012 use the old staff categories and are not read.")
    years, not_served = {}, []
    for y in range(a.first, datetime.date.today().year + 1):
        got = read_year(y, required=(y <= 2023))
        if got is None:
            not_served.append(f"EAP{y}")
        else:
            years[y] = got
    sec = mc.sectors()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    v2.write_json(LAYER_PATH, {
        "measure": ("[full-time, part-time] headcounts by category; core and broad administrative shares are "
                    "computed from them (see src/administrative layer.py); fall year Y is fiscal year Y+1"),
        "written at (UTC)": now, "files": [years[y]["file"] for y in sorted(years)],
        "files not served": not_served,
        "by fall year": {str(y): years[y]["values"] for y in sorted(years)}})
    v2.write_json(CHECK_PATH, {"written at (UTC)": now,
                               "note": "Checks of the measurement only; no closure outcome is read.",
                               **checks(years, sec)})
    c = json.loads(CHECK_PATH.read_text())
    print(json.dumps({k: c[k] for k in ("years read (fall)", "categories resolved per year")}, indent=1))


def candidate(layer: dict, unitid: str, fiscal_years: list[int], cats: tuple = CORE):
    """For a scoring window: (meta_obs, mask) with meta_obs = 1 - administrative share (higher = thinner),
    aligned to fiscal_years. Years without a value are masked out, never filled."""
    import numpy as np
    obs, mask = np.zeros(len(fiscal_years)), np.zeros(len(fiscal_years), dtype=bool)
    for i, fy in enumerate(fiscal_years):
        rec = layer["by fall year"].get(str(fy - 1), {}).get(unitid)
        s = shares(rec, cats, True) if rec else None
        if s is not None:
            obs[i], mask[i] = 1 - s, True
    return obs, mask


if __name__ == "__main__":
    main()
