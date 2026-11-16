# Transfer test protocol

Fixed before any outcome data for this test was downloaded or looked at.
The outcomes already exist (they are published by the Texas Higher Education
Coordinating Board), so this is a pre-registered analysis of existing data,
labeled exploratory: it can support or contradict the hypothesis, but it is
not a blind test of the tracker. It changes nothing in classifier v3, the
reanalysis or any frozen file.

## Hypothesis

Contingent (part-time) instructors are paid only for class hours, with
preparation and conferences unpaid, and can lose their jobs to a single
unprovable complaint by not being rehired, while tenured faculty cannot.
Teaching under those conditions is simplified to match the wage and to
avoid complaints: easier assignments, fewer demanding topics, and passing
students who might complain. Community colleges that rely heavily on
contingent instructors therefore pass on students less prepared than their
grades say. Those students' outcomes after transfer, which no
community-college instructor grades, should be worse.

**Prediction.** Within the same receiving Texas public university, students
transferring from community colleges with a higher contingent share of
instructional staff:

1. more often have a first-year university GPA below 2.0;
2. more often are not enrolled at that university the following fall;
3. less often earn a bachelor's degree.

## Data

| Quantity | Source | Unit |
|---|---|---|
| Contingent share | IPEDS staffing files (EAP), "Instructional staff, total": part-time headcount divided by full-time plus part-time headcount; already measured in `data/meta channel/instructional staff share.json` | community college, fall year |
| First-year GPA below 2.0; enrolled the following fall | THECB, "Academic Performance of 2-Year College Transfer Students at Texas Public Universities" (one report per two-year college per fall transfer cohort) | pair (two-year college, university), fall transfer cohort |
| Bachelor's completion by sending college | THECB accountability system, two-year colleges: six-year graduation rate, "Bachelor's or Above" line, for the entering fall cohort | two-year college, entering cohort |
| Bachelor's completion by receiving university | THECB Transfer Report: four-year completion rate of community-college transfer juniors and of non-transfer juniors | university, junior cohort |
| Student population | College Scorecard, PCTPELL (share of undergraduates receiving Pell grants), from the dated raw-data file this repository already keeps (release "scorecard-raw-data-2026-11-02", SHA-256 fixed in `src/build_scorecard_compact.py`) | community college, year |

Contingent share for a fall transfer cohort Y is the mean of the community
college's share in falls Y−2 and Y−1, the two falls before transfer.
Community colleges with fewer than 25 instructional staff in either fall
are left out, because their shares jump by chance (see the meta-channel
check). Pairs THECB groups as "Other Public 4-Yr Institutions" (fewer than
5 transfers) are left out. Every two-year college and every fall cohort in
the THECB reports is used; none is chosen by hand.

THECB names are matched to IPEDS unit IDs by name, in a mapping file
committed with the data; every unmatched name is listed, never guessed.

## Analysis

All analyses use bootstrap intervals that resample community colleges
(clusters), 2,000 resamples, seed 20261116.

**Level 1, pairs (primary).** For each outcome (share with first-year GPA
below 2.0; share not enrolled the following fall), the slope of the pair's
outcome share on its community college's contingent share, with the
receiving university and the cohort year held fixed: both are centered
within each university-and-cohort group, weighted by the pair's number of
transfers, and the slope is the weighted least-squares slope of the
centered values. Pell share is included the same way, as a centered
covariate, so colleges serving similar students are compared; no direction
is assumed for it, and its own slope is reported, not predicted. The same
slopes without Pell share, and within each third of community colleges by
Pell share, are reported as checks.

**Level 2, sending colleges.** Spearman correlation between a community
college's six-year bachelor's-or-above rate for an entering cohort and its
contingent share in that cohort's first two falls; and the partial
correlation given Pell share. Predicted below zero.

**Level 3, receiving universities.** For each university and junior
cohort, the transfer graduation gap (transfer juniors' four-year completion
rate minus non-transfer juniors'), which holds the university's own
standards constant, against the transfer-weighted mean contingent share of
the community colleges that sent it students (from the level 1 data, same
cohort or nearest). Spearman correlation; predicted below zero.

**Reading the results.** For each prediction: supported if the 95%
interval lies entirely on the predicted side of zero; contradicted if it
lies entirely on the other side; not decided otherwise. Every result is
reported, whichever way it comes out. Level 1 is the primary result;
levels 2 and 3 are supporting checks with fewer independent units.

## Steps

1. Commit this protocol with `src/transfer sources.py` and the workflow
   "transfer test 1 - list the Texas transfer reports"
   (`transfer_test_sources.yml`), which lists what the THECB sites serve
   and writes no outcome.
2. From that listing, build the download, parsing and analysis code, test
   it offline on synthetic files, and commit it before it runs.
3. Run it once; report every result.

## Amendment 1 (November 16, before any analysis data was downloaded; disclosed)

Step 1 found where and how the reports are served; this amendment fits the
analysis to them. Only one sample report per form was read, to write the
parser (Northeast Lakeview College: academic performance, fall 2023; and
graduation, fall 2020); no other outcome had been seen.

1. **Source.** The per-pair reports are served as PDFs by the
   Coordinating Board's "Transfer Students Success" page
   (apps.highered.texas.gov), one per two-year college per fall cohort:
   academic performance (fall cohorts 2014 to 2024 used; earlier cohorts
   have no staffing data two falls before transfer) and graduation (fall
   cohorts 2014 to 2021, the latest offered). Page 1 of each performance
   report, which splits every transfer exactly once (with or without
   developmental education), is the table used.
2. **Graduation at level 1.** The graduation reports give, for each pair,
   how many of a fall cohort's transfers graduated within four years from a
   Texas public or independent institution. Prediction 3 (less often
   graduate) is therefore tested at level 1 as well, as the share not
   graduated, with the same analysis as the other two outcomes.
3. **Level 2.** The graduation reports' institution totals (each
   community college's transfers, and how many graduated) replace the
   accountability system's whole-cohort bachelor's rate: they measure what
   the hypothesis is about, the transfers' own completion, and the
   accountability system's download route was not established. Predicted
   below zero, as before.
4. **Level 3 deferred.** The receiving universities' junior-cohort tables
   are in the annual Transfer Report PDFs; level 3 will be built and
   reported separately, under this protocol, without changing levels 1
   and 2.
5. **Details fixed.** The first-year GPA share is taken over transfers
   with a known GPA. Colleges are matched by FICE code, which is the first
   six digits of the IPEDS OPEID; every IPEDS unit with that OPEID6 in a
   fall's header file is assigned to the college and their staff counts
   summed. Pell share is the mean PCTPELL of those units in the College
   Scorecard files for the same two falls. Reports whose tables do not add
   up are left out and listed, never repaired.
6. **Run.** `src/transfer data.py` downloads and parses the reports and
   assembles the inputs; `src/transfer test.py` runs the analysis; both are
   run by the workflow "transfer test 2 - download the Texas reports and run the test"
   (`transfer_test_run.yml`), which commits data/transfer test/reports.json,
   inputs.json and results.json.
