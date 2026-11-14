# Sampling Protocol v2: Retrained Classifier and Forward-in-Time Test

This protocol is committed before any institution is drawn, scored or trained on under it. It fixes, in advance, which institutions the second version of Tell's classifier is trained on, how it is frozen, which institutions it is then tested on, and how the test is judged, so that neither the classifier nor the test can be shaped after the fact.

## Relationship to the first confirmatory test

The first confirmatory test, under `sampling protocol.md`, did not pass. Of 278 scored institutions, 13 closed or merged; the frozen classifier flagged 12 of them and 241 of the 265 survivors, so its false-alarm rate was 0.91 and its J was 0.014 (95% interval −0.172 to 0.117). Triggers R1 (no discrimination) and R3 (excess false alarms) fired; R2 and R4 did not. That result stands as reported and is never replaced by anything under this protocol. Every result of both tests is published together.

Two causes were identified after outcomes were known, and this protocol is designed to remove both:

1. **Calibration.** The classifier was trained on the 54-institution validation panel, whose surviving institutions are mostly large, wealthy, well-documented institutions selected for being so, and whose closure rate (23 of 54) is roughly nine times the population's. On a random sample it read ordinary institutions as closures.
2. **The broken window.** Institutions skipped for insufficient data closed at 11.3% (54 of 476), against 4.7% (13 of 278) among scored institutions. Of the 54 skipped closures, 51 were skipped because a single year was missing from their College Scorecard enrollment, completion or tuition series, and 31 were for-profit institutions. The data rule removed, disproportionately, the institutions the test most needed.

Because these causes were identified with the first test's outcomes in view, nothing in this protocol is evaluated on the first test's institutions. Every institution the first test touched is excluded from the new test.

## Design phases

The phases run in this order, and each is committed to this repository before the next begins.

0. **Code changes and equivalence check** (below).
1. **Training draw**, from the fiscal year 2014 frame.
2. **Training scoring**, features only, at fiscal year 2014.
3. **Training outcomes**, from IPEDS header files for 2015 through 2019.
4. **Classifier v2 fit and freeze**, including its flag threshold.
5. **Test draw**, from the fiscal year 2019 frame, excluding every institution touched by the first test or by the training draw.
6. **Test scoring**, committed before any test outcome is looked up.
7. **Comparator flags**, committed before any test outcome is looked up.
8. **Test outcomes and measures.**

The 54-institution validation panel and the 16-institution exploratory pilot are not used for training or testing. The panel is scored by classifier v2 after phase 4 as a sanity check and reported, but is not a criterion of anything.

## Phase 0: code changes and equivalence check

The first test's pipeline rejected an institution if its enrollment, completion rate or in-state tuition was missing in any single year of the scoring window. Three changes let the model fit the years that are present, as it already does for finance and debt.

1. `src/fetch_live_data.py`: `build_live_series` records a missing enrollment, completion or tuition value as missing for that year instead of rejecting the institution.
2. `src/model.py`: the official and operational observation channels are fitted only at the years where they are observed, using the same masking already applied to the finance channels in the same model.
3. `src/real_adapter.py` and `src/score_institution.py`: every step that reads these series is made safe for missing years. In particular, the test of whether completion rates are recorded as percentages uses the largest observed value, not a maximum that a single missing year would make undefined, and peak enrollment is taken over observed years.

**Equivalence check.** Before any training institution is scored, the changed pipeline is run on the first 20 institutions, in slot order, that the first test scored with complete data. For each institution and each of the eight features, the changed pipeline's value at seed 7 must lie within the range spanned by the unchanged pipeline's values at seeds 7, 101 and 202. If any feature of any institution falls outside that range, the change is treated as having altered scoring for complete data; it is corrected and the check is repeated before anything else proceeds. Both runs and their comparison are committed.

**Early-finance check.** The training window reaches back to fiscal year 2004, earlier than any year the live finance pipeline has parsed so far. Before training scoring, a diagnostic confirms for 20 institutions in the training draw that every finance year from 2004 through 2014 is downloaded, read from the correct form and parsed into the four values the model uses. Any year whose file location or field codes differ is documented and handled before training scoring begins, and the diagnostic's output is committed.

## The missing-data signal

Two features are added to the classifier's eight, computed directly from which data are present, before any model is fitted.

