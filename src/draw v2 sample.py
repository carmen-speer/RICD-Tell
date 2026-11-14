"""
Draws the training sample and the test sample for "sampling protocol v2.md"
(phases 1 and 5). Read that file first; this script implements it and
changes none of its rules.

    python "draw v2 sample.py" training          phase 1: 600 institutions from the 2014 frame
    python "draw v2 sample.py" training-second   phase 1, event floor: one second pass, used
                                                 only if the protocol's event floor requires it
    python "draw v2 sample.py" test              phase 5: 300 institutions from the 2019 frame

What it does, for each draw:

1. Downloads the IPEDS institutional header file (HD) for the frame year
   from NCES and records its SHA-256.
2. Builds the frame exactly as the first test did: SECTOR 1, 2 or 3 and
   DEGGRANT 1, sorted by UNITID ascending. For the test draw, every
   institution in the first test's draw log and every institution in
   either training pass is then removed from the frame, along with every
   institution the first test evaluated as a backup during scoring.
3. Computes k = floor(N / target) and selects every kth institution,
   starting from frame position 1 (position floor(k/2) + 1 for the
   second training pass).
4. Applies the collision rule: a panel or pilot institution, or one
   already selected, is skipped and replaced by the next institution in
   UNITID order, wrapping at the end of the frame. No other skip
   applies at the draw, and there are no backups: under this protocol
   an institution that cannot be scored stays in the record as
   unscorable rather than being replaced.
5. Writes the draw (data/v2/<name> draw.json) and its log
   (data/v2/<name> draw log.csv).

It refuses to run if that draw has already been committed, and the
second training pass refuses to run unless the first one exists. The
test draw refuses to run unless classifier v2 has been frozen
(data/v2/classifier v2.json), since the protocol draws the test only
after the freeze. No finance data, score or outcome is read here.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "v2"
V1_DRAW_LOG = ROOT / "data" / "confirmatory" / "draw log.csv"
V1_OUTCOMES = ROOT / "data" / "confirmatory" / "outcomes.csv"
CLASSIFIER_V2 = OUT_DIR / "classifier v2.json"

# The panel and pilot lists are the first test's, read from its own draw
# script so the two tests cannot disagree about who counts as either.
_spec = importlib.util.spec_from_file_location("v1draw", Path(__file__).resolve().parent / "draw confirmatory sample.py")
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)

DRAWS = {
    "training": {"year": 2014, "target": 600, "second_pass": False},
    "training-second": {"year": 2014, "target": 600, "second_pass": True},
    "test": {"year": 2019, "target": 300, "second_pass": False},
}


def paths(name: str) -> tuple[Path, Path]:
    return OUT_DIR / f"{name} draw.json", OUT_DIR / f"{name} draw log.csv"


def download_hd(year: int) -> tuple[bytes, str]:
    table = f"HD{year}"
    last_error = None
    for url in (f"https://nces.ed.gov/ipeds/datacenter/data/{table}.zip",
                f"https://nces.ed.gov/ipeds/complete-data-files/{table}.zip"):
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 404:
                last_error = f"404 at {url}"
                continue
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                names = sorted((n for n in zf.namelist() if n.lower().endswith(".csv")),
                               key=lambda n: ("_rv" in n.lower(), len(n)))
                if names:
                    print(f"Using {names[0]} from {url}")
                    return zf.read(names[0]), url
                last_error = f"no .csv inside ZIP at {url}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e} (at {url})"
    raise SystemExit(f"Could not download {table} from NCES. Last error: {last_error}")


def build_frame(csv_bytes: bytes) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("latin-1")))
    reader.fieldnames = [f.strip().lstrip("﻿").lstrip("ï»¿").upper() for f in reader.fieldnames]
    for col in ("UNITID", "INSTNM", "SECTOR", "DEGGRANT"):
        if col not in reader.fieldnames:
            raise SystemExit(f"The header file is missing the {col} column.")
    frame = []
    for row in reader:
        sector = row["SECTOR"].strip()
        if sector in v1.SECTOR_TO_PIPELINE and row["DEGGRANT"].strip() == "1":
            frame.append({"unitid": row["UNITID"].strip(), "name": row["INSTNM"].strip(),
                          "sector_code": sector, "sector": v1.SECTOR_TO_PIPELINE[sector],
                          "state": row.get("STABBR", "").strip()})
    frame.sort(key=lambda r: int(r["unitid"]))
    return frame


def excluded_for_test() -> set[str]:
    ids = set()
    # Every institution the first test drew, skipped at the draw, or
    # evaluated as a backup during scoring (third amendment): the draw log
    # alone omits backups evaluated later, whose outcomes are now known.
    for path in (V1_DRAW_LOG, V1_OUTCOMES):
        with open(path, newline="") as f:
            ids |= {r["unitid"] for r in csv.DictReader(f)}
    for name in ("training", "training-second"):
        p, _ = paths(name)
        if p.exists():
            ids |= {s["unitid"] for s in json.loads(p.read_text())["institutions"]}
    return ids


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in DRAWS:
        raise SystemExit('Usage: python "draw v2 sample.py" training | training-second | test')
    name = sys.argv[1]
    spec = DRAWS[name]
    out_json, out_log = paths(name)
    if out_json.exists() or out_log.exists():
        raise SystemExit(f"The {name} draw has already been committed. Refusing to draw again.")
    if name == "training-second" and not paths("training")[0].exists():
        raise SystemExit("The second training pass needs the first training draw to exist.")
    if name == "test" and not CLASSIFIER_V2.exists():
        raise SystemExit("The test is drawn only after classifier v2 is frozen (data/v2/classifier v2.json).")

    csv_bytes, url = download_hd(spec["year"])
    frame = build_frame(csv_bytes)
    full_n = len(frame)
    removed = 0
    if name == "test":
        drop = excluded_for_test()
        removed = sum(1 for r in frame if r["unitid"] in drop)
        frame = [r for r in frame if r["unitid"] not in drop]
    blocked = {str(i["unitid"]) for i in json.loads(v1.PANEL_PATH.read_text())}
    pilot = v1.PILOT_UNITIDS | v1.PILOT_REMOVED_UNITIDS
    first_pass = set()
    if name == "training-second":
        first_pass = {s["unitid"] for s in json.loads(paths("training")[0].read_text())["institutions"]}

    n = len(frame)
    k = n // spec["target"]
    if k < 1:
        raise SystemExit(f"Frame has only {n} institutions.")
    offset = (k // 2) if spec["second_pass"] else 0
    starts = [offset + i * k for i in range(spec["target"]) if offset + i * k < n]

    chosen, picks, log_rows = set(), [], []
    for slot, start in enumerate(starts, start=1):
        pos, steps = start, 0
        while steps < n:
            inst = frame[pos]
            uid = inst["unitid"]
            reason = ("panel" if uid in blocked else "pilot" if uid in pilot
                      else "already selected" if uid in chosen or uid in first_pass else None)
            log_rows.append({"slot": slot, "frame position": pos + 1, "unitid": uid, "name": inst["name"],
                             "sector": inst["sector"], "state": inst["state"],
                             "status": "skipped" if reason else "selected",
                             "reason": reason or ("primary selection" if pos == start else "replacement")})
            if reason is None:
                chosen.add(uid)
                picks.append({"slot": slot, "frame position": pos + 1, **inst})
                break
            pos, steps = (pos + 1) % n, steps + 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_log, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        w.writeheader()
        w.writerows(log_rows)
    out = {
        "protocol": "sampling protocol v2.md",
        "draw": name,
        "drawn at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source file": f"HD{spec['year']}", "source url": url,
        "source sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "frame size before exclusions": full_n,
        "removed as touched by the first test or the training draw": removed,
        "frame size N": n, "step size k": k, "first position": offset + 1,
        "institutions drawn": len(picks),
        "by sector": {s: sum(1 for p in picks if p["sector"] == s) for s in ("public", "private", "forprofit")},
        "collisions skipped": sum(1 for r in log_rows if r["status"] == "skipped"),
        "institutions": picks,
    }
    out_json.write_text(json.dumps(out, indent=2))
    print(f"{name}: frame {n} (of {full_n}), k = {k}, {len(picks)} drawn, "
          f"{out['collisions skipped']} collisions skipped. Wrote {out_json.name} and {out_log.name}.")


if __name__ == "__main__":
    main()
