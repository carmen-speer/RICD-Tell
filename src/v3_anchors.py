"""
Anchor flows for "sampling protocol v3.md" (RICD §10.5b.13c).

For every institution in the IPEDS files of each scoring year (2014 for the
training set, 2019 for the v2 test set and the v3 test), this records the
inputs of the anchor capacity

    A(t) = W(t) · [ θ_approp · f_approp(t) + θ_gift · f_gift(t) + θ_par · S_par(t) ]

where each f_k is the three-year average of that flow divided by the
institution's total expenses over the same years, and S_par is 1 for a
member of a multi-institution system whose parent draws no return from it.
The weights θ are fitted later with the classifier; this step reads flows
only. Every record is dated at or before its scoring year (fiscal years
2012-2014 for 2014, 2017-2019 for 2019), as §10.5b.13c's measurement rule
requires. No institution's outcome is read.

Codes, each chosen from NCES's own dictionary title as recorded in
data/v3/anchor codes diagnostic.json:

  public (F1A)   appropriations  F1B10 federal + F1B11 state + F1B12 local
                 gifts           F1B16 gifts, including contributions from
                                 affiliated organizations
                 total expenses  F1D02
  private (F2)   appropriations  F2D02 federal + F2D03 state + F2D04 local
                 gifts           F2D08A private gifts + F2D09 contributions
                                 from affiliated entities
                 total expenses  F2B02
  for-profit (F3) appropriations F3D02A federal + F3D03A state + F3D03C local
                                 (separate lines exist from fiscal 2014 on;
                                 earlier years have only lines that include
                                 grants and contracts, so they are not read)
                 gifts           none: F3D04 joins gifts with grants and
                                 contracts, which are paid work, not gifts
                 total expenses  F3B02, or F3D09 total revenues where F3B02
                                 is empty

Not read as anchors: capital appropriations and capital grants and gifts
(F1B20, F1B21), which pay for buildings and cannot absorb an operating
deficit, and private grants and contracts, which are exchange.

System membership comes from the directory file of the scoring year:
S_par = 1 where F1SYSTYP = 1 (a member of a multi-institution or
multi-campus organization) and CONTROL is 1 or 2 (public or private
nonprofit). For-profit chains (CONTROL 3) are excluded because their
parent draws a return from its members. HBCU, TRIBAL and LANDGRNT and
religious affiliation (RELAFFIL) are recorded as descriptors only; any
money they bring already appears in the flows above.

Each finance ZIP is read from its first CSV, the file the scoring pipeline
itself reads (fetch_live_data.download_ipeds_finance_bulk).

The result is written to data/v3/anchors.json.

Usage (GitHub Actions only, via v3_anchors.yml):
    cd src
    python v3_anchors.py
"""

from __future__ import annotations

import csv
import datetime
import io
import zipfile

import v2_common as v2
import v3_common as v3
import diagnose_v2_finance_codes as d2

OUT_PATH = v3.V3_DIR / "anchors.json"
COHORTS = {"2014": (2012, 2013, 2014), "2019": (2017, 2018, 2019)}
FORMS = {"public": "F1A", "private": "F2", "forprofit": "F3"}
CODES = {
    "public": {"approp": ("F1B10", "F1B11", "F1B12"), "gift": ("F1B16",), "expenses": ("F1D02",)},
    "private": {"approp": ("F2D02", "F2D03", "F2D04"), "gift": ("F2D08A", "F2D09"), "expenses": ("F2B02",)},
    "forprofit": {"approp": ("F3D02A", "F3D03A", "F3D03C"), "gift": (), "expenses": ("F3B02",),
                  "expenses fallback": ("F3D09",)},
}
FORPROFIT_FIRST_YEAR = 2014       # first fiscal year with separate appropriation lines on F3
MIN_ROWS = 1000                   # a finance or directory file read with fewer rows is a reading failure


def clean(h: str) -> str:
    return h.strip().lstrip("\ufeff").lstrip("\u00ef\u00bb\u00bf").strip().upper()


def read_csv(data: bytes, prefer_first: bool = True) -> list[dict]:
    z = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in z.namelist() if n.lower().endswith(".csv")]
    if not prefer_first:
        names = sorted(names, key=lambda n: ("_rv" in n.lower(), len(n)))
    reader = csv.DictReader(io.StringIO(z.read(names[0]).decode("latin-1")))
    fields = {f: clean(f) for f in reader.fieldnames or []}
    return [{fields[k]: (v or "").strip() for k, v in r.items() if k in fields} for r in reader]


