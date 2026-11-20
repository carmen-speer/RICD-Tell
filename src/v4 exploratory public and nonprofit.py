"""
EXPLORATORY, not part of channel selection: stage 1 of "channel selection
protocol.md" repeated on public and private nonprofit institutions only
(2014 frame), where size and sector separate closures less sharply than in
the whole frame. The selection already made (stages 1 and 2, committed in
data/v4 channels/"selection stages 1 and 2.json") is not changed by anything
here, and nothing here is used to choose v4's dimensions.

Same features, folds, seeds and bootstrap as stage 1. Also repeated within
private nonprofit institutions alone.

Output: data/v4 channels/exploratory public and nonprofit.json

Usage (GitHub Actions only, via v4_exploratory_public_nonprofit.yml):
    cd src
    python "v4 exploratory public and nonprofit.py"
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
OUT = st.DIR / "exploratory public and nonprofit.json"


def run(group: list[dict]) -> dict:
    res = {}
    for dim, feats in st.DIMENSIONS.items():
        cov = [r for r in group if r[st.IOTA[dim]]]
        res[dim] = st.compare(cov, [], feats, "size and sector", f"size, sector and {dim}")
        res[dim]["coverage"] = st.describe(cov, [r for r in group if not r[st.IOTA[dim]]])
    return res


def main() -> None:
    rows = st.load()
    out, files = st.outcomes([r["unitid"] for r in rows])
    for r in rows:
        r["closed"] = bool(out[r["unitid"]]["closed or failed (primary)"])
    base = [r for r in rows if r["log FTE"] is not None]
    pn = [r for r in base if r["control"] in ("public", "private nonprofit")]
    np_only = [r for r in base if r["control"] == "private nonprofit"]
    result = {
        "status": "EXPLORATORY. Not part of channel selection; changes nothing already selected.",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "frame": st.FRAME, "header files": files,
        "public and private nonprofit": {"institutions": len(pn), "closures": sum(r["closed"] for r in pn),
                                         "stage 1 repeated": run(pn)},
        "private nonprofit only": {"institutions": len(np_only), "closures": sum(r["closed"] for r in np_only),
                                   "stage 1 repeated": run(np_only)},
    }
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    for g in ("public and private nonprofit", "private nonprofit only"):
        print(g, {d: {k: v.get(k) for k in ("N", "closures", "gain", "gain 95% bootstrap", "verdict")}
                  for d, v in result[g]["stage 1 repeated"].items()})


if __name__ == "__main__":
    main()
