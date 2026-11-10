# Sampling Protocol: Confirmatory Out-of-Sample Test

This protocol is committed before any confirmatory institution is drawn or scored. Its purpose is to fix every decision about which institutions are tested, how they are scored, and how results are judged, so that the test's outcome cannot be shaped after the fact.

## Purpose

The tracker reached 100% leave-one-out accuracy on its 54-institution validation panel. That panel was designed to be representative, not random, so leave-one-out accuracy shows the classifier is internally consistent but does not show how it performs on institutions nobody chose. This test scores 300 institutions selected by a fixed, mechanical rule, using only data available in fiscal year 2019, and then checks the scores against what actually happened to those institutions afterward.

## Design phases

The tracker's institutions fall into three separate groups, which are always reported separately and never pooled.

1. **Validation panel (54 institutions).** Chosen deliberately to represent the range of institutional types and outcomes. Used to build and validate the classifier.
2. **Exploratory pilot (16 institutions).** The first live-scored institutions, chosen by a mix of methods documented in `src/score_batch.py`. Reported as a pilot set, because their selection methods were mixed.
3. **Confirmatory sample (300 institutions).** Drawn by systematic sampling under this protocol. This is the test.

## Sampling method

The method is systematic sampling.

- **Frame:** the IPEDS Institutional Characteristics header file (HD) for fiscal year 2019, restricted to institutions with SECTOR equal to 1, 2 or 3 (public, private nonprofit and private for-profit four-year institutions) and DEGGRANT equal to 1 (degree-granting).
- **Order:** the frame is sorted by UNITID, ascending.
- **Step size:** k = floor(N / 300), where N is the number of institutions in the filtered frame.
- **Selection:** starting from the first institution in the ordered frame, every kth institution is selected.
- **Target:** 300 scored institutions.

## Collision rule

A selected institution is skipped and replaced by the next institution in UNITID order if any of the following is true:

- it is in the 54-institution validation panel;
- it is in the 16-institution exploratory pilot;
- it duplicates an institution already drawn;
- it fails the insufficient-data rule below.

If replacements reach the end of the ordered frame, selection continues from the start of the frame. Every skip is recorded in the draw log with its reason.

## Insufficient-data rule

An institution is classified as having insufficient data, and is skipped and replaced, if it fails any one of these three checks.

1. **Data check.** It lacks at least five consecutive fiscal years of complete finance data ending in fiscal year 2019.
2. **Convergence check.** Its model fit shows any divergent transitions, or any parameter with R-hat above 1.01. This catches the funnel geometry that data-scarce institutions produce.
3. **Stability check.** Fits run with three different random seeds do not all agree on the institution's risk flag.

Institutions that fail are never debugged, refit, reparameterized or otherwise rescued. They are skipped and replaced, and the skip is logged along with the type of data gap that caused it.

Skipped institutions are not discarded from the analysis. Their later outcomes are recorded alongside the scored institutions' outcomes, to test whether missing or unstable data is itself associated with closure. This is the "institutional broken window" hypothesis: a visible failure in an institution's official reporting layer may itself be a sign of distress.

## Scoring rules

- Institutions are scored using fiscal year 2019 data and earlier only.
- The classifier is frozen in its current validated form. No feature, threshold, prior or setting is changed during or after the confirmatory run.
- All scores are committed to this repository, with a timestamp, before any institution's outcome is looked up.

## Outcome definition

An institution counts as having closed or failed if, in any IPEDS header file released after fiscal year 2019, it shows a closure date (CLOSEDAT), a year of deletion from IPEDS (DEATHYR), or a merger into another institution (MERGEID). All other institutions count as surviving.

## Pre-specified measures

Primary measures:

- **Sensitivity:** the share of institutions that closed or merged which the tracker flagged.
- **False-alarm rate:** the share of surviving institutions which the tracker flagged.
- **Precision:** the share of flagged institutions which went on to close or merge.

Secondary measures:

- **Comparison with standard early-warning indicators.** The same institutions are scored using the critical-slowing-down indicators, rising variance and rising lag-1 autocorrelation, computed on the same fiscal year 2019 data, and their sensitivity, false-alarm rate and precision are compared with the tracker's.
- **Anchor analysis.** Flagged institutions that survived are examined for external backing (such as state appropriations, rescue funding or revenue diversification), as a separate analysis that does not change the classifier or its scores.
- **Insufficient-data outcomes.** The closure and merger rate among institutions skipped for insufficient data is compared with the rate among scored institutions.

## Draw log

The draw is recorded in a log committed to this repository. For every institution the draw touches, the log records:

- its position in the ordered frame;
- its UNITID and name;
- whether it was selected, or skipped and why (panel, pilot, duplicate, or insufficient data, with the check it failed and the type of data gap);
- for scored institutions, the risk score and flag;
- the commit timestamp of the scores.

The log records N, k and the final count of scored and skipped institutions.
