"""
One-off diagnostic: prints, year by year, exactly which of the four
required College Scorecard fields (enrollment size, admission rate,
4-year completion rate, in-state tuition) is present or missing for
one or more institutions across 2013-2023.

Why this exists: fetch_live_data.build_live_series() requires all four
fields to be present in every single year, with zero tolerance -- one
missing field in one year fails the whole institution, and the
function only ever reports "insufficient data," never which field or
year broke it. University of Phoenix-Arizona has hit this wall with no
visibility into why.

A real, well-documented possibility worth checking directly rather
than assuming: completion_rate_4yr_150nt specifically measures a
first-time, full-time, bachelor's-seeking cohort completing within
150% of expected time. That cohort definition fits poorly for
institutions with large adult, part-time, transfer, or online
populations -- exactly the profile of a for-profit like Phoenix -- and
NCES/College Scorecard frequently report this specific field as null
for such institutions. That would not mean the institution's real
completion outcomes are unknowable, only that this particular
first-time-full-time definition doesn't describe how most of its
students actually enroll. This script exists to confirm or rule that
out with real per-year data, not to assume it.

Usage: python diagnose_scorecard_gaps.py [unitid ...]
  Defaults to University of Phoenix-Arizona (484613) and West Virginia
  University (238032) if no UNITIDs are given.
"""
from __future__ import annotations

import sys

import fetch_live_data as fld

FIELDS = {
    "student.size": "enrollment size",
    "admissions.admission_rate.overall": "admission rate",
    "completion.completion_rate_4yr_150nt": "4-yr completion rate",
    "cost.tuition.in_state": "in-state tuition",
}


def diagnose(unitid: str, start_year: int = 2013, end_year: int = 2024) -> None:
    print(f"\n{'=' * 70}\nUNITID {unitid}: per-year, per-field availability, {start_year}-{end_year - 1}\n{'=' * 70}")
    for year in range(start_year, end_year):
        fields = [f"{year}.{key}" for key in FIELDS]
        try:
            result = fld.fetch_scorecard_fields(unitid, fields)
        except Exception as e:
            print(f"  {year}: REAL API ERROR -- {type(e).__name__}: {e}")
            continue
        if not isinstance(result, dict):
            print(f"  {year}: UNEXPECTED SHAPE -- fetch_scorecard_fields returned "
                  f"{type(result).__name__} instead of dict. Raw value: {result!r}")
            continue
        row = []
        for key, label in FIELDS.items():
            full_key = f"{year}.{key}"
            value = result.get(full_key)
            row.append(f"{label}={value if value is not None else 'MISSING'}")
        print(f"  {year}: " + ", ".join(row))


def main() -> None:
    unitids = sys.argv[1:] or ["484613", "238032"]  # Phoenix, WVU by default
    for unitid in unitids:
        diagnose(unitid)


if __name__ == "__main__":
    main()
