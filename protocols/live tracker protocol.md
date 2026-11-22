# Live tracker protocol (item 23h): scoring every college with tracker v3 on the newest data

Fixed November 21, 2026, before any college is scored on the live window. This is not a test: it applies the frozen tracker v3 (data/v3/classifier v3.json) to current data so the public dashboard shows what v3 reads now. Nothing is fitted, tuned or chosen after a score is seen.

## 1. What is scored

Every degree-granting college in the newest institutional header file NCES serves (HD2025 at the time of writing): SECTOR 1, 2 or 3 (four-year public, private nonprofit and for-profit) and DEGGRANT 1, the frame tracker v3 was trained and tested on, built with the same frame function as the v2 and v3 tests (draw v2 sample.py, build_frame), sorted by unit ID. No college is excluded for having been in a training or test set: the dashboard reads the whole four-year sector. Two-year colleges are outside v3's frame and are not scored. The header file and its SHA-256 are recorded.

## 2. The window and inputs

- **Window:** fiscal years 2014 to 2024 (start year 2013, end year 2024 in the pipeline's own labels), the newest eleven years of finance data, the same length as the v3 test's fiscal 2009 to 2019. Scoring year 2024.
- **Pipeline:** the frozen v3 scoring pipeline (v3_score_one.py with the drift terms of RICD §10.3a), unchanged. The live window is supplied by a launcher (src/v3_score_live_one.py) that adds it to the pipeline's window table at run time, so no frozen file changes, and the git blob hash of every pipeline file is checked against data/v3/classifier v3.json before every shard and merge.
- **Enrollment features:** from the compact College Scorecard file (the release fixed in build_scorecard_compact.py), for scoring year 2024 (the file's 2023 label, which is fiscal 2024).
- **Anchor sensor inputs (RICD §10.5b.13c):** f_approp, f_gift and S_par for the 2024 cohort (fiscal 2022 to 2024), computed by v3_anchors.py's own cohort function, unchanged, and written to data/live/anchors 2024.json; the frozen data/v3/anchors.json is not touched.
- **Rules carried over unchanged from the v3 test:** the structural-reporting rule, the minimum record, seed 7, one fit per process with empty compile caches, the frozen scaler, coefficients, intercept and cut points (for-profit and public-and-nonprofit), and the anchored flag (classifier v3's log-odds less the frozen anchor coefficients times the anchor inputs, judged at classifier v3's cuts, so anchoring can only clear a flag).

## 3. What each college gets

Scored, structurally unscorable, or unscorable (with the pipeline's own reason), as in the v3 test. For a scored college: its v3 probability and flag, its anchored score and anchored flag, its anchor inputs, and its nineteen features. A pipeline error or a failed NCES download says nothing about the college, so it is not recorded and the college is tried again in the next run. The size-and-sector baseline is not computed for the dashboard; it remains part of the reported test results.

## 4. Running

Twenty shards per run, each with a time budget; colleges not reached wait for the next run, which skips colleges already scored. Results are merged into numbered batches in data/live/scores/. A full pass of the sector takes several runs. Scores are redone once a year, when NCES releases a new finance year; the weekly workflow checks for a new release and scores only then.

## 5. The dashboard

The dashboard shows, for each scored college, the anchored flag (the tracker's reading after its anchors are counted), the v3 flag and probability, and the anchors that clear a flag, with a plain statement that a flag marks risk of closure, not a forecast that a college will close. The v1 prototype's live table retires.

## 6. Relation to the blind retest

These are interim scores on fiscal 2024 data. The blind retest has its own protocol and its own committed run on the newest data before NCES releases HD2026; this run serves as its rehearsal and does not replace it.

## 7. Records

Script src/score_live.py (frame, anchors, prefetch, shard, merge); launcher src/v3_score_live_one.py; workflow score_live.yml ("item 23h - score every college with v3 (live)"); outputs in data/live/.