For each fiscal year in an institution's scoring window, the year counts as **reported** if both the institution's College Scorecard enrollment and its own IPEDS finance row are present. Completion rate and tuition are not part of this definition: completion rates are routinely suppressed for small cohorts and tuition is absent for some program structures, so their gaps are handled by the masking above rather than read as distress.

Let the institution's **first reporting year** be the first year of the window in which it reported anything. Years before it are a leading gap, which usually means the institution opened partway through the window, and are ignored. Let n be the number of years from the first reporting year to the end of the window.

- **`gap_trailing`**: the number of consecutive unreported years at the end of the window, divided by n. An institution that stopped reporting before the scoring year has a positive value.
- **`gap_internal`**: the number of unreported years between the first reporting year and the last reported year, divided by n.

**Structural reporting is not a signal.** An institution that has no finance row of its own in any year of the window (typically a branch campus whose parent reports for it), or whose total revenue or total expenses are flagged "not applicable" by IPEDS in most years of the window, is classed as **structurally unscorable**. It is not scored, not used in training, and not counted in the test's measures; its later outcome is recorded and reported with the unscorable group below.

## Minimum record

An institution is scored if, within its 11-year window, it has at least three years with enrollment, completion rate and tuition all present, at least three parsed finance years, and the debt series the pipeline already requires. No year at the end of the window is required, since a missing final year is part of what `gap_trailing` measures. An institution that does not meet this minimum and is not structurally unscorable is classed as **unscorable**.

Unscorable and structurally unscorable institutions are never replaced by backups. They remain in the record with their outcomes, so that the share of closures falling outside the scored set is visible rather than hidden by replacement.

The three-seed stability check is no longer a skip rule. In the test, every scored institution is fitted with seeds 7, 101 and 202; its score and flag are those from seed 7, and any disagreement among the three flags is recorded as an attribute of the institution and reported. In training, only seed 7 is fitted.

## Phase 1: training draw

- **Frame:** the IPEDS header file (HD) for fiscal year 2014, restricted to SECTOR 1, 2 or 3 and DEGGRANT 1, the same restriction as the first test.
- **Order and selection:** sorted by UNITID ascending; step size k = floor(N / 600); every kth institution selected from the first.
- **Collisions:** panel and pilot institutions are skipped and replaced by the next institution in UNITID order. No other skip applies at the draw.
- **Target:** 600 drawn institutions.

The training frame is the 2014 frame, not the 2019 frame, because every institution in the 2019 frame survived until 2019 by construction, and a classifier trained only on survivors of the training period has no closures to learn from.

**Event floor.** If fewer than 40 scored training institutions closed or merged in phase 3, a second systematic pass is drawn once from the same frame, starting at position floor(k/2) + 1, scored and added before fitting. This rule is applied once and only once.

## Phase 2: training scoring

