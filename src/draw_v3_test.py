"""
Phase 2 of "sampling protocol v3.md": the v3 test institutions.

The v3 test is not a sample. It is every institution that remains in the
fiscal year 2019 frame once every institution already used is removed:

1. Downloads the IPEDS institutional header file for 2019 (HD2019) from
   NCES and records its SHA-256.
2. Builds the frame exactly as the first test and the v2 test did: SECTOR
   1, 2 or 3 and DEGGRANT 1, sorted by UNITID ascending (the v2 draw
   script's own function, unchanged).
3. Removes every institution in the first test's draw log or evaluated by
   it as a backup, every institution in either v2 training pass, every
   institution in the v2 test draw, and the panel and pilot institutions.
4. Lists every remaining institution, in UNITID order, as the v3 test, and
   writes data/v3/test draw.json and data/v3/test draw log.csv.

It refuses to run if the v3 test has already been listed, or before
classifier v3 is frozen (data/v3/classifier v3.json). No finance data,
score or outcome is read.

Usage (GitHub Actions only, via draw_v3_test.yml):
    cd src
    python draw_v3_test.py
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
V2_DIR = ROOT / "data" / "v2"
V3_DIR = ROOT / "data" / "v3"
CLASSIFIER_V3 = V3_DIR / "classifier v3.json"
V2_TEST_DRAW = V2_DIR / "test draw.json"
OUT_JSON = V3_DIR / "test draw.json"
OUT_LOG = V3_DIR / "test draw log.csv"

_spec = importlib.util.spec_from_file_location("v2draw", SRC / "draw v2 sample.py")
v2draw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2draw)


def main() -> None:
    if OUT_JSON.exists() or OUT_LOG.exists():
        raise SystemExit("The v3 test has already been listed. Refusing to list it again.")
    if not CLASSIFIER_V3.exists():
        raise SystemExit("The v3 test is listed only after classifier v3 is frozen (data/v3/classifier v3.json).")
    if not V2_TEST_DRAW.exists():
        raise SystemExit("The v2 test draw is missing; its institutions must be excluded.")

    csv_bytes, url = v2draw.download_hd(2019)
    frame = v2draw.build_frame(csv_bytes)
    used_v1_v2_training = v2draw.excluded_for_test()
    used_v2_test = {s["unitid"] for s in json.loads(V2_TEST_DRAW.read_text())["institutions"]}
    panel = {str(i["unitid"]) for i in json.loads(v2draw.v1.PANEL_PATH.read_text())}
    pilot = v2draw.v1.PILOT_UNITIDS | v2draw.v1.PILOT_REMOVED_UNITIDS

    log_rows, picks = [], []
    for pos, inst in enumerate(frame, start=1):
        u = inst["unitid"]
        reason = ("first test or v2 training" if u in used_v1_v2_training
                  else "v2 test" if u in used_v2_test
                  else "panel" if u in panel
                  else "pilot" if u in pilot else None)
        log_rows.append({"frame position": pos, "unitid": u, "name": inst["name"], "sector": inst["sector"],
                         "state": inst["state"], "status": "excluded" if reason else "listed",
                         "reason": reason or ""})
        if reason is None:
            picks.append({"slot": len(picks) + 1, "frame position": pos, **inst})

    V3_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        w.writeheader()
        w.writerows(log_rows)
    out = {
        "protocol": "sampling protocol v3.md, phase 2 (every remaining institution; no outcome looked up)",
        "drawn at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source file": "HD2019", "source url": url, "source sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "frame size": len(frame),
        "excluded": {r: sum(1 for x in log_rows if x["reason"] == r)
                     for r in ("first test or v2 training", "v2 test", "panel", "pilot")},
        "institutions listed": len(picks),
        "by sector": {s: sum(1 for p in picks if p["sector"] == s) for s in ("public", "private", "forprofit")},
        "institutions": picks,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"Frame {len(frame)}; excluded {out['excluded']}; listed {len(picks)} {out['by sector']}.")


if __name__ == "__main__":
    main()
