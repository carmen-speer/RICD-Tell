# Lifetime-earnings protocol (item 13): professions and trades

Fixed November 20, 2026, before any earnings, wage or debt value is read. Separate from the closure model: nothing here is tested against closure, and nothing here enters a tracker.

## 1. Question

Across fields of study and credential levels, how does what graduates earn early compare with what their occupations pay across a career, and with what they borrowed, for the trades against the professions?

## 2. Sources

- **Graduates' earnings and debt.** College Scorecard, the most recent cohorts field-of-study file (Most-Recent-Cohorts-Field-of-Study.csv) in the repository's release asset scorecard-raw-data-2026-11-02 (SHA-256 as fixed in "sampling protocol.md"). Earnings: the national medians for each field (4-digit CIP) and credential level at 1, 5 and 7 years after completion (EARN_MDN_1YR_NAT, EARN_MDN_5YR_NAT, EARN_MDN_7YR_NAT), with the 25th and 75th percentiles at 5 years. Debt: each program's median debt at completion (DEBT_ALL_STGP_EVAL_MDN), combined nationally as the median of program medians weighted by their borrower counts (DEBT_ALL_STGP_EVAL_N), an approximation stated as such.
- **What occupations pay.** BLS Occupational Employment and Wage Statistics, national file, May 2024 (oesm24nat.zip): for each detailed occupation, employment (TOT_EMP) and the annual wage median, 25th and 90th percentiles (A_MEDIAN, A_PCT25, A_PCT90). Wages BLS top-codes (shown as #) are set to the top-code value stated in the BLS technical notes for that release ($239,200 for May 2024) and flagged; every result that uses one is a lower bound, and each comparison is also reported without top-coded occupations.
- **The link.** The NCES–BLS CIP 2020 to SOC 2018 crosswalk (CIP2020_SOC2018_Crosswalk.xlsx). Each 4-digit field is linked to every detailed occupation its 6-digit codes map to; the field's occupational wages are the employment-weighted means of those occupations' values. Codes with no occupational match (SOC 99-9999) are left out, and fields with none are listed. The crosswalk is conceptual (what a program prepares for), not a record of where graduates work; stated as a limitation.
- If the BLS or NCES site refuses a download from GitHub Actions, the file is downloaded once by hand and committed to data/item 13/, and the script reads it from there, recording which copy it used.

## 3. Measures, for each field and credential level

- **Early position:** graduates' median earnings 5 years out / the linked occupations' median wage.
- **Occupational ladder:** the occupations' 90th / 25th percentile wage. This is a cross-section of all workers in the occupation, not a career followed over time; it stands in for the lifetime range and mixes experience with differences between workers, stated as a limitation.
- **Graduates' growth:** median earnings 7 years out / 1 year out (the same national cohorts' series as Scorecard reports it).
- **Payoff to cost:** the occupations' median wage / median debt; and early payoff, earnings 5 years out / median debt.

## 4. Sectors and prediction

- **Trades:** undergraduate certificates and associate degrees (Scorecard credential levels 1 and 2) in CIP families 12 (personal and culinary services), 46 (construction trades), 47 (mechanic and repair), 48 (precision production) and 49 (transportation and materials moving).
- **Professions:** first professional degrees (credential level 7; the credential labels are recorded from the file).
- Every field and credential level is also reported in a table by credential level, for information.
- **Prediction (fixed before any value is read):** trades start closer to their occupations' median and climb a shorter ladder; professions start further below and climb further. Three comparisons of the sector medians across field-and-credential units, professions minus trades, each with a 95% bootstrap interval (2,000 resamples of units within sector, fixed seed): (P1) early position lower for professions; (P2) occupational ladder higher for professions; (P3) graduates' growth higher for professions. Each is supported if its interval excludes zero in the predicted direction, "in the predicted direction" if only the point estimate is, and not supported otherwise. Payoff to cost is reported by sector without a prediction.
- Units without a value for a measure are left out of that measure only, and the counts are reported.

## 5. Records

data/item 13/lifetime earnings.json (every unit's values and links, the files and their sources) and data/item 13/lifetime earnings test.json (the comparisons), committed by the workflow item13_lifetime_earnings.yml.
