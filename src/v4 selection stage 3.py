"""
v4 channel selection, stage 3: confirmation on the later scoring year
("channel selection protocol.md", section 4, Amendments 2 and 4).

Reads the committed stage 1 and 2 result (which dimensions were carried),
the committed gap values for the 2019 frame and step 1's inputs (for size),
and then, and only then, the 2019 frame's closure outcomes from the IPEDS
header files HD2019 onward (every file released; primary coding of protocol
v2).

Models, each fitted and scored out of fold exactly as in stages 1 and 2:
    (0) size and sector
    (1) size, sector and the best single carried gap (highest stage-1 gain)
    (2) size, sector and the carried gaps combined by the maximum
    (3) size, sector and the carried gaps as separate features
on the institutions with every carried dimension available.

The pre-registered prediction (several parts beat one) is tested only if
at least two dimensions were carried; otherwise (1), (2) and (3) coincide,
and the result says the prediction is not testable on these gaps.
Amendment 4: (a) the carried price gap on the whole frame; (b) the four-year
gap on public and private nonprofit institutions only, with three
institutions whose standard bachelor's exceeds four years marked unavailable
by name, and a sensitivity analysis without every institution with r_on = 0.
A gap enters v4 (for its group) only if its gain over size and sector has a
paired 95% bootstrap interval above zero on this frame.

Output: data/v4 channels/selection stage 3.json

Usage (GitHub Actions only, via v4_selection_stage_3.yml):
    cd src
    python "v4 selection stage 3.py"
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("stages", HERE / "v4 selection stages 1 and 2.py")
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)
OUT = st.DIR / "selection stage 3.json"
FRAME = 2019
TRIED = list(range(2019, 2027))
LONGER_PROGRAMS = {"Northeastern University", "Southern California Institute of Architecture",
                   "Boston Architectural College"}


def load_2019() -> list[dict]:
    st.FRAME = FRAME
    return st.load()


def outcomes_2019(ids: list[str]) -> tuple[dict, list, list]:
    coding = st.coding
    files, tables, not_found = [], {}, []
    for y in TRIED:
        try:
            hd = coding.download_hd(y)
        except SystemExit:
            if y == FRAME:
                raise
            not_found.append(f"HD{y}")
            continue
        t = coding.rows_by_id(hd["csv"])
        if len(t) < st.MIN_HD_ROWS:
            raise SystemExit(f"HD{y} yielded {len(t)} institutions; misread. Nothing recorded.")
        tables[y] = t
        files.append({k: v for k, v in hd.items() if k != "csv"} | {"institutions read": len(t)})
    years = sorted(tables)
    coding.SCORING_YEAR, coding.FILES = FRAME, years
    return {u: coding.code(u, {y: tables[y].get(u) for y in years}) for u in ids}, files, not_found


def main() -> None:
    sel = json.loads((st.DIR / "selection stages 1 and 2.json").read_text(encoding="utf-8"))
    carried = sel["stage 2"]["carried (Decision B)"]
    rows = load_2019()
    out, files, not_found = outcomes_2019([r["unitid"] for r in rows])
    for r in rows:
        r["closed"] = bool(out[r["unitid"]]["closed or failed (primary)"])
    base = [r for r in rows if r["log FTE"] is not None]
    result = {
        "protocol": "channel selection protocol.md, section 4, Amendments 2 and 4: stage 3 (2019 frame)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "frame": FRAME, "header files": files, "header files not yet released": not_found,
        "carried from stages 1 and 2": carried, "institutions in frame": len(rows), "with size": len(base),
        "closures (primary) among those with size": sum(r["closed"] for r in base),
        "note": "Selection-stage performance, used only to choose dimensions; never an estimate of v4's accuracy.",
    }
    if not carried:
        result["verdict"] = "no dimension was carried; v4 has no IPEDS claim gap from this item"
    else:
        cov = [r for r in base if all(r[st.IOTA[d]] for d in carried)]
        best = carried[0]
        for r in cov:
            r["D_max"] = max(r[st.DIRECTION_FREE[d]] for d in carried)
        m1 = st.compare(cov, [], st.DIMENSIONS[best], "size and sector", f"size, sector and {best}")
        result["(1) best single gap against size and sector"] = m1 | {"gap": best}
        result["coverage"] = st.describe(cov, [r for r in base if r not in cov])
        enters = {d: None for d in carried}
        if len(carried) == 1:
            enters[best] = m1.get("gain 95% bootstrap", [0])[0] > 0
            result["prediction (several parts beat one)"] = ("not testable on these gaps: only one dimension was "
                                                             "carried, so models (1), (2) and (3) coincide")
        else:
            sep = [k for d in carried for k in st.DIMENSIONS[d]]
            m2 = st.compare(cov, st.DIMENSIONS[best], ["D_max"], f"size, sector and {best}", "size, sector and the maximum")
            m3 = st.compare(cov, st.DIMENSIONS[best], sep, f"size, sector and {best}", "size, sector and the carried gaps")
            result["(2) maximum against (1)"], result["(3) separate features against (1)"] = m2, m3
            lo2, lo3 = m2["gain 95% bootstrap"][0], m3["gain 95% bootstrap"][0]
            result["prediction (several parts beat one)"] = (
                "supported" if lo2 > 0 and lo3 > 0 else
                "in the predicted direction, not separated from zero" if m2["gain"] > 0 and m3["gain"] > 0 else
                "not supported")
            for d in carried:
                g = st.compare(cov, [], st.DIMENSIONS[d], "size and sector", f"size, sector and {d}")
                result[f"{d} against size and sector"] = g
                enters[d] = g["gain 95% bootstrap"][0] > 0
        # Amendment 4 (b): the four-year gap, public and private nonprofit institutions only
        pn = [r for r in base if r["control"] in ("public", "private nonprofit") and r["iota_4yr"]
              and r["name"] not in LONGER_PROGRAMS]
        m4 = st.compare(pn, [], st.DIMENSIONS["four-year"], "size and sector", "size, sector and four-year")
        result["(b) four-year gap, public and private nonprofit"] = m4 | {
            "marked unavailable by name (Amendment 4)": sorted(LONGER_PROGRAMS),
            "coverage": st.describe(pn, [r for r in base if r["control"] in ("public", "private nonprofit") and r not in pn]),
            "sensitivity: without institutions with r_on = 0": st.compare(
                [r for r in pn if r["D_4yr"] < 1.0], [], st.DIMENSIONS["four-year"], "size and sector",
                "size, sector and four-year")}
        enters["four-year (public and private nonprofit)"] = m4.get("gain 95% bootstrap", [0])[0] > 0
        result["enters v4 (Amendment 4)"] = enters
        result["verdict"] = ("enter v4: " + ", ".join(d for d, v in enters.items() if v)) if any(enters.values()) \
            else "no gap is confirmed; v4 has no IPEDS claim gap from this item"
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("header files", "coverage")}, indent=1))


if __name__ == "__main__":
    main()
