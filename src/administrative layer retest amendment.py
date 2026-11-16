"""
Amendment 1 to "administrative layer retest protocol.md" (disclosed, fixed
after the run): the joint reading with each sector split at its own median
debt trend instead of at zero, on the same held-out colleges.

Output: data/meta channel/administrative layer retest amendment.json

Usage:
    cd src
    python "administrative layer retest amendment.py"   [--root DIR for testing]
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location("retest",
                                               Path(__file__).resolve().parent / "administrative layer retest.py")
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)


def joint_median(rs, measure):
    rs = [r for r in rs if r[measure] is not None and r["debt trend"] is not None]
    m_share = float(np.median([r[measure] for r in rs]))
    m_trend = float(np.median([r["debt trend"] for r in rs]))
    grp = lambda r: ("thick" if r[measure] > m_share else "thin",
                     "upper half" if r["debt trend"] > m_trend else "lower half")
    rate = lambda g: sum(r["closed"] for r in g) / len(g) if g else None
    out = {"median share": round(m_share, 4), "median debt trend": round(m_trend, 6), "groups": {}}
    for layer in ("thin", "thick"):
        for half in ("lower half", "upper half"):
            g = [r for r in rs if grp(r) == (layer, half)]
            out["groups"][f"{layer}, debt trend {half}"] = {
                "colleges": len(g), "closed": int(sum(r["closed"] for r in g)),
                "closure rate": None if rate(g) is None else round(rate(g), 4)}

        def diff(s, layer=layer):
            a = [r for r in s if grp(r) == (layer, "upper half")]
            b = [r for r in s if grp(r) == (layer, "lower half")]
            return None if not a or not b else rate(a) - rate(b)
        d = diff(rs)
        ci = rt.interval(rs, diff)
        out[f"{layer} layer: closure rate, upper minus lower half of debt trend"] = {
            "difference": None if d is None else round(d, 4), "95% interval": ci,
            "verdict (predicted above zero)": rt.verdict(ci)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    root = Path(ap.parse_args().root)
    rows = rt.load(root)
    out = {"protocol": "administrative layer retest protocol.md, Amendment 1 (disclosed; fixed after the run)",
           "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "bootstrap": {"resamples": rt.BOOT, "seed": rt.SEED}}
    for measure, label in (("core", "core administrative share (primary)"), ("broad", "broad administrative share")):
        out[label] = {}
        for code, name in (("private", "private nonprofit"), ("forprofit", "for-profit")):
            g = [r for r in rows if r["sector"] == code]
            out[label][name] = joint_median(g, measure)
    path = root / "data" / "meta channel" / "administrative layer retest amendment.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
