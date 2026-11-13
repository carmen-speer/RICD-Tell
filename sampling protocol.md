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

## Frozen scoring configuration

The classifier and feature pipeline are frozen at the following file versions (git blob hashes, which identify each file's exact contents):

- `src/classifier.py`: 13c946532f651501e3e99f8574a9ccdea8f4ae8d
- `data/panel/panel.json`: 8d1f5e4135ee278f80c4af937611ab68ff4b3f78
- `src/model.py`: ec8aac432fd772def527ca8d7db4dfa4c2e1aaf5
- `src/dynamics.py`: 0fb853c22972a9ccdfd2a44de82fcbf7513c81f8
- `src/real_adapter.py`: 7bcd88039d990d131e0ef0ac31b16531fd9defc8
- `src/score_institution.py`: 30d65337f8e45cc88e84a48a99250a2943e0a765
- `src/fetch_live_data.py`: 4c93cb61998d834b25dea502f17b7698154497a1

The confirmatory scoring script checks these hashes before scoring each batch and stops if any file differs.

Every fit uses the production sampler settings: 300 draws, 300 tuning steps, 2 chains, target_accept 0.9, cores 1, and the Numba backend. The three seeds for the stability check are 7 (the production seed), 101 and 202; the score and flag reported for an institution are those from seed 7. The exact version of every installed package is recorded with each committed batch of scores.

### Governance override in the confirmatory run

The External Governance Attestation override is not applied in the confirmatory run. Its current list draws on accreditor actions taken after fiscal year 2019, which would introduce post-2019 information into FY2019 scores; every institution on the list is in the validation panel and is already excluded by the collision rule, and no new attestations are researched for confirmatory institutions.

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

## Pre-stated contingency: results that revise the framework's claims

This section is committed before any confirmatory institution has been scored and before any outcome has been looked up. It states in advance which results change what the framework and this repository claim, as distinct from results that are only reported with a caveat. After scoring begins, nothing in this section is changed.

### Definitions

- **E:** the number of scored confirmatory institutions that closed or merged under the outcome definition above.
- **S (sensitivity)** and **F (false-alarm rate)** as defined under Pre-specified measures.
- **J = S − F** (Youden's index). J = 0 is a classifier with no skill, one that flags institutions that later closed at the same rate as institutions that survived.
- **Flag:** the frozen classifier's `high_risk` prediction at its existing 0.5 probability cut, with no recalibration to the confirmatory sample's closure rate.
- **Intervals:** 95% Wilson intervals for S and F; a 95% percentile bootstrap interval for J (10,000 resamples of the scored institutions, random seed 20261112).

### Minimum number of events

If E is below 10, the test cannot estimate sensitivity usefully. The result is reported as underpowered for sensitivity, no confirmatory claim is made in either direction, and only trigger R3 below is evaluated.

### Revision triggers

**R1 — No discrimination.** If the lower bound of J's interval is at or below 0, the claim that Tell's flag carries information about later closure outside the 54-institution panel is withdrawn. The README's validated result is restated as internal validation only, alongside the failed confirmatory result, and the classifier is not presented as a reader of distress in the general population until a new, separately pre-registered test on a fresh sample passes.

**R2 — Low sensitivity.** If E is at least 10 and S is below 0.50, the classifier is recorded as missing most closures in the general population. This triggers re-examination of the directional-entropy fix (comparing the current downside-only `frac_high_entropy` construction against the superseded gated construction on the confirmatory sample) and of `reserve_adequacy`'s extrapolation outside the panel's range. Any change that results is a new classifier version, which requires its own pre-registered test on a fresh sample; the confirmatory result for the frozen classifier stands as reported and is never replaced by the revised version's performance on this same sample.

**R3 — Excess false alarms.** If F is above 0.30, the claim that a flag marks distress specific enough to act on is withdrawn for the general population. The "distress, not collapse" interpretation may not be invoked to reclassify any confirmatory false alarm as a correct flag; the anchor analysis is reported separately and changes no score, flag or measure.

**R4 — No advantage over standard indicators.** If the critical-slowing-down comparator's J is equal to or greater than the tracker's J, the claim that RICD's divergence features add early-warning signal beyond standard indicators is withdrawn for this domain. The comparator's flag rule (which series, which window, and the cut on the trend in variance and lag-1 autocorrelation) is committed to this repository before any outcome is looked up.

### What counts as passing

The confirmatory test is reported as passed only if E is at least 10, the lower bound of J's interval is above 0, S is at least 0.50, and F is at most 0.30. Precision is reported together with the sample's closure rate and the lift (precision divided by that rate); because the panel's closure rate (23 of 54) is far above the population's, a fall in precision relative to the panel is expected and is not on its own evidence for or against the classifier. No subset of the confirmatory sample (by sector, size or state) is reported as the headline result.

## Draw log

The draw is recorded in a log committed to this repository. For every institution the draw touches, the log records:

- its position in the ordered frame;
- its UNITID and name;
- whether it was selected, or skipped and why (panel, pilot, duplicate, or insufficient data, with the check it failed and the type of data gap);
- for scored institutions, the risk score and flag;
- the commit timestamp of the scores.

The log records N, k and the final count of scored and skipped institutions.