Each training institution is scored over the 11-year window ending in fiscal year 2014 (the pipeline's `start_year` 2003 and `end_year` 2014), under the changed pipeline, with the production sampler settings of the first test: 300 draws, 300 tuning steps, 2 chains, target_accept 0.9, cores 1, the Numba backend, seed 7. The ten features of every scored institution, its unscorable or structurally unscorable status otherwise, and the exact versions of all installed packages are committed.

College Scorecard values come from the same fixed copy of the "All Data Files" download used by the first test (SHA-256 ec66842e4c788a77818b81f23f2262020127d0524cc7132cf96e3207da463ec7).

## Phase 3: training outcomes

Training outcomes are read from the IPEDS header files for fiscal years 2014 through 2019, under the outcome definition below with the scoring year 2014. Looking up these outcomes is permitted: they are the outcomes the classifier is trained on, and they precede every test outcome.

## Phase 4: classifier v2 fit and freeze

- **Model:** the same form as the current classifier: features standardized, then a logistic regression with scikit-learn's default L2 penalty (C = 1), fitted on all scored training institutions with their primary-coding outcomes.
- **Features:** the eight current features plus `gap_trailing` and `gap_internal`.
- **Base rate:** because the training set is a systematic draw from the population rather than a set selected on outcome, the training closure rate is the population's, and the fitted intercept needs no prior correction. This is how the over-weighting of closures in the first classifier is removed.
- **Flag threshold:** fixed by 10-fold stratified cross-validation on the training set (random seed 20261114): the probability cut, on a grid of 0.01 steps, that maximizes the mean J across folds. It is rounded to two decimal places and frozen with the model. The first test's fixed cut of 0.5 is not used, since with a realistic base rate it would flag almost nothing.
- **Freeze:** the fitted coefficients, the scaler, the threshold, and the git blob hashes of every file in the scoring pipeline are committed in `data/v2/classifier v2.json` before the test draw. The test scoring script checks every hash before each batch and stops if any differs.

The cross-validated J at the frozen threshold is reported as an in-sample estimate only. It is not a test result.

## Phase 5: test draw

- **Frame:** the fiscal year 2019 header file, with the first test's restriction (2,876 institutions), minus every institution that appears anywhere in the first test's draw log, every institution in the training draw, and the panel and pilot.
- **Order and selection:** sorted by UNITID ascending; step size k = floor(N′ / 300), where N′ is the size of the reduced frame; every kth institution selected from the first.
- **Target:** 300 drawn institutions, with no backups.

## Phase 6: test scoring

Each test institution is scored over the 11-year window ending in fiscal year 2019 (`start_year` 2008, `end_year` 2019) with the frozen classifier v2 and the frozen pipeline, under the sampler settings and seeds above. All scores, flags, seed agreements, unscorable statuses and package versions are committed before any test outcome is looked up. The External Governance Attestation override is not applied, for the reason given in the first protocol.

## Phase 7: comparator

The critical-slowing-down comparator is computed exactly as committed under the first protocol: operating margin over fiscal years 2009–2019, linear detrending, a sliding 6-year window, Kendall's τ for variance and lag-1 autocorrelation, flagged when both are positive, and not computable for an institution with fewer than 8 of the 11 years. Its flags are committed before any test outcome is looked up.

## Outcome definition

The same definition is used for training (scoring year 2014, header files 2014–2019) and for the test (scoring year 2019, header files 2019–2025, the latest available).

**Primary coding.** An institution counts as having closed or failed if any of the following holds and the institution does not appear again as active (ACT equal to A or R) in a later header file:

- (a) a closure date (CLOSEDAT) falling after the end of the scoring year, in the scoring-year header file or any later one;
- (b) a year of deletion from IPEDS (DEATHYR) after the scoring year, or ACT equal to D;
- (c) a successor institution (NEWID) other than itself, that is, a merger or combination;
- (d) presence in the scoring-year header file and absence from the latest available header file, with no record of (a) to (c), counted as a closure.

An event under (a) to (c) followed by the institution's reappearance as active is a change in how the institution is reported, not a failure. This rule is fixed because the first test's diagnostic found Pennsylvania State University's main campus recorded under (b) and (c) in 2020, during a consolidation of its campuses' reporting, and active again from 2022.

**Sensitivity codings,** reported alongside the primary result but never used to evaluate the triggers:

- **Coding B:** events under (c) counted as surviving.
- **Coding C:** institutions under (d) counted as surviving, the first test's treatment.

## Measures and revision triggers

E, S, F, J, precision, closure rate and lift are defined as in the first protocol, for scored test institutions under the primary coding, with 95% Wilson intervals for S and F and a 95% percentile bootstrap interval for J (10,000 resamples, random seed 20261115). The flag is the frozen classifier v2's flag at its frozen threshold.

The minimum-number-of-events rule, triggers R1 to R4 and the definition of passing are those of the first protocol, applied unchanged to this test. A failure under this protocol is published in full, as the first test's is.

Additional pre-specified analyses, none of which changes a trigger or the pass criterion:

- **By sector.** S, F and J for public, private nonprofit and for-profit institutions separately. Because closures and missing data both concentrate among for-profit institutions, J is also reported within the for-profit sector alone; if the missing-data features separate closures from survivors overall but not within that sector, that is stated as evidence that they mainly encode sector.
- **Missing-data features.** The fitted coefficients of `gap_trailing` and `gap_internal`, and the test's S, F and J for classifier v2 refitted on the training set without them, so the contribution of the missing-data signal is visible.
- **Unscorable institutions.** The closure rate among unscorable and among structurally unscorable test institutions, compared with the scored institutions', as in the first test's broken-window analysis; and bounds on S and F over all drawn non-structural institutions, counting every unscorable institution first as flagged and then as not flagged.
- **Seed disagreement.** The number of scored test institutions whose three seeds disagree, and their outcomes.
- **Panel sanity check.** Classifier v2's flags on the 54-institution panel, reported descriptively.
- **Anchor analysis.** As in the first protocol, flagged survivors are examined for external backing, separately, changing no score or measure.

## Amendments

Before phase 6 begins, this protocol may be amended only to correct something that would otherwise prevent it from being carried out as written, and only on evidence that involves no test outcome. Each amendment is recorded at the end of this file with its date, the phase it was made in, what it changed and the evidence for it. After phase 6 begins, nothing in this file changes except the addition of results.

## First amendment (2026-11-14), during phase 0

This amendment was made during phase 0, before any training or test institution was drawn. The evidence for it comes only from refitting institutions the first test already scored; no outcome of any institution was used.

**1. The first equivalence check failed.** `check_v2_equivalence.yml` fitted the first 20 institutions the first test scored, once each, with the changed pipeline at seed 7, and its result is committed in `data/v2/equivalence check.json`. For 10 institutions, all eight features equaled the first test's committed seed-7 values exactly. For the other 10, the features computed directly from finance data still matched exactly, but features computed from the model's sampled trajectories differed slightly, and for 9 of them at least one such feature fell outside the range spanned by the first test's three seeds. Under the first test's frozen classifier, no institution's risk flag changed. None of the 10 has a gap in its College Scorecard data, so for each of them the changed code ran the original lines; every finance file was byte-for-byte the file the first test read, by SHA-256; and every installed package was the version the first test used. The institutions that differed and those that matched were scored in the same batches, minutes apart. The differences therefore point to running on a different machine rather than to the change, but the check as written could not show that, because the first test's three seeds do not span variation between machines.

**2. The check is replaced by a same-machine comparison.** `check_v2_equivalence_control.yml` fits each of the same 20 institutions three times on one machine, one after another and each in its own process: with the pipeline as it was before the v2 changes (the four changed files taken from commit 8a1608d, every other file identical), with the changed pipeline, and with the changed pipeline again. If the machine reproduces its own result exactly in every repeat, the check passes only if the old and changed pipelines agree exactly on every feature of every institution. If any repeat differs, the check passes only if, for every feature of every institution, the old-versus-changed difference is no larger than the largest repeat difference for that feature across the 20 institutions. "Exactly" allows floating-point slack of 1e-9 only. The result is committed in `data/v2/equivalence control.json`, and phase 1 begins only if it passes.

**3. Reporting.** The size of the variation between machines, as measured by the first check and the control check together, is reported with the test results, since it bounds how precisely any single score can be reproduced.

## Second amendment (2026-11-14), during phase 0

This amendment was made during phase 0, before any training or test institution was drawn, on evidence from refitting institutions the first test already scored; no outcome of any institution was used.

**1. The controlled check failed for one institution.** `check_v2_equivalence_control.yml`, whose result is committed in `data/v2/equivalence control.json`, found that the machine reproduced its own result exactly in every repeat, and that the old and changed pipelines agreed exactly on every feature for 19 of the 20 institutions. For the remaining institution, Alabama A & M University, the four features computed from the model's sampled trajectories differed between the two pipelines by up to 0.05. Its old-pipeline fit was the first model fit of the job, made before any compiled code had been cached, and it was the only fit in the job that reproduced the first test's committed seed-7 values exactly; every later fit, of either pipeline, agreed with every other fit on the same machine but not with the first test's values. This points to the state of the compile cache, not to the code, as the source of the difference, but the controlled check cannot separate the two, because the first fit of the job was always an old-pipeline fit.

**2. A cold-cache check is added.** `check_v2_equivalence_cold.yml` repeats the controlled comparison on one machine, with every fit run in its own process and starting from its own new, empty PyTensor compile directory and Numba cache directory, and with the order alternating: the old pipeline is fitted first for odd-numbered slots and the changed pipeline first for even-numbered slots, each followed by a repeat of the changed pipeline. Its pass rule is the controlled check's. Its result is committed in `data/v2/equivalence cold.json`, and phase 1 begins only if it passes. It also records how many cold old-pipeline fits reproduce the first test's committed values exactly.

**3. Consequence beyond phase 0.** If the cold-cache check confirms that the compile cache's state changes sampled features, every later fit under this protocol is run from an empty cache, so that each institution's score does not depend on what was fitted before it on the same machine; that rule would be added by a further amendment before phase 2, and the finding is reported with the test results.
