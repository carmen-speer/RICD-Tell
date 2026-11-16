# Sampling Protocol v3: Within-Sector Test on Every Remaining 2019 Institution

This protocol is committed before classifier v3 is fitted and before any v3 test institution is listed, scored or looked up. It fixes in advance how classifier v3 and the anchor sensor are built, which institutions they are tested on, and how the test is judged.

## Relationship to the earlier tests

**The first confirmatory test** (`sampling protocol.md`) did not pass. **The v2 test** (`sampling protocol v2.md`) passed its pre-registered criteria: of 245 scored institutions, 11 closed or failed; classifier v2 flagged 6 of them and 33 of the 234 survivors (S = 0.55, F = 0.14, J = 0.40, 95% interval 0.08 to 0.72), against the critical-slowing-down comparator's J of −0.09. Both results stand as reported and are never replaced by anything under this protocol.

The v2 test's own pre-specified sector analysis showed where that result came from. Classifier v2 flagged every scored for-profit institution, which caught all 5 for-profit closures, and caught 1 of the 6 closures among public and private nonprofit institutions. Within the for-profit sector its J was 0; among public institutions it was −0.10 and among private nonprofit institutions 0.18. A rule that flags every for-profit institution and nothing else would have had J = 0.39 on the same institutions, close to classifier v2's 0.40 (a comparison made after outcomes were known, and reported as such).

The v2 test therefore showed that the tracker separates for-profit institutions from the rest, and did not show that it can tell a failing institution from a healthy one within the same sector. This protocol tests that. It is the third pre-registered test of the tracker, and every result of all three is published together.

## What the development data showed

Before this protocol was written, the institutions whose outcomes are already known (the v2 training set, scoring year 2014, and the v2 test, scoring year 2019; together 670 scored institutions, 70 closures, 19 of them among public and private nonprofit institutions) were examined to decide what classifier v3 should change. Looking at these outcomes is permitted, because no institution in them can be in the v3 test. Three findings shaped this protocol:

1. **The tracker's features carry a weak signal within the nonprofit sectors.** Among public and private nonprofit institutions, the out-of-fold area under the ROC curve of the tracker's ten features was about 0.68.
2. **Institution size carries a stronger one.** Undergraduate enrollment alone reached about 0.74 among the same institutions, and adding the tracker's ten features to enrollment did not raise it.
3. **The flag threshold matters as much as the model.** With one threshold for every institution, the threshold that suits for-profit institutions flags almost no nonprofit institution.

Because finding 2 rests on only 19 nonprofit closures, it is a reason to test the question, not an answer to it. This protocol therefore reaches two verdicts: whether classifier v3, which combines the tracker's features with size and sector, passes the agreed criteria; and, separately, whether the tracker's own features add anything beyond size and sector.

## Two additions before the freeze: the drift terms and the anchor sensor

The development data also suggested why the tracker misses most nonprofit closures: they are drift-type, a slow slide toward break-even rather than a sudden loss, and many institutions in deep distress survive because an outside party absorbs their deficit. Two additions follow from RICD 17.4, and both are built and frozen before any v3 test institution is listed.

**The drift terms (RICD §10.3a).** The scoring model gains the drift-type and shock-type collapse terms: a local linear trend on log enrollment relative to its peak, with heavy-tailed steps for sudden losses, and the headroom term of §10.3's adaptive possibility. With the terms switched off, the model is exactly the v2 model; the v3 reproducibility check (`check_v3_reproducibility.yml`, `data/v3/reproducibility check.json`) confirmed this on the same machine. Five read-outs of the drift terms become features of classifier v3: `enroll_drift`, `slide_rate`, `collapse_urgency`, `coverage_final` and `enroll_jump_recent`. Every development institution was rescored with the terms switched on, at seed 7 (`score_v3_development.yml`, `data/v3/development scores/`).

**The anchor sensor (RICD §10.5b.13c).** A separate layer reads each institution's one-directional anchors from information dated at or before its scoring year: appropriations and gifts as three-year shares of total expenses, and membership in a public or nonprofit system (`v3_anchors.yml`, `data/v3/anchors.json`; the codes and the reasons for them are recorded in `src/v3_anchors.py`). It is combined with classifier v3's reading as an additive correction to the log-odds and can only clear a flag, never raise one.

**Processor dependence.** The pipeline's results are identical on repeated runs on one processor family, but differ slightly between families (by up to about 0.1 on some features). The processor of every result is recorded, and the count and flag rate on each processor are reported with the results.

## Design phases

The phases run in this order, and each is committed to this repository before the next begins.

0. **Already done before the freeze:** the v3 reproducibility check, the development rescoring and the anchor flows, described above.
1. **Classifier v3, the size-and-sector baseline and the anchor sensor, fit and freeze** (`fit_classifier_v3.yml`).
2. **Test list**: every remaining institution in the 2019 frame (`draw_v3_test.yml`).
3. **Test scoring**, committed before any test outcome is looked up (`score_v3_test.yml`).
4. **Comparator flags**, committed before any test outcome is looked up (`v3_comparator.yml`).
5. **Test outcomes, measures and verdicts** (`v3_test_results.yml`).

