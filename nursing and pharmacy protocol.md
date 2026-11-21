# Nursing and pharmacy protocol (item 22a): does failure show in licensure outcomes before a program shrinks?

Fixed November 21, 2026, after the field check (data/item 22a/field check.json: sources and IPEDS completions fields only) and before any pass rate is downloaded or any completions count is computed for a program.

## 1. Question and prediction

The law-school test (channel selection protocol.md, Amendment 14) found that law schools in the bottom decile on bar passage or employment shrank severely far more often than other schools (test period 2017 to 2022: rate ratio 10.7, 95% interval 3.8 to 38.6; AUC 0.81). Item 22a asks whether the same holds in other licensed fields: in programs whose graduates sit a national licensing exam, does failure show plainly in the outcome channel before the end? The test copies Amendment 14 wherever the fields allow, so the three results can be read side by side.

**Prediction.** Programs in the bottom decile on first-time licensure pass rates shrink severely more often than other programs, in nursing and in pharmacy separately.

## 2. Units

- **Nursing (NCLEX-RN).** Every pre-licensure registered-nursing program in the four pilot states of channel selection protocol.md section 5 (Oklahoma, Indiana, Texas, Florida), by institution and award level (associate or bachelor's), with at least 20 first-time test takers in the base year's exam year. Practical-nursing (NCLEX-PN) programs are reported separately, report-only.
- **Pharmacy (NAPLEX).** Every Doctor of Pharmacy program in NABP's reports by school with at least 25 first-time candidates in the base year's graduating class.
- **Matching.** Each program is matched to its IPEDS unit ID by normalized name and state, then by a fixed hand list (data/item 22a/name crosswalk.csv), as in item 15b. A program that cannot be matched is listed and left out, never matched by its values.

## 3. Predictor (as in Amendment 8)

Flagged in year y if the program was in the bottom decile on first-time pass rate for exam year (nursing) or graduating class (pharmacy) y − 1, the figure published by year y. Nursing deciles are taken within state, award level and year, since each board reports on its own calendar and programs differ by level; pharmacy deciles are national. A continuous score is also reported: 100 minus the program's percentile. Texas changed its exam year from October to September (to 2015) to the calendar year; years are aligned to the year in which most of the exam window falls, and each changed year is flagged.

## 4. Outcome (as in Amendment 14)

**Completions.** IPEDS Completions (C files), first majors, at the program's award level. Nursing uses CIP 51.3801 (registered nursing) from 2010 and its predecessor 51.1601 before 2010; practical nursing uses 51.3901 from 2010 and 51.1613 before. Pharmacy uses 51.2001 in every year. The field check found these codes in every year 2008 to 2024; the 2010 crosswalk is applied by code, and nothing else.

**Severe shrinkage over three years:** the program's completions in y + 3 divided by its completions in y, relative to the same ratio for all programs of the same field and award level reporting both years, is 0.6 or lower; or the institution closed after y and no later than y + 3 (the closure rule of ending types protocol.md). A year with no completions counts as 0. A program missing in y + 3 for any other reason (merger, a change of unit ID, a reporting gap) is left out of that year, not counted as shrinking. Dividing by the national ratio keeps field-wide swings from counting as a program's own collapse.

**Lag, report-only.** Completions trail admissions by the length of the program, so a program that cuts admissions in y + 1 may not show it in completions until y + 3 to y + 5. The same outcome over four years (y + 4) is reported beside the three-year result; only the three-year result decides the verdict, so the test matches Amendment 14.

## 5. Development and test

The last completions year read in the field check is 2024, so the base years end at 2021. Nursing: development base years 2015 to 2017 (Florida from 2017), test base years 2018 to 2021. Pharmacy: the same split over the years the NABP reports cover, with the earliest year recorded in the results. Development is reported only, since nothing is fitted.

Reported for each field, period and (for nursing) state: shrinkage rates of flagged and other program-years, their ratio with a 95% bootstrap interval resampling programs (2,000 resamples, seed 20261121), and the AUC of the continuous score with the same interval; and the rate ratio within terciles of program size. **Verdict, for nursing and pharmacy separately:** supported if the test-period rate ratio's interval is above 1; in the predicted direction if only its point estimate is; not supported otherwise.

## 6. Limits of the design

Four nursing states are not the nation, and each board reports differently; the within-state deciles keep state reporting differences out of the flag but do not make the states representative. Completions measure program size with a lag (section 4). Programs whose institution reports several campuses under one unit ID are read at the unit ID, the level IPEDS reports.

## 7. Records

Downloads and parsing: src/item 22a downloads.py, with each source file's URL and sha256 recorded, and files that refuse automated download placed by hand in data/item 22a/raw/ and recorded the same way. Test: src/item 22a test.py. Workflow item22a_test.yml ("item 22a - nursing and pharmacy test"). Results in data/item 22a/results.json, with the program-year table, the name crosswalk and the list of unmatched programs.
