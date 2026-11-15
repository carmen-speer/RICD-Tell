"""
Phase 3 of "sampling protocol v2.md": the training institutions' outcomes.

Every institution in the committed training draw (and in the second pass,
if the event floor required one) is coded from the IPEDS header files for
2014 through 2019, with the scoring year 2014, under the protocol's
outcome definition:

  primary coding   closed or failed if any of
                     (a) a closure date (CLOSEDAT) after the end of the
                         scoring year (30 June 2014), in HD2014 or later;
                     (b) a year of deletion (DEATHYR) after 2014, or ACT = D;
                     (c) a successor institution (NEWID) other than itself;
                     (d) presence in HD2014 and absence from HD2019, with
                         no record of (a) to (c);
                   holds, and the institution does not appear again as
                   active (ACT = A or R) in a header file later than the
                   one recording the event. An event followed by such a
                   reappearance is a change in reporting, not a failure.
  coding B         as primary, but an institution with a standing event
                   under (c) counts as surviving.
  coding C         as primary, but an institution whose only ground is (d)
                   counts as surviving.

How dates are read: CLOSEDAT holds a date such as 6/30/2016 or 2016-06-30,
or a negative code meaning none. A full date counts under (a) if it falls
after 30 June 2014; a bare year counts only if it is 2015 or later, since
a bare 2014 cannot be placed on either side of that date.

The lookup is allowed only once every training institution has a result
committed in data/v2/training scores/, so that no score can follow an
outcome. The result also says whether the event floor holds: if fewer
than 40 scored training institutions closed or failed under the primary
coding, the protocol's one second pass ("training-second") is drawn and
scored before the classifier is fitted.

Output: data/v2/training outcomes.json.

Usage (GitHub Actions only, via v2_training_outcomes.yml):
    cd src
    python v2_training_outcomes.py
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import re
import subprocess
import time
import zipfile
from pathlib import Path

import requests

import v2_common as v2

OUT_PATH = v2.V2_DIR / "training outcomes.json"
SCORES_DIR = v2.V2_DIR / "training scores"
SCORING_YEAR = 2014
FILES = list(range(2014, 2020))           # HD2014 .. HD2019
FLOOR = 40
KEEP = ("UNITID", "INSTNM", "ACT", "CLOSEDAT", "DEATHYR", "NEWID", "CYACTIVE")


def committed(path: Path) -> str:
    rel = str(path.relative_to(v2.ROOT))
    h = subprocess.run(["git", "log", "-1", "--format=%H %cI", "--", rel], cwd=v2.ROOT,
                       capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=v2.ROOT,
                           capture_output=True, text=True).stdout.strip()
    if not h or dirty:
        raise SystemExit(f"{rel} is not committed; nothing is looked up.")
    return h


def institutions() -> list[dict]:
    out = []
    for name in ("training", "training-second"):
        p = v2.V2_DIR / f"{name} draw.json"
        if p.exists():
            committed(p)
            out += [{**i, "draw": name} for i in json.loads(p.read_text())["institutions"]]
    return out


def scores() -> dict:
    committed(SCORES_DIR)
    res = {}
    for p in sorted(SCORES_DIR.glob("batch_*.json")):
        for r in json.loads(p.read_text())["results"]:
            res[r["unitid"]] = r
    return res


def download_hd(year: int) -> dict:
    table = f"HD{year}"
    last = ""
    for attempt in range(1, 6):
        for url in (f"https://nces.ed.gov/ipeds/datacenter/data/{table}.zip",
                    f"https://nces.ed.gov/ipeds/complete-data-files/{table}.zip"):
            try:
                r = requests.get(url, timeout=180)
                if r.status_code == 200 and r.content[:2] == b"PK":
                    z = zipfile.ZipFile(io.BytesIO(r.content))
                    names = sorted((n for n in z.namelist() if n.lower().endswith(".csv")),
                                   key=lambda n: ("_rv" in n.lower(), len(n)))
                    if names:
                        return {"table": table, "url": url, "file": names[0],
                                "zip sha256": hashlib.sha256(r.content).hexdigest(),
                                "csv": z.read(names[0]).decode("latin-1")}
                last = f"HTTP {r.status_code} at {url}"
            except requests.RequestException as e:
                last = f"{e} at {url}"
        time.sleep(20 * attempt)
    raise SystemExit(f"Could not download {table} ({last}). Nothing recorded; run again later.")


def rows_by_id(text: str) -> dict:
    reader = csv.DictReader(io.StringIO(text))
    # A heading may carry a byte-order mark (read as latin-1 it appears as "\u00ef\u00bb\u00bf"), as
    # every other IPEDS reader in this repository already allows for; without this, a file whose first
    # heading is UNITID yields no rows at all.
    fields = {f: f.strip().lstrip("\ufeff").lstrip("\u00ef\u00bb\u00bf").strip().upper()
              for f in (reader.fieldnames or [])}
    out = {}
    for r in reader:
        row = {fields[k]: (v or "").strip() for k, v in r.items() if k in fields}
        u = row.get("UNITID", "")
        if u:
            out[u] = {k: row.get(k, "") for k in KEEP if k != "UNITID"}
    return out


def number(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def closure_after_scoring_year(v: str) -> bool | None:
    """True if CLOSEDAT falls after 30 June 2014; False if before; None if it holds no date."""
    v = (v or "").strip()
    n = number(v)
    if not v or (n is not None and n < 0):
        return None
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", v)            # 6/30/2016
    if m:
        d = datetime.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        return d > datetime.date(SCORING_YEAR, 6, 30)
    m = re.match(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})", v)                 # 2016-06-30
    if m:
        d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return d > datetime.date(SCORING_YEAR, 6, 30)
    m = re.match(r"^\s*(\d{1,2})/(\d{4})\s*$", v)                       # 6/2016
    if m:
        return (int(m.group(2)), int(m.group(1))) > (SCORING_YEAR, 6)
    m = re.search(r"(\d{4})", v)                                         # a bare year
    if m:
        return int(m.group(1)) >= SCORING_YEAR + 1
    return None


def code(unitid: str, rows: dict) -> dict:
    """rows: {year: row or None}. Returns the evidence and all three codings."""
    present = {y: r for y, r in rows.items() if r is not None}
    events = []
    for y, r in sorted(present.items()):
        if closure_after_scoring_year(r.get("CLOSEDAT", "")):
            events.append({"ground": "a", "file": f"HD{y}", "CLOSEDAT": r["CLOSEDAT"], "year": y})
        dy = number(r.get("DEATHYR", ""))
        if (dy is not None and dy > SCORING_YEAR) or r.get("ACT", "").upper() == "D":
            events.append({"ground": "b", "file": f"HD{y}", "DEATHYR": r.get("DEATHYR", ""),
                           "ACT": r.get("ACT", ""), "year": y})
        nid = r.get("NEWID", "").strip()
        if number(nid) is not None and number(nid) > 0 and nid != unitid:
            events.append({"ground": "c", "file": f"HD{y}", "NEWID": nid, "year": y})
    for e in events:
        later = [y for y, r in present.items() if y > e["year"] and r.get("ACT", "").upper() in ("A", "R")]
        e["voided by reappearance as active"] = f"HD{min(later)}" if later else None
    standing = [e for e in events if not e["voided by reappearance as active"]]
    grounds = sorted({e["ground"] for e in standing})
    in_first, in_last = SCORING_YEAR in present, FILES[-1] in present
    if not events and in_first and not in_last:
        grounds = ["d"]
    primary = bool(grounds)
    coding_b = primary and "c" not in grounds
    coding_c = primary and grounds != ["d"]
    return {"in HD2014": in_first, "in HD2019": in_last, "events": events, "standing grounds": grounds,
            "closed or failed (primary)": primary, "coding B": coding_b, "coding C": coding_c}


def main() -> None:
    insts = institutions()
    if not insts:
        raise SystemExit("No training draw is committed.")
    sc = scores()
    missing = [i["unitid"] for i in insts if i["unitid"] not in sc]
    if missing:
        raise SystemExit(f"{len(missing)} training institutions have no committed result yet "
                         f"(first: {missing[:5]}); no outcome is looked up until all do.")
    files = {}
    for y in FILES:
        files[y] = download_hd(y)
    tables = {y: rows_by_id(f["csv"]) for y, f in files.items()}

    records = []
    for i in insts:
        u = i["unitid"]
        res = sc[u]
        c = code(u, {y: tables[y].get(u) for y in FILES})
        records.append({"slot": i["slot"], "draw": i["draw"], "unitid": u, "name": i["name"],
                        "sector": i["sector"], "status": res["status"], **c})

    def summary(group: list[dict]) -> dict:
        n = len(group)
        out = {"N": n}
        for k in ("closed or failed (primary)", "coding B", "coding C"):
            e = sum(r[k] for r in group)
            out[k] = {"closed": e, "rate": (e / n) if n else None}
        return out

    scored = [r for r in records if r["status"] == "scored"]
    unscorable = [r for r in records if r["status"] == "unscorable"]
    structural = [r for r in records if r["status"] == "structurally unscorable"]
    e_scored = sum(r["closed or failed (primary)"] for r in scored)
    second_drawn = any(i["draw"] == "training-second" for i in insts)
    out = {
        "protocol": "sampling protocol v2.md, phase 3 (training outcomes)",
        "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "training scores committed (commit, time)": committed(SCORES_DIR),
        "scoring year": SCORING_YEAR,
        "header files": [{k: v for k, v in f.items() if k != "csv"} for f in files.values()],
        "summary": {"scored": summary(scored), "unscorable": summary(unscorable),
                    "structurally unscorable": summary(structural), "all drawn": summary(records)},
        "event floor": {"floor": FLOOR, "closed or failed among scored (primary)": e_scored,
                        "second pass already drawn": second_drawn,
                        "verdict": ("met" if e_scored >= FLOOR else
                                    "not met after the one second pass; the classifier is fitted on what there is"
                                    if second_drawn else
                                    "not met: the protocol's one second pass (draw_v2_sample.yml, training-second) "
                                    "is drawn and scored before the classifier is fitted")},
        "institutions": records,
        "machine": v2.machine(),
    }
    v2.write_json(OUT_PATH, out)
    print(f"Wrote {OUT_PATH}: {len(scored)} scored, {e_scored} closed or failed among them; "
          f"event floor {out['event floor']['verdict']}.")


if __name__ == "__main__":
    main()
