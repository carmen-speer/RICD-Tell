"""
Item 14: do the staffing shares add closure information beyond size,
sector and staff exit? ("channel selection protocol.md", Amendment 15;
exploratory: both frames have been used before.)

Readings, from committed files only:
  D_om_sound       exit reading at the frame's scoring year
                   (data/v4 channels/"soundness values at scoring years.csv")
  secure share     (tenured + tenure track) / all instructional staff, fall t
                   (data/meta channel/"tenure share.json")
  part-time share  part-time / all instructional staff, fall t
                   (data/meta channel/"adjunct absorption.json")
with t = 2014 for the 2014 frame and 2019 for the 2019 frame. Outcomes are
read from the header files as in the selection stages (HD2014-HD2019 for
the 2014 frame; HD2019 onward for the 2019 frame).

Comparisons (Amendment 2 settings): size, sector and exit against size,
sector, exit and the share, on colleges with all of them; and each share
against size and sector alone. A share is carried into the HD2026 retest
only if its gain over size, sector and exit is positive on 2014 and its
interval is above zero on 2019.

Output: data/v4 channels/staffing shares beyond exit.json

Usage (GitHub Actions only, via staffing_shares_beyond_exit.yml):
    cd src
    python "staffing shares beyond exit.py"
"""

from __future__ import annotations

import csv
import datetime
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


st = _load("stages", "v4 selection stages 1 and 2.py")
s3 = _load("stage3", "v4 selection stage 3.py")
META = HERE.parent / "data" / "meta channel"
OUT = st.DIR / "staffing shares beyond exit.json"


def f(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def shares(fall: int) -> dict:
    ten = json.loads((META / "tenure share.json").read_text())["by fall year"][str(fall)]
    adj = json.loads((META / "adjunct absorption.json").read_text())["by fall year"][str(fall)]
    out = {}
    for u, rec in ten.items():
        tot = sum(rec.get("total", [0, 0]))
        if tot > 0:
            out.setdefault(u, {})["secure share"] = min(1.0, (sum(rec.get("tenured", [0, 0])) + sum(rec.get("track", [0, 0]))) / tot)
    for u, m in adj.items():
        if m.get("pool share") is not None:
            out.setdefault(u, {})["part-time share"] = m["pool share"]
    return out


def rows_for(frame: int) -> list[dict]:
    fte = {}
    with open(st.DIR / "inputs.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["fiscal year"]) == frame and f(r["FTE"]):
                fte[r["unitid"]] = f(r["FTE"])
    sh = shares(frame)
    rows = []
    with open(st.DIR / "soundness values at scoring years.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["frame"]) != frame or not fte.get(r["unitid"]):
                continue
            s = sh.get(r["unitid"], {})
            rows.append({"unitid": r["unitid"], "control": r["control"], "log FTE": math.log(fte[r["unitid"]]),
                         "D_om_sound": f(r["D_om_sound"]), "secure share": s.get("secure share"),
                         "part-time share": s.get("part-time share")})
    return rows


def judge(rows: list[dict]) -> dict:
    res = {}
    for share in ("secure share", "part-time share"):
        cov = [r for r in rows if r["D_om_sound"] is not None and r[share] is not None]
        alone = [r for r in rows if r[share] is not None]
        res[share] = {
            "beyond size, sector and exit": st.compare(cov, ["D_om_sound"], ["D_om_sound", share],
                                                       "size, sector and exit", f"size, sector, exit and {share}"),
            "against size and sector alone": st.compare(alone, [], [share], "size and sector", f"size, sector and {share}"),
            "coverage": st.describe(cov, [r for r in rows if r not in cov])}
    return res


def main() -> None:
    out = {}
    r14 = rows_for(2014)
    st.FRAME = 2014
    o14, f14 = st.outcomes([r["unitid"] for r in r14])
    for r in r14:
        r["closed"] = bool(o14[r["unitid"]]["closed or failed (primary)"])
    out["2014 frame (development look)"] = {"header files": f14, **judge(r14)}
    r19 = rows_for(2019)
    o19, f19, nf = s3.outcomes_2019([r["unitid"] for r in r19])
    for r in r19:
        r["closed"] = bool(o19[r["unitid"]]["closed or failed (primary)"])
    out["2019 frame (check)"] = {"header files": f19, "header files not yet released": nf, **judge(r19)}
    carried = {}
    for share in ("secure share", "part-time share"):
        g14 = out["2014 frame (development look)"][share]["beyond size, sector and exit"].get("gain", 0)
        ci19 = out["2019 frame (check)"][share]["beyond size, sector and exit"].get("gain 95% bootstrap", [0, 0])
        carried[share] = g14 > 0 and ci19[0] > 0
    out["carried into the HD2026 retest (Amendment 15 rule)"] = carried
    out["tenure-share retest"] = "kept, as the secure share is carried" if carried["secure share"] else "dropped"
    OUT.write_text(json.dumps({
        "test": "Item 14 (exploratory): staffing shares beyond size, sector and staff exit",
        "protocol": "channel selection protocol.md, Amendment 15",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(), **out,
        "note": "Selection-stage performance, used only to choose; never an estimate of a tracker's accuracy."},
        indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if "frame" not in k}, indent=1))


if __name__ == "__main__":
    main()
