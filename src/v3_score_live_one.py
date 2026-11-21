"""
Launcher for the live tracker ("live tracker protocol.md", section 2).

Adds the live window (fiscal years 2014 to 2024: pipeline labels 2013 to
2023, end year 2024 exclusive, the same length as the v3 test's window) to
the frozen pipeline's window table at run time, then runs the frozen
v3_score_one.py unchanged. No frozen pipeline file is edited, so their git
blob hashes still match data/v3/classifier v3.json.

Usage: the same arguments as v3_score_one.py, with --window live.
"""
from __future__ import annotations

import v2_common as v2

LIVE_WINDOW = {"start_year": 2013, "end_year": 2024}   # FY2014-FY2024
v2.WINDOWS["live"] = LIVE_WINDOW

import v3_score_one  # noqa: E402  (imported after the window is added)

if __name__ == "__main__":
    v3_score_one.main()
