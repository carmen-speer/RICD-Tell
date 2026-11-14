"""
Settings and helpers shared by every script under "sampling protocol v2.md".

Nothing here changes how a single institution is scored. It fixes, in one
place, the two scoring windows, the sampler settings, the download of the
NCES finance files a window needs, and which finance form holds an
institution's row in its scoring year, so that the training and test
scripts cannot drift apart.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2_DIR = ROOT / "data" / "v2"
SECTORS = ("private", "public", "forprofit")

# Pipeline years: start_year S and end_year E cover fiscal years S+1..E.
WINDOWS = {
    "training": {"start_year": 2003, "end_year": 2014},  # FY2004-FY2014
    "test": {"start_year": 2008, "end_year": 2019},      # FY2009-FY2019
}

# The first test's production settings (sampling protocol v2.md, phase 2).
SAMPLER = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9,
               cores=1, compile_mode="NUMBA")
TEST_SEEDS = (7, 101, 202)
TRAINING_SEED = 7


def prefetch_finance(out: str | Path, start_year: int, end_year: int,
                     required: bool = True) -> tuple[dict, list[str]]:
    """Download every finance file a window needs, once, with patient retries.

    Returns (manifest of SHA-256 by file, list of files NCES did not serve).
    With required=True a missing file stops the run; with required=False it
    is reported instead, which is what the early-finance check needs.
    """
    import fetch_live_data as fld
    base = Path(out)
    manifest, missing = {}, []
    for sector in SECTORS:
        for year in range(start_year, end_year):
            got = None
            for attempt in range(1, 7):
                got = fld.download_ipeds_finance_bulk(year, dest_dir=base / sector, sector=sector)
                if got is not None:
                    break
                time.sleep(30 * attempt)
            if got is None:
                missing.append(f"{sector} {year}")
                continue
            for f in sorted(Path(got).glob("*.csv")):
                manifest[f"{sector}/{year}/{f.name}"] = hashlib.sha256(f.read_bytes()).hexdigest()
                normalize_finance_csv(f, sector)   # after the raw file's hash is recorded
            time.sleep(2)
    if missing and required:
        raise SystemExit("Could not download these NCES finance files: " + ", ".join(missing)
                         + ". Nothing recorded; run the workflow again later.")
    return manifest, missing


def use_finance_cache(finance_dir: str | Path) -> None:
    """Point the pipeline's download function at the prefetched copies."""
    import fetch_live_data as fld
    original = fld.download_ipeds_finance_bulk
    base = Path(finance_dir)

    def cached(year, dest_dir, sector="private"):
        src = base / sector / str(year)
        files = sorted(src.glob("*.csv")) if src.exists() else []
        if not files:
            return original(year, dest_dir=dest_dir, sector=sector)
        year_dir = Path(dest_dir) / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copyfile(f, year_dir / f.name)
            normalize_finance_csv(year_dir / f.name, sector)   # a no-op on an already normalized copy
        return year_dir

    fld.download_ipeds_finance_bulk = cached


# ---------------------------------------------------------------------------
# Finance-file rules of the fourth amendment ("sampling protocol v2.md").
# They apply only inside v2: the live pipeline's own files and field codes
# are unchanged until the results are published.
#
# 1. Column headings are trimmed of surrounding whitespace and upper-cased
#    before any column is looked up. Some NCES files carry whitespace in
#    their headings (the endowment heading in most public years and in the
#    private years 2011-2014), which made an exact lookup fail silently.
# 2. For-profit (F3) files gain two columns the pipeline reads in place of
#    its for-profit institutional-support and instruction codes:
#      V2_MAINT  academic support + student services + institutional
#                support: the combined line F3E03 on the form used before
#                fiscal year 2014, and F3E03A1 + F3E03B1 + F3E03C1 on the
#                form used from 2014, so the series means the same thing
#                on both sides of the change of form;
#      V2_INSTR  instruction: F3E01 before 2014, F3E011 from 2014.
#    The code the live pipeline reads as for-profit institutional support,
#    F3E061, is "Other expenses - Total amount" in NCES's own dictionary.
# ---------------------------------------------------------------------------
V2_MAINT, V2_INSTR = "V2_MAINT", "V2_INSTR"


def _num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def normalize_finance_csv(path: str | Path, sector: str) -> None:
    """Rewrite one finance CSV under the fourth amendment's rules, in place."""
    path = Path(path)
    with open(path, encoding="latin-1", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return
    header = [h.strip().upper() for h in rows[0]]
    if sector == "forprofit" and V2_MAINT not in header:
        idx = {h: i for i, h in enumerate(header)}
        new_form = "F3E03C1" in idx

        def get(r, code):
            i = idx.get(code)
            return _num(r[i]) if i is not None and i < len(r) else None

        header += [V2_MAINT, V2_INSTR]
        for r in rows[1:]:
            if new_form:
                parts = [get(r, c) for c in ("F3E03A1", "F3E03B1", "F3E03C1")]
                parts = [x for x in parts if x is not None]
                maint = sum(parts) if parts else None
                instr = get(r, "F3E011")
            else:
                maint, instr = get(r, "F3E03"), get(r, "F3E01")
            r += ["" if maint is None else repr(maint), "" if instr is None else repr(instr)]
    rows[0] = header
    with open(path, "w", encoding="latin-1", newline="") as fh:
        csv.writer(fh).writerows(rows)


def apply_finance_rules() -> None:
    """Point the pipeline's for-profit field codes at the v2 columns (v2 processes only)."""
    import fetch_live_data as fld
    fld.FORPROFIT_FINANCE_FIELDS["institutional_support"] = V2_MAINT
    fld.FORPROFIT_FINANCE_FIELDS["instruction"] = V2_INSTR


apply_finance_rules()


_ROWS: dict = {}


def finance_sector(unitid: str, default: str, finance_dir: str | Path, end_year: int) -> str:
    """The sector whose finance form holds this institution's row in its scoring year.

    The same rule as the first test's: keep the header file's sector if
    that form has the row; otherwise use the one other form that does.
    """
    key = (str(finance_dir), end_year)
    if key not in _ROWS:
        _ROWS[key] = {}
        for sector in SECTORS:
            ids = set()
            for f in (Path(finance_dir) / sector / str(end_year - 1)).glob("*.csv"):
                with open(f, encoding="latin-1") as fh:
                    for row in csv.DictReader(fh):
                        ids.add((row.get("UNITID") or "").strip())
            _ROWS[key][sector] = ids
    rows = _ROWS[key]
    if unitid in rows.get(default, set()):
        return default
    others = [s for s in SECTORS if s != default and unitid in rows.get(s, set())]
    return others[0] if len(others) == 1 else default


def machine() -> dict:
    """What the run was executed on, recorded with every result."""
    cpu = ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout.split()
    return {"cpu": cpu, "python": platform.python_version(), "platform": platform.platform(),
            "environment variables": {k: os.environ.get(k) for k in
                                      ("NUMBA_CPU_NAME", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                                       "PYTENSOR_FLAGS", "NUMBA_CACHE_DIR")},
            "packages": freeze}


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))
