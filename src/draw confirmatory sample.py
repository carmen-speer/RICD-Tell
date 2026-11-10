"""
Draws the 300-institution confirmatory sample, exactly as specified in
"sampling protocol.md" at the root of this repository. Read that file
first -- this script implements it and does not change any of its rules.

What this script does:

1. Downloads the IPEDS Institutional Characteristics header file (HD)
   for 2019 from NCES.
2. Builds the sampling frame: SECTOR 1, 2 or 3 (public, private
   nonprofit and private for-profit four-year institutions) and
   DEGGRANT 1 (degree-granting), sorted by UNITID, ascending.
3. Computes the step size k = floor(N / 300).
4. Selects every kth institution, starting from the first institution
   in the ordered frame (frame positions 0, k, 2k, ... 299k). Each of
   these 300 positions is one "slot."
5. For each slot, applies the collision rule: if the selected
   institution is in the validation panel or the exploratory pilot, it
   is skipped and replaced by the next institution in UNITID order,
   wrapping to the start of the frame at the end. An institution
   already selected for another slot counts as a duplicate and is
   skipped the same way.
6. For each slot, records an ordered list of backup candidates (the
   next eligible institutions in UNITID order). These are used ONLY by
   the later scoring step, if a slot's institution fails the
   insufficient-data rule -- the data check, the convergence check or
   the stability check. Those checks need the institution's finance
   data and a full model fit, so they cannot be applied here; they
   are applied when the sample is scored, and every skip is logged
   then.
7. Writes the draw log and the slot list to data/confirmatory/, where
   the workflow commits them.

This script refuses to run if a draw has already been committed. The
whole point of committing the draw is that it can't be quietly redone.
To redo a draw on purpose, the existing files must be deleted in a
separate, visible commit first.

No institution's finance data, score or outcome is looked at here.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import requests

SAMPLE_SIZE = 300
N_BACKUPS_PER_SLOT = 25
HD_TABLE = "HD2019"
HD_URLS = [
    f"https://nces.ed.gov/ipeds/datacenter/data/{HD_TABLE}.zip",
    f"https://nces.ed.gov/ipeds/complete-data-files/{HD_TABLE}.zip",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
PANEL_PATH = REPO_ROOT / "data" / "panel" / "panel.json"
OUT_DIR = REPO_ROOT / "data" / "confirmatory"
DRAW_LOG_PATH = OUT_DIR / "draw log.csv"
SLOTS_PATH = OUT_DIR / "draw slots.json"

# The exploratory pilot: the 16 institutions live-scored before this
# protocol existed (see score_batch.py for how each was chosen), frozen
# here as a fixed list so later changes to the live dashboard can't
# change who counts as a pilot institution.
PILOT_UNITIDS = {
    "110583",  # California State University-Long Beach
    "124292",  # Thomas Aquinas College
    "132903",  # University of Central Florida
    "134097",  # Florida State University
    "143084",  # Augustana College
    "166124",  # College of the Holy Cross
    "170976",  # University of Michigan-Ann Arbor (smoke test)
    "206525",  # Wittenberg University
    "211291",  # Bucknell University
    "212911",  # Haverford College
    "217882",  # Clemson University
    "225511",  # University of Houston
    "232256",  # Hampden-Sydney College
    "233718",  # Sweet Briar College
    "238032",  # West Virginia University
    "484613",  # University of Phoenix-Arizona
}

# Two institutions that were scored during the pilot and later removed
# from it (see score_batch.py's own docstring). Their results have
# already been seen, so they can't serve as blind confirmatory cases.
# They are treated as pilot institutions for the collision rule.
PILOT_REMOVED_UNITIDS = {
    "196088",  # University at Buffalo, removed 2026-09-20
    "206695",  # Youngstown State University, swapped out 2026-09-15
}

SECTOR_TO_PIPELINE = {"1": "public", "2": "private", "3": "forprofit"}


def download_hd() -> tuple[bytes, str]:
    """Download the HD file and return (csv bytes, url used)."""
    last_error = None
    for url in HD_URLS:
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 404:
                last_error = f"404 at {url}"
                continue
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                # Prefer the plain data file over any revised-value file.
                names.sort(key=lambda n: ("_rv" in n.lower(), len(n)))
                if not names:
                    last_error = f"no .csv inside ZIP at {url}: {zf.namelist()}"
                    continue
                print(f"Using {names[0]} from {url}")
                return zf.read(names[0]), url
        except Exception as e:  # try the next known address
            last_error = f"{type(e).__name__}: {e} (at {url})"
    raise SystemExit(f"Could not download {HD_TABLE} from NCES. Last error: {last_error}")


def build_frame(csv_bytes: bytes) -> list[dict]:
    """Filter to SECTOR 1-3 and DEGGRANT 1, sorted by UNITID ascending."""
    text = csv_bytes.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [f.strip().lstrip("\ufeff").lstrip("ï»¿").upper() for f in reader.fieldnames]
    for col in ("UNITID", "INSTNM", "SECTOR", "DEGGRANT"):
        if col not in reader.fieldnames:
            raise SystemExit(f"{HD_TABLE} is missing the {col} column. Columns found: {reader.fieldnames[:20]}")
    frame = []
    for row in reader:
        sector = row["SECTOR"].strip()
        if sector in SECTOR_TO_PIPELINE and row["DEGGRANT"].strip() == "1":
            frame.append({
                "unitid": row["UNITID"].strip(),
                "name": row["INSTNM"].strip(),
                "sector_code": sector,
                "sector": SECTOR_TO_PIPELINE[sector],
                "state": row.get("STABBR", "").strip(),
            })
    frame.sort(key=lambda r: int(r["unitid"]))
    return frame


def load_panel_unitids() -> set[str]:
    panel = json.loads(PANEL_PATH.read_text())
    return {str(inst["unitid"]) for inst in panel}


def draw(frame: list[dict], panel_ids: set[str]) -> tuple[list[dict], list[dict], int]:
    """
    Apply the sampling method and collision rule. Returns (slots, log rows, k).
    """
    n = len(frame)
    k = n // SAMPLE_SIZE
    if k < 1:
        raise SystemExit(f"Frame has only {n} institutions -- fewer than {SAMPLE_SIZE}.")
    primary_positions = [i * k for i in range(SAMPLE_SIZE)]
    primary_ids = {frame[p]["unitid"] for p in primary_positions}

    def collision_reason(inst: dict, chosen: set[str], own_position: int, pos: int) -> str | None:
        uid = inst["unitid"]
        if uid in panel_ids:
            return "panel"
        if uid in PILOT_UNITIDS or uid in PILOT_REMOVED_UNITIDS:
            return "pilot"
        if uid in chosen:
            return "duplicate"
        # A replacement may not take another slot's own primary selection.
        if pos != own_position and uid in primary_ids:
            return "duplicate"
        return None

    chosen: set[str] = set()
    slots, log_rows = [], []
    for slot_no, start in enumerate(primary_positions, start=1):
        selected = None
        backups = []
        steps = 0
        pos = start
        while (selected is None or len(backups) < N_BACKUPS_PER_SLOT) and steps < n:
            inst = frame[pos]
            reason = collision_reason(inst, chosen, start, pos)
            if selected is None:
                log_rows.append({
                    "slot": slot_no, "frame position": pos + 1,
                    "unitid": inst["unitid"], "name": inst["name"],
                    "sector": inst["sector"], "state": inst["state"],
                    "status": "skipped" if reason else "selected",
                    "reason": reason or ("primary selection" if pos == start else "replacement"),
                })
                if reason is None:
                    selected = inst
                    chosen.add(inst["unitid"])
            elif reason is None:
                backups.append({"frame position": pos + 1, **inst})
            pos = (pos + 1) % n
            steps += 1
        if selected is None:
            raise SystemExit(f"Slot {slot_no}: no eligible institution found in the whole frame.")
        slots.append({
            "slot": slot_no,
            "primary frame position": start + 1,
            "selected": {"frame position": next(r["frame position"] for r in reversed(log_rows)
                                                if r["slot"] == slot_no and r["status"] == "selected"),
                         **selected},
            "backups in order": backups,
        })
    return slots, log_rows, k


def main() -> None:
    if DRAW_LOG_PATH.exists() or SLOTS_PATH.exists():
        raise SystemExit(
            "A draw has already been committed (data/confirmatory/ already has its files). "
            "Refusing to draw again. To redo the draw on purpose, delete those files in a "
            "separate, visible commit first."
        )

    csv_bytes, url = download_hd()
    frame = build_frame(csv_bytes)
    panel_ids = load_panel_unitids()
    print(f"Frame: {len(frame)} institutions (SECTOR 1-3, DEGGRANT 1, {HD_TABLE}).")
    print(f"Panel: {len(panel_ids)} institutions. Pilot: {len(PILOT_UNITIDS)} "
          f"(+{len(PILOT_REMOVED_UNITIDS)} removed pilot institutions).")

    slots, log_rows, k = draw(frame, panel_ids)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(DRAW_LOG_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        writer.writeheader()
        writer.writerows(log_rows)

    skipped = [r for r in log_rows if r["status"] == "skipped"]
    summary = {
        "protocol": "sampling protocol.md",
        "drawn at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source file": HD_TABLE,
        "source url": url,
        "source sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "frame size N": len(frame),
        "step size k": k,
        "slots": len(slots),
        "skipped at draw": {
            "panel": sum(r["reason"] == "panel" for r in skipped),
            "pilot": sum(r["reason"] == "pilot" for r in skipped),
            "duplicate": sum(r["reason"] == "duplicate" for r in skipped),
        },
        "note": ("Insufficient-data skips (data check, convergence check, stability check) "
                 "happen at scoring time, using each slot's backups in order, and are "
                 "logged then."),
        "sector counts of selected": {
            s: sum(sl["selected"]["sector"] == s for sl in slots)
            for s in ("public", "private", "forprofit")
        },
        "slot list": slots,
    }
    SLOTS_PATH.write_text(json.dumps(summary, indent=2))

    print(f"N = {len(frame)}, k = {k}, slots = {len(slots)}")
    print(f"Skipped at draw: {summary['skipped at draw']}")
    print(f"Selected by sector: {summary['sector counts of selected']}")
    print(f"Wrote {DRAW_LOG_PATH} and {SLOTS_PATH}")


if __name__ == "__main__":
    sys.exit(main())
