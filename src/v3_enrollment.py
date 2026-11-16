"""
The three enrollment features of "sampling protocol v3.md".

They are computed from undergraduate enrollment (UGDS) in the compact
College Scorecard file the pipeline already builds (build_scorecard_compact.py,
from the fixed copy whose SHA-256 the protocols record), over the same
11-year window the institution is scored on. A year's value counts only if
it is a positive number; NULL, PrivacySuppressed and zero are missing.

With L the window's last year label (2013 for scoring year 2014, 2018 for
scoring year 2019; the compact file labels fiscal year Y as Y - 1) and the
window's years L - 10 to L:

  log_enrollment         the natural log of enrollment in the latest year
                         of the window that has a value;
  below_peak             the log of that latest enrollment divided by the
                         largest enrollment in the window (0 at the peak,
                         negative below it);
  enrollment_change_5y   the log of that latest enrollment divided by the
                         enrollment in the latest year with a value that is
                         at least five years earlier within the window, or 0
                         if there is no such year.

If no year of the window has a value, all three are None.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

FEATURES = ["log_enrollment", "below_peak", "enrollment_change_5y"]
LAST_LABEL = {2014: 2013, 2019: 2018}


def load(compact: str | Path, unitids: set[str] | None = None) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    with open(compact, newline="") as f:
        for row in csv.DictReader(f):
            u = (row.get("UNITID") or "").strip()
            if unitids is not None and u not in unitids:
                continue
            try:
                v = float(row.get("UGDS") or "")
            except ValueError:
                continue
            if v > 0 and math.isfinite(v):
                out.setdefault(u, {})[int(row["YEAR"])] = v
    return out


def features(series: dict[int, float] | None, scoring_year: int) -> dict:
    last_label = LAST_LABEL[scoring_year]
    years = sorted(y for y in (series or {}) if last_label - 10 <= y <= last_label)
    if not years:
        return {k: None for k in FEATURES}
    last = years[-1]
    size = series[last]
    peak = max(series[y] for y in years)
    earlier = [y for y in years if y <= last - 5]
    change = math.log(size / series[earlier[-1]]) if earlier else 0.0
    return {"log_enrollment": math.log(size), "below_peak": math.log(size / peak), "enrollment_change_5y": change}