def total(row: dict, codes: tuple) -> float | None:
    vals = [d2.number(row.get(c, "")) for c in codes]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def finance_year(sector: str, fy: int, log: dict) -> dict:
    table = f"F{str(fy - 1)[2:]}{str(fy)[2:]}_{FORMS[sector]}"
    data, src = d2.fetch(table + ".zip")
    if data is None:
        raise SystemExit(f"{table}: not served ({src})")
    rows = read_csv(data)
    if len(rows) < MIN_ROWS:
        raise SystemExit(f"{table}: only {len(rows)} rows read")
    codes = CODES[sector]
    present = set(rows[0]) if rows else set()
    missing = [c for k in ("approp", "gift", "expenses") for c in codes[k] if c not in present]
    if sector == "forprofit" and fy < FORPROFIT_FIRST_YEAR:
        missing = [c for c in missing if c not in codes["approp"]]
    if missing:
        raise SystemExit(f"{table}: columns not found: {missing}")
    out = {}
    for r in rows:
        u = r.get("UNITID", "")
        if not u:
            continue
        exp = total(r, codes["expenses"])
        if (exp is None or exp == 0) and "expenses fallback" in codes:
            exp = total(r, codes["expenses fallback"])
        approp = None if (sector == "forprofit" and fy < FORPROFIT_FIRST_YEAR) else total(r, codes["approp"])
        gift = total(r, codes["gift"]) if codes["gift"] else 0.0
        out[u] = {"approp": approp, "gift": gift, "expenses": exp}
    log[table] = {"source": src, "rows": len(rows)}
    return out


def directory(year: int, log: dict) -> dict:
    hd, src = d2.fetch(f"HD{year}.zip")
    ic, src2 = d2.fetch(f"IC{year}.zip")
    if hd is None or ic is None:
        raise SystemExit(f"HD{year} or IC{year} not served")
    h = read_csv(hd, prefer_first=False)
    c = {r.get("UNITID", ""): r for r in read_csv(ic, prefer_first=False)}
    if len(h) < MIN_ROWS or len(c) < MIN_ROWS:
        raise SystemExit(f"HD{year}/IC{year}: too few rows ({len(h)}, {len(c)})")
    log[f"HD{year}"], log[f"IC{year}"] = {"source": src, "rows": len(h)}, {"source": src2, "rows": len(c)}
    out = {}
    for r in h:
        u = r.get("UNITID", "")
        if not u:
            continue
        name = r.get("F1SYSNAM", "")
        out[u] = {
            "control": r.get("CONTROL", ""),
            "system member": r.get("F1SYSTYP", "") == "1",
            "system name": "" if name in ("", "-2", "-1") else name,
            "HBCU": r.get("HBCU", "") == "1",
            "TRIBAL": r.get("TRIBAL", "") == "1",
            "LANDGRNT": r.get("LANDGRNT", "") == "1",
            "RELAFFIL": c.get(u, {}).get("RELAFFIL", ""),
        }
    return out


def cohort(year: str, years: tuple, log: dict) -> dict:
    fin = {s: {fy: finance_year(s, fy, log) for fy in years} for s in FORMS}
    dirs = directory(int(year), log)
    out = {}
    for u, dinfo in dirs.items():
        # an institution's form is the one holding its row in the scoring year, as in v2_common.finance_sector
        sector = next((s for s in FORMS if u in fin[s][years[-1]]), None)
        if sector is None:
            continue
        per_year = {fy: fin[sector][fy].get(u) for fy in years}
        used = {fy: r for fy, r in per_year.items() if r and r["expenses"] and r["expenses"] > 0}
        rec = {"form": sector, **dinfo, "fiscal years read": sorted(used)}
        for k in ("approp", "gift"):
            ys = [fy for fy, r in used.items() if r[k] is not None]
            num = sum(used[fy][k] for fy in ys)
            den = sum(used[fy]["expenses"] for fy in ys)
            rec[f"f_{k}"] = round(num / den, 6) if den > 0 else None
        rec["W"] = round(sum(r["expenses"] for r in used.values()) / len(used), 2) if used else None
        rec["S_par"] = 1 if (dinfo["system member"] and dinfo["control"] in ("1", "2")) else 0
        out[u] = rec
    return out


def main() -> None:
    log: dict = {}
    result = {
        "protocol": "sampling protocol v3.md",
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "machine": v2.machine(),
        "codes": CODES,
        "cohorts": {},
    }
    for year, years in COHORTS.items():
        recs = cohort(year, years, log)
        result["cohorts"][year] = {
            "fiscal years": list(years),
            "institutions": len(recs),
            "with f_approp > 0": sum(1 for r in recs.values() if (r["f_approp"] or 0) > 0),
            "with f_gift > 0": sum(1 for r in recs.values() if (r["f_gift"] or 0) > 0),
            "with S_par = 1": sum(r["S_par"] for r in recs.values()),
            "records": recs,
        }
        print(year, {k: v for k, v in result["cohorts"][year].items() if k != "records"})
    result["files read"] = log
    v2.write_json(OUT_PATH, result)


if __name__ == "__main__":
    main()
