"""
Meta-channel measurement 3: the secure (tenure-protected) share of each
institution's instructional staff, from the IPEDS staffing files (EAP),
fall 2012 on.

Why: RICD Spine §15.2 asks that a meta-channel proxy bear on whether a
population can actually transmit dissent accurately, and names
contingent-versus-secure staffing for higher education because job security
bears directly on that. Full-time status is not security: a full-time
instructor on an annual contract can be let go for dissent. Tenure status is
the closer reading, and IPEDS records it.

Each category is found by its label in that year's data dictionary, never by
an assumed code:
  total        "Instructional staff, total"
  tenured      "Instructional staff, Tenured"
  track        "Instructional staff, On Tenure Track"
  indefinite   "Instructional staff, Indefinite contract"   (fall 2016 on)
A category whose label does not match exactly one code in a year is recorded
as unresolved for that year, with the full label table, and the shares that
need it are not computed for that year.

Shares, over all instructional staff (full-time plus part-time headcount):
  secure (primary)        (tenured + tenure-track) / total
  tenured only            tenured / total
  secure with indefinite  (tenured + tenure-track + indefinite contract) / total, fall 2016 on
Which version the retest uses is decided after the development test, before
the retest is fixed. Within a resolved category an institution with no row
has none of that staff (IPEDS writes no zero rows). Fall year Y is fiscal
year Y+1.

Output: data/meta channel/tenure share.json (counts by fall year) and
tenure share check.json (checks of the measurement only; no outcome read).

Usage (GitHub Actions):
    cd src
    python "tenure share.py" --first 2012
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json

import v2_common as v2
import meta_channel as mc

LAYER_PATH = mc.OUT_DIR / "tenure share.json"
CHECK_PATH = mc.OUT_DIR / "tenure share check.json"
JUMP = 0.20
LABELS = {"total": "instructional staff total",
          "tenured": "instructional staff tenured",
          "track": "instructional staff on tenure track",
          "indefinite": "instructional staff indefinite contract"}
VERSIONS = {"secure (primary)": (("tenured", "track"), ("total",)),
            "tenured only": (("tenured",), ("total",)),
            "secure with indefinite": (("tenured", "track", "indefinite"), ("total",))}


def resolve(labels: dict[str, str]) -> tuple[dict, dict]:
    found, unresolved = {}, {}
    for name, want in LABELS.items():
        hits = [(c, l) for c, l in labels.items() if mc.norm(l) == want]
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


def share(rec: dict, version: str, resolved) -> float | None:
    """A version's share for one institution-year; None unless every needed category was resolved
    that year and the institution reports instructional staff."""
    num, den = VERSIONS[version]
    if any(c not in resolved for c in num + den) or "total" not in rec:
        return None
    total = sum(rec["total"])
    if total <= 0:
        return None
    return min(1.0, sum(sum(rec[c]) for c in num if c in rec) / total)


def resolved_by_fall(layer: dict) -> dict[str, set]:
    return {f["table"][3:]: set(f["categories"]) for f in layer["files"]}


def checks(years: dict, sec: dict) -> dict:
    fy = sorted(years)
    out = {"years read (fall)": fy, "fiscal years they are assigned to": [y + 1 for y in fy],
           "categories resolved per year": {str(y): sorted(years[y]["file"]["categories"]) for y in fy}}
    for version in VERSIONS:
        per_year, series = {}, {}
        for y in fy:
            res = years[y]["file"]["categories"]
            s = {u: share(r, version, res) for u, r in years[y]["values"].items()}
            s = {u: v for u, v in s.items() if v is not None}
            if not s:
                per_year[str(y)] = "not computed: a needed category was not resolved this year"
                continue
            series[y] = s
            per_year[str(y)] = {"institutions": len(s), "share": mc.quantiles(list(s.values())),
                                "fraction with no tenured or tenure-track staff": round(
                                    sum(v == 0 for v in s.values()) / len(s), 4)}
        block = {"per year": per_year}
        ys = sorted(series)
        if ys:
            block[f"by sector, fall {ys[-1]} (sector from {sec['file']})"] = {
                name: mc.quantiles([v for u, v in series[ys[-1]].items() if sec["sector"].get(u) == code])
                for code, name in mc.SECTOR_NAMES.items()}
        moves, jumps, pairs = [], 0, 0
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
            block["coverage of the tracker's institutions"] = {
                name: {"institutions": len(ids), "with a value in the latest year": sum(u in series[ys[-1]] for u in ids)}
                for name, ids in mc.frames().items()}
        out[version] = block
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2012)
    a = ap.parse_args()
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
        "measure": ("[full-time, part-time] headcounts of instructional staff: total, tenured, on tenure "
                    "track, indefinite contract; shares computed from them (see src/tenure share.py); "
                    "fall year Y is fiscal year Y+1"),
        "written at (UTC)": now, "files": [years[y]["file"] for y in sorted(years)],
        "files not served": not_served,
        "by fall year": {str(y): years[y]["values"] for y in sorted(years)}})
    v2.write_json(CHECK_PATH, {"written at (UTC)": now,
                               "note": "Checks of the measurement only; no closure outcome is read.",
                               **checks(years, sec)})
    c = json.loads(CHECK_PATH.read_text())
    print(json.dumps({k: c[k] for k in ("years read (fall)", "categories resolved per year")}, indent=1))


if __name__ == "__main__":
    main()