The scoring pipeline is the v3 pipeline: the v2 pipeline with the drift terms switched on (`v3_score_one.py`). Classifier v3 records the git blob hash of every pipeline file; the fit refuses to run unless every development result ran with those files, and scoring refuses to run if any differs from those frozen with classifier v3. The software environment, the sampler settings and the one-fit-per-process, empty-cache rule are those of the v2 protocol's third amendment.

## Phase 1: classifier v3 and the baseline

- **Development set:** every scored institution of the v2 training set and of the v2 test, as rescored with the v3 pipeline, with its primary-coding outcome read from the committed v2 outcome files (for the v2 test, the corrected phase 8 run). An institution scored in v2 that cannot be scored with the drift terms is left out of the fit and listed.
- **Features of classifier v3:** the eight model features at seed 7, `gap_trailing` and `gap_internal`; `forprofit`, equal to 1 for an institution in the for-profit sector of its draw and 0 otherwise; three enrollment features, defined below; and the five drift features.
- **Features of the size-and-sector baseline:** `forprofit` and the three enrollment features only.
- **Model, for both:** features standardized, then logistic regression with scikit-learn's default L2 penalty (C = 1), fitted on the whole development set.
- **Thresholds, for both:** two cuts, one for for-profit institutions and one for public and private nonprofit institutions, fixed together by 10-fold cross-validation on the development set (random seed 20261114, folds stratified on outcome and sector together): the pair of cuts that maximizes the mean J across folds, with the nonprofit cut on a grid from 0.01 to 0.99 and the for-profit cut on a grid from 0.00 to 0.99, in steps of 0.01. A for-profit cut of 0.00 flags every for-profit institution. On ties the lowest nonprofit cut is taken, then the lowest for-profit cut.
- **Anchor sensor:** the primary outcome is regressed on the anchor inputs `f_approp`, `f_gift` (each capped at 1) and `S_par`, by logistic regression without an intercept, with non-negative coefficients and the same L2 penalty (C = 1), with classifier v3's out-of-fold log-odds as an offset, so that only the anchor terms are estimated. The anchored log-odds are classifier v3's log-odds minus the fitted anchor terms, and the anchored flag uses classifier v3's own cuts, so anchoring can only clear a flag. An institution with no anchor record or no total expenses gets anchor inputs of 0.
- **Freeze:** the scalers, coefficients, intercepts and cuts of both models, the anchor coefficients, the pipeline file hashes, the processor counts of the development results, and the cross-validated estimates are committed in `data/v3/classifier v3.json` before the test list is drawn up. The cross-validated estimates are in-sample only and are not a test result.

**Enrollment features.** They are computed from undergraduate enrollment (UGDS) in the compact College Scorecard file built from the fixed copy recorded in the earlier protocols (SHA-256 ec66842e4c788a77818b81f23f2262020127d0524cc7132cf96e3207da463ec7), over the institution's 11-year scoring window. A year's value counts only if it is a positive number. With the window's latest year that has a value:

- `log_enrollment` is the natural log of that year's enrollment;
- `below_peak` is the log of that enrollment divided by the largest enrollment in the window;
- `enrollment_change_5y` is the log of that enrollment divided by the enrollment in the latest year with a value at least five years earlier in the window, or 0 if there is none.

## Phase 2: the test list

The v3 test is not a sample. It is every institution in the fiscal year 2019 header file (HD2019) with SECTOR 1, 2 or 3 and DEGGRANT 1, the frame of the first and v2 tests, except:

- every institution in the first test's draw log or evaluated by it as a backup;
- every institution in the v2 training draw (and its second pass, had there been one);
- every institution in the v2 test draw;
- the panel and pilot institutions.

The list is drawn up only after classifier v3 is frozen, and is committed with a log recording every frame institution and why any was excluded. There are no backups: an institution that cannot be scored stays in the record as unscorable or structurally unscorable, with its outcome, under the v2 protocol's rules.

Because this lists every remaining institution, it uses up the 2019 frame. No later version of the tracker can be tested on an unused 2019-era institution; a later test needs a newer scoring year, or a fully prospective test, scored now and judged as closures occur.

## Phase 3: test scoring

Each v3 test institution is scored over the window ending in fiscal year 2019, under the v2 protocol's structural-reporting rule and minimum record, with the frozen v3 pipeline, once, at seed 7. The v2 test fitted every institution at three seeds; its two seed disagreements both concerned survivors and changed no measure, so a single fit is used here, which keeps the scoring of about four times as many institutions within a day of computing.

