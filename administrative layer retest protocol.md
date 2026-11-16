# Administrative layer retest protocol

Fixed before this analysis was run on any of its colleges. It tests the
administrative-layer hypothesis, with the corrections found on November 16,
on the colleges held back from the first test: the 987 scored v3 test
colleges. Their closure outcomes are already recorded in this repository
(data/v3/test outcomes.json), but the administrative-layer hypothesis has
never been examined on them. This is a pre-registered analysis of existing
outcomes, labeled exploratory; it changes no v3 verdict and does not use up
the prospective retest, which is judged on closures that have not yet
happened.

## Background

The first test (data/meta channel/administrative layer test.json, the 670
development colleges) found a thicker administrative layer going with more
resource debt and a higher research ratio, as predicted, but with less
closure, more adaptive capacity and more full-time faculty, against the
predictions. Exploring why (recorded in the to-do list, November 16) showed
those three reversals were largely wealth and sector composition: wealthier
colleges have both thicker administrative layers and more full-time faculty,
and close less. At equal size and wealth, a thicker layer still went with
more resource debt. The reading adopted: the administrative share is an
ambivalent signal, reflecting both the wealth needed to afford the layer
and a drain on it, so it must be read at equal wealth, sector by sector,
and jointly with the college's financial trajectory.

## Measures (fixed)

| Quantity | Definition | Source |
|---|---|---|
| Administrative share (primary: core; also broad) | `shares()` in `src/administrative layer.py`, full-time equivalents, fall 2018, or the latest earlier fall from 2012 with a value | data/meta channel/administrative layer.json |
| Resource debt, debt trend, adaptive capacity | delta_R_final, delta_R_trend, d_A_final from the two-channel rescoring (seed 7) | data/v3 reanalysis/test scores/ |
| Wealth | reserve_adequacy (log endowment per student) | same |
| Size | log of instructional staff headcount (full-time plus part-time), same fall as the share | data/meta channel/instructional staff share.json |
| Appropriations | f_approp, state and local appropriations as a share of expenses, 2019 cohort | data/v3/anchors.json |
| Full-time faculty share | full-time over full-time plus part-time instructional headcount, same fall | data/meta channel/instructional staff share.json |
| Closure | "closed or failed (primary)" | data/v3/test outcomes.json |

"Held constant" means a partial Spearman correlation: the ranks of both
variables are residualized on the ranks of the controls (size and wealth;
for public colleges also appropriations), and the residuals correlated.
Intervals are 95% bootstrap intervals (colleges resampled, 2,000
resamples, seed 20261116).

## Predictions (fixed)

1. **Debt.** At equal size and wealth, a thicker layer goes with more
   resource debt and a steeper debt trend: partial correlation above zero,
   for all colleges together (with sector as an added control) and within
   private nonprofit colleges.
2. **Closure.** At equal size and wealth, a thicker layer goes with more
   closure: partial correlation above zero, for all colleges together (with
   sector as an added control) and within each sector with at least 10
   closures (private nonprofit; for-profit). Public colleges have too few
   closures to test and are reported only.
3. **Joint reading.** Within each sector with at least 10 closures,
   colleges are split at the sector's median share (thin, thick) and at
   zero debt trend (flat or falling, rising). Rising debt is predicted to
   close more than flat debt among thick-layer colleges (wealth funding
   divergence) and among thin-layer colleges (starved). Reported as the
   difference in closure rates, rising minus flat, with bootstrap
   intervals.

Reported without prediction: the full-time faculty share and adaptive
capacity against the administrative share at equal size and wealth (and,
for public colleges, appropriations), by sector; and the same analyses for
the broad share.

## Reading the results

For each prediction: supported if the 95% interval lies entirely above
zero; contradicted if entirely below; not decided otherwise. Every result
is reported, whichever way it comes out.

## Steps

1. Commit this protocol with `src/administrative layer retest.py` and the
   workflow "meta channel 3 - retest the administrative layer on the held-out colleges"
   (`administrative_layer_retest.yml`).
2. Run the workflow once; it writes data/meta channel/administrative layer retest.json.
3. Report every result.
