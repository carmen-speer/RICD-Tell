# Sampling Protocol: Confirmatory Out-of-Sample Test

This protocol is committed before any confirmatory institution is drawn or scored. Its purpose is to fix every decision about which institutions are tested, how they are scored, and how results are judged, so that the test's outcome cannot be shaped after the fact.

It was amended twice: on 2026-11-12, after the draw and before any confirmatory institution was scored, and on 2026-11-13, after the first two scoring batches and before any outcome was looked up. Each amendment, what it changed and the evidence for each change are set out at the end of this file.

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

An institution is classified as having insufficient data, and is skipped and replaced, if it fails either of these two checks.

1. **Data check.** It lacks at least five consecutive fiscal years of complete finance data ending in fiscal year 2019, or the pipeline cannot build its complete College Scorecard series (enrollment, completion rate and in-state tuition in every year of the scoring window) or its debt series.
2. **Stability check.** Fits run with three different random seeds do not all agree on the institution's risk flag.

Divergent transitions and R-hat are recorded for every fit, but neither causes a skip. The original rule's convergence check (no divergent transitions and no R-hat above 1.01) was removed by the amendment, because on the validation panel it skipped every institution at production settings and, at higher sampling effort, skipped every closure while keeping most surviving institutions; see "Amendment before scoring." The stability check is the test of whether a fit is reliable enough to score: it asks directly whether the flag, which is the quantity being tested, depends on the sampler's random seed.

Institutions that fail are never debugged, refit, reparameterized or otherwise rescued. They are skipped and replaced, and the skip is logged along with the type of data gap that caused it.

Skipped institutions are not discarded from the analysis. Their later outcomes are recorded alongside the scored institutions' outcomes, to test whether missing or unstable data is itself associated with closure. This is the "institutional broken window" hypothesis: a visible failure in an institution's official reporting layer may itself be a sign of distress.

## Scoring rules

- Institutions are scored using fiscal year 2019 data and earlier only, over an 11-year window covering fiscal years 2009 through 2019 (the pipeline's `start_year` 2008 and `end_year` 2019).
- Finance data are read from the IPEDS finance form (F1A, F2 or F3) on which the institution's own FY2019 finance row is filed, using that form's established variables (see "Second amendment").
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
- `src/fetch_live_data.py`: d56d8231e6dd82bcd10a061f676ea40bd5e1ba76
- `src/build_scorecard_compact.py`: ce3683908488ecd8f590a9a4021df255a3416352

The confirmatory scoring script checks these hashes before scoring each batch and stops if any file differs.

Enrollment, completion rate, in-state tuition and admission rate come from one fixed copy of the U.S. Department of Education's College Scorecard "All Data Files" download (`College_Scorecard_Raw_Data_11022026.zip`, 561,612,763 bytes, SHA-256 ec66842e4c788a77818b81f23f2262020127d0524cc7132cf96e3207da463ec7), kept unchanged as an asset of this repository's release `scorecard-raw-data-2026-11-02`. `src/build_scorecard_compact.py` refuses any file whose SHA-256 differs. They do not come from the College Scorecard API, which has no record for institutions that have since closed.

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

## Amendment before scoring (2026-11-12)

This amendment was made after the draw and before any confirmatory institution was scored or any outcome was looked up. Every change below rests on measurements of the 54-institution validation panel only, which is excluded from the confirmatory sample by the collision rule, and on the completeness of the drawn institutions' pre-2019 College Scorecard data. No confirmatory institution was fitted, and no confirmatory outcome was consulted.

**1. Convergence check removed as a skip rule.** `check_panel_convergence.yml` fitted the panel under the confirmatory conditions. At production settings (300 draws, 300 tuning steps, 2 chains), 0 of 34 fitted institutions met R-hat ≤ 1.01, so the rule as committed would have skipped every confirmatory institution. At 1000 draws, 1000 tuning steps and 4 chains, 25 of 27 surviving institutions met it but 0 of 3 closures did, all three with divergent transitions; across the two settings the flag was the same for all 30 institutions fitted at both. A rule that removes closures specifically would bias the test's sensitivity in a direction the scores could not reveal. Divergent transitions and R-hat are now recorded for every fit and do not cause a skip; the three-seed stability check remains.

**2. College Scorecard data taken from a fixed bulk file, not the API.** `diagnose_window_data.yml` found that the College Scorecard API returns no record at all for 20 of the panel's 23 closures, so under the original pipeline almost every institution that closed after 2019 would have failed the data check, and closures would have gathered in the skipped group instead of being scored. The Department of Education's bulk "All Data Files" download keeps closed institutions for the years they reported. `diagnose_window_choice.yml` compared the two sources wherever the API has a record: 1,897 values across 34 institutions, with 0 mismatches, so the change alters where the numbers come from, not what they are. The file used is fixed by its SHA-256 under "Frozen scoring configuration." It is kept as a release asset because the Department's download site refuses requests from GitHub Actions.

**3. Scoring window set to fiscal years 2009-2019.** The original configuration's window began in 2013, giving six fiscal years ending in FY2019. At that window the classifier flagged every panel institution it scored (53 of 53, Harvard and Princeton included). That is consistent with several features depending on series length while the classifier was trained on longer series (the panel's own features cover 2005-06 through 2022-23), and the longer windows below behave accordingly. `diagnose_window_choice.yml` scored the panel at three windows ending in FY2019, chosen before that run: from 2005 (14 years), 2008 (11 years) and 2013 (6 years). Results: from 2005, 14 of 18 scored closures and 2 of 30 scored surviving institutions flagged (42 of 48 correct); from 2008, 19 of 19 closures and 2 of 30 surviving institutions flagged (47 of 49 correct); from 2013, every institution flagged (22 of 53 correct). The window from 2008 was chosen. Two cautions apply. These accuracies are in-sample, because the classifier was trained on these institutions, so they show that the six-year window is broken; they do not validate the chosen one. And the choice among the three windows was made with the panel's outcomes in view; the confirmatory sample played no part in it. The window from 2008 is also the 11-year length the weekly live scoring already uses.

