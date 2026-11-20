"""
Item 13, post hoc check (decided November 20 after the protocol's results
were seen, and labelled so): the three predictions of "lifetime earnings
protocol.md" with "professions" restricted to the historic IPEDS
first-professional fields, because Scorecard credential level 7 turned out
to hold 155 field units, most of them outside the professions (education,
computing, engineering and others).

Classic first-professional fields (IPEDS's historic list), as 4-digit CIP
at credential level 7: veterinary medicine 0180, law 2201, theology and
ministerial studies 3906, chiropractic 5101, dentistry 5104, medicine 5112,
optometry 5117, pharmacy 5120; osteopathic medicine (5119) and podiatry
(5121) are included if present (they are not separate in the Scorecard
file). Trades are unchanged. Same measures, bootstrap and verdict rules as
the protocol; few units, so wide intervals.

Reads only data/item 13/lifetime earnings.json (committed by the
protocol's run). Output: data/item 13/lifetime earnings classic professions.json

Usage:
    cd src
    python "lifetime earnings classic professions.py"
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "item 13"
CLASSIC = {"0180", "2201", "3906", "5101", "5104", "5112", "5117", "5120", "5119", "5121"}
SEED, BOOT = 20261127, 2000


def main() -> None:
    units = json.loads((DATA / "lifetime earnings.json").read_text())["units"]
    prof = [u for u in units if u["credential level"] == "7" and u["cip"] in CLASSIC]
    trades = [u for u in units if u["sector"] == "trades"]
    rng = np.random.default_rng(SEED)

    def compare(measure, sign):
        p = [u[measure] for u in prof if u.get(measure) is not None]
        t = [u[measure] for u in trades if u.get(measure) is not None]
        if len(p) < 3 or len(t) < 3:
            return {"professions units": len(p), "trades units": len(t), "verdict": "too few units; not computed"}
        diff = float(np.median(p) - np.median(t))
        b = [np.median(rng.choice(p, len(p))) - np.median(rng.choice(t, len(t))) for _ in range(BOOT)]
        ci = [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]
        ok = (ci[1] < 0) if sign < 0 else (ci[0] > 0)
        pt = (diff < 0) if sign < 0 else (diff > 0)
        return {"professions units": len(p), "trades units": len(t), "median, professions": float(np.median(p)),
                "median, trades": float(np.median(t)), "difference (professions - trades)": diff, "95% interval": ci,
                "verdict": "supported" if ok else "in the predicted direction" if pt else "not supported"}

    tests = {}
    for s in ("", " (top-coded occupations left out)"):
        tests["P1 early position lower for professions" + s] = compare("early position" + s, -1)
        tests["P2 occupational ladder higher for professions" + s] = compare("occupational ladder" + s, +1)
    tests["P3 graduates' growth higher for professions"] = compare("graduates' growth", +1)
    keep = ("EARN_MDN_1YR_NAT", "EARN_MDN_5YR_NAT", "EARN_MDN_7YR_NAT", "occupations' median wage", "early position",
            "occupational ladder", "graduates' growth", "median debt (weighted median of program medians)",
            "payoff to cost", "share of linked employment top-coded")
    out = {"check": "Item 13 post hoc: professions restricted to the historic first-professional fields",
           "label": "post hoc: decided after the protocol's results were seen",
           "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "fields used": {u["cip"]: u["field"] for u in prof},
           "predictions": tests,
           "payoff to cost, medians": {
               "professions": float(np.median([u["payoff to cost"] for u in prof if u.get("payoff to cost") is not None])),
               "trades": float(np.median([u["payoff to cost"] for u in trades if u.get("payoff to cost") is not None]))},
           "units": [{k: u.get(k) for k in ("cip", "field") + keep} for u in prof]}
    (DATA / "lifetime earnings classic professions.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(tests, indent=1))


if __name__ == "__main__":
    main()
