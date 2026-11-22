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

## Amendment 1 (November 21, 2026, after the downloads and before any pass rate was parsed): what the source files allow

The downloads (data/item 22a/raw/downloads.json) show what each source contains, read for layout only. Four decisions follow.

1. **Oklahoma's threshold.** The Oklahoma Board of Nursing's tables give each program's first-time pass rate for every calendar year, but its count of first-time candidates only for the newest year of each edition (2022, 2023 and 2025 in the editions found). The threshold of section 2 (at least 20 first-time test takers) is therefore applied, for Oklahoma only, to the institution's IPEDS first-major completions in registered nursing (the CIP codes of section 4) at the program's award level in the exam year: at least 20. Completions stand in for test takers because nearly every completer sits the exam; a program whose completions cannot be matched is listed and left out.
2. **Several campuses under one unit ID.** Where a board lists campuses separately and IPEDS reports them under one unit ID, the campuses are combined to the unit ID, the level of the outcome. For Indiana, Texas and Florida, passed and tested counts are summed, which gives the unit ID's true rate. For Oklahoma, which gives rates without counts in the years tested, the campuses' rates are averaged without weights, the only combination its figures allow.
3. **Florida's annual counts.** Florida's figures are the board's fourth-quarter NCSBN program reports (Report 4), which give delivered and passed counts for each quarter of the exam year. A program's annual counts are the sums of its four quarterly Total rows. The reports for exam years 2016 to 2019 are added to the downloader under each naming pattern the board has used, beside the 2020 report already downloaded.
4. **Pharmacy.** NABP's reports by school that could be found cover graduates of 2020 to 2025 only (the editions for 2020 to 2022, 2021 to 2023 and 2023 to 2025); its ten-year report gives national rates only. The test of section 5 needs graduating classes of 2020 or earlier with development years before them, since the newest completions year is 2024. If earlier editions by school (2017 to 2019, 2018 to 2020 or 2019 to 2021 graduates) are placed by hand in data/item 22a/raw/ before the test runs, the pharmacy test runs as specified. Otherwise pharmacy becomes a prospective test: the flags for base years 2022 onward, from graduating classes 2021 onward, are computed and committed before IPEDS releases the completions year that judges them (2025 completions for base year 2022), with the outcome of section 4 unchanged, and judged as each release arrives. Which of the two applies is recorded in the results. NABP notes that graduation data before 2021 were self-reported and are not guaranteed; that is recorded as a limitation of any class before 2021.

Nothing else in the protocol changes. No pass rate had been parsed, and no completions count computed for any program, when this amendment was written.

