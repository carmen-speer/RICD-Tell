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