For each scored institution, the batch records its nineteen features, its classifier v3 probability and flag (the probability at or above the frozen for-profit cut for a for-profit institution, and at or above the frozen nonprofit cut for any other), its anchor inputs, anchored probability and anchored flag, its size-and-sector baseline probability and flag, the processor it ran on, and, for analysis only, the frozen classifier v2 coefficients applied to its v3-pipeline features. Every score is committed before any test outcome is looked up.

## Phase 4: comparator

The critical-slowing-down comparator is computed for every scored v3 test institution exactly as in the v2 test, and its flags are committed before any test outcome is looked up.

## Phase 5: outcomes, measures and verdicts

**Outcomes** follow the v2 protocol's outcome definition (primary coding and codings B and C) with the scoring year 2019 and the IPEDS header files from 2019 through the latest available, read with the corrected v2 reader and its reading check.

**Measures** are those of the v2 protocol: E, S, F, J, precision, closure rate and lift for scored institutions under the primary coding, with 95% Wilson intervals and a 95% percentile bootstrap interval for J (10,000 resamples, random seed 20261115). E_np and J_np are the same measures among scored public and private nonprofit institutions only.

**Minimum events.** The test is underpowered, and does not pass, unless E ≥ 10 and E_np ≥ 10.

**Revision triggers:**

- **R1 (no discrimination):** the lower bound of J's interval is at or below 0.
- **R2 (low sensitivity):** S < 0.50.
- **R3 (excess false alarms):** F > 0.30.
- **R4 (no advantage over the comparator):** the comparator's J is equal to or greater than classifier v3's J, over the scored institutions for which the comparator is computable.
- **R5 (no advantage over sector alone):** the J of flagging every for-profit institution and nothing else is equal to or greater than classifier v3's J, over all scored institutions.
- **R6 (no discrimination within the nonprofit sectors):** among scored public and private nonprofit institutions, the lower bound of classifier v3's J interval (10,000 resamples of those institutions, random seed 20261115) is at or below 0.

**Passing.** Classifier v3 passes if both minimums are met and none of R1 to R6 fires.

**Second verdict: do the tracker's own features add value beyond size and sector?** Among scored public and private nonprofit institutions, classifier v3's area under the ROC curve is compared with the size-and-sector baseline's, by a paired 95% percentile bootstrap of the difference (10,000 resamples of those institutions, random seed 20261116). If the interval's lower bound is above 0, the tracker's features are found to add value beyond size and sector; otherwise they are not shown to add value. If E_np < 10, this verdict is that the test is underpowered for it. The two models' J at their frozen cuts are reported beside it. This verdict does not change the first, and both are reported together, whichever way each comes out.

**Anchor sensor.** Two tests, neither of which changes a trigger or either verdict above:

- **Main test: does anchoring explain flagged survivors?** Among scored institutions flagged by classifier v3, the area under the ROC curve of the anchor capacity for survival, with a 95% percentile bootstrap interval (10,000 resamples, random seed 20261117). The anchor sensor passes if the lower bound is above 0.5. The test is underpowered unless at least 10 flagged institutions closed and at least 10 survived.
- **Second test: does the anchored flag beat the tracker alone?** Over all scored institutions, the J of the anchored flag minus the J of classifier v3's flag, with a paired 95% bootstrap interval. The anchored flag improves on the tracker if the lower bound is above 0.

Both are repeated under coding B, where a merger counts as survival, because a system can save a member by merging it. Reported, not scored: closure rates among flagged institutions with and without religious affiliation, HBCU, tribal and land-grant status, for-profit chain membership and nonprofit or public system membership.

**Further pre-specified analyses,** none of which changes a trigger or a verdict:

- the measures under codings B and C;
- S, F and J by sector;
- a paired bootstrap interval for classifier v3's J minus the J of flagging every for-profit institution;
- the frozen classifier v2 coefficients applied to the same institutions' v3-pipeline features, overall and among public and private nonprofit institutions (not the v2 pipeline's own scores, which these institutions do not have);
- the closure rates among unscorable and structurally unscorable institutions against scored ones, and bounds on S, F and J over all listed non-structural institutions, counting every unscorable institution first as flagged and then as not flagged;
- the flagged survivors, with their anchor capacity and anchored flag;
- the count and flag rate of scored institutions on each processor.

## Known properties carried over unchanged

The `debt_spike` feature takes extreme values (above 600,000 in absolute value) for four for-profit institutions of the 2014 development set, where its denominator is near zero, which compresses that feature after standardization in both classifier v2 and classifier v3. Clipping it was examined on the development data and lowered discrimination within the nonprofit sectors, so the feature is used as the pipeline produces it.

## Amendments

Before phase 3 begins, this protocol may be amended only to correct something that would otherwise prevent it from being carried out as written, and only on evidence that involves no v3 test outcome. Each amendment is recorded at the end of this file with its date, the phase it was made in, what it changed and the evidence for it. After phase 3 begins, nothing in this file changes except the addition of results, and any error in how a file is read is recorded as an erratum, as in the v2 protocol.