**4. Admission rate no longer required.** Admission rate is not a model input anywhere in the live pipeline; it was only ever a gate, and the pipeline already exempted for-profit institutions from it. Open-admission public and private colleges do not report it. Among the 300 drawn institutions, 160 had complete College Scorecard series for the scoring window under the original gate; admission rate was missing in at least one year for 105 of them and was the only gap for 38. With the gate removed for every sector, 198 of the 300 have complete series before backups. No institution that already passed scores differently, since the value is never read.

**5. Frozen-file hashes updated.** `src/fetch_live_data.py` changed (items 2 and 4) and `src/build_scorecard_compact.py` was added (item 2); their hashes above replace the originals. No other frozen file changed.

**Known consequence.** Even after these changes, roughly a third of the drawn institutions will lack complete data for an 11-year window (missing completion rate, tuition or enrollment in some year, or not appearing in some years at all, often because they opened after 2008) and will be replaced by backups. The scored sample therefore leans toward institutions with complete reporting over 2009-2019. Every skipped institution and the reason for its skip are recorded, and their later outcomes are compared with the scored institutions' outcomes under the "institutional broken window" analysis.

## Second amendment (2026-11-13), during scoring

This amendment was made after the first two scoring batches had been committed (12 slots finalized) and before any outcome was looked up. It changes how finance data are located, not what the model reads or how it scores. No finalized slot is affected: none of the evaluations it touches had been assigned to a slot, and no skip in a finalized slot's record involves finance data.

**1. Finance form chosen from where the institution files.** IPEDS collects finance on three forms: F1A (public institutions, GASB standards), F2 (private nonprofit institutions, FASB standards) and F3 (for-profit institutions). The pipeline chose the form from the institution's sector, so it read every public institution from F1A. `diagnose_finance_form.yml` showed that seven drawn public institutions file F2 instead. Six of them (Temple University, Pennsylvania State University's main campus, Pennsylvania College of Technology, Lincoln University in Pennsylvania, Radford University-Carilion and Sinte Gleska University) report complete figures on F2 for every year of the window; under the original rule they were recorded as having "insufficient parsed finance data," which misstated their data and would have removed a group of large public universities from the sample. The seventh, the University of Pittsburgh-Bradford, also files F2, but its total revenue and total expenses there are flagged not applicable (as under item 2), so it is evaluated again on the correct form and is expected to fail the data check for that reason. The pipeline is now given the sector whose form holds the institution's own FY2019 finance row, so an F2-filing public institution is measured exactly as every private institution is, with the same variables the classifier was trained on. An institution whose rows sit on different forms in different years of the window (two Purdue University Global campuses, which moved from F3 to F2 in 2017) is not changed, and fails the data check if its data is incomplete. The form used is recorded with each evaluation. No frozen file changed; the selection is made in `src/score_confirmatory.py`.

**2. Totals reported as not applicable remain skips.** The same diagnostic found 21 institutions (among them UCLA, UC Irvine, UC Riverside, UC San Diego, Ohio University's regional campuses, Kent State University at Salem, Castleton University, three Inter American University of Puerto Rico campuses and the U.S. Merchant Marine Academy) whose instruction and institutional-support figures are reported every year but whose total revenue or total expenses, among the four values the model reads, are blank and flagged "A" (not applicable) by IPEDS for most of the window. Supplying those totals would mean substituting other variables the classifier was not trained on, which would require its own validation, so these institutions continue to fail the data check. Of the diagnostic's other finance failures, 13 have no finance row of their own on any form (mostly branch campuses whose parent reports for them), and the rest have no FY2019 finance row, a history that begins too late for five complete years ending in FY2019, or rows on different forms in different years; all of these are genuine gaps under the data check. The skipped sample therefore leans toward campuses that belong to a university system; their later outcomes are still compared with the scored institutions' outcomes under the "institutional broken window" analysis.

**3. Voided evaluations.** `data/confirmatory/voided evaluations.json` lists every recorded evaluation that is void, with its reason and the log that shows it: eleven from the first batch whose finance downloads failed partway through (NCES's server dropped connections), and the seven F2-filing institutions under item 1. A voided evaluation is ignored and the candidate is evaluated again. Batch files are never edited, and no evaluation in a finalized slot's record can be voided.

**4. Implementation changes that alter no rule.** Each batch now downloads every NCES finance file the window needs once, with retries, and records each file's SHA-256 in the batch; every fit reads those copies, so the files parsed are byte-for-byte the files the pipeline would have downloaded. An evaluation during which any finance download failed is held for retry instead of recorded. A waiting slot's whole backup list is evaluated in one batch, which changes how many batches the run takes but not which institution fills any slot.
