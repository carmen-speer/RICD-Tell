# Ending-types protocol (item 15): drift-type and shock-type approaches to collapse

Fixed November 20, 2026, before any finance, enrollment or closure value is read. Exploratory: the rule is fixed here, measured on two named colleges and on every documented closure since 2005, then frozen for the retest. Nothing here enters a tracker until the retest protocol says so.

## 1. Question

Was a college's approach to collapse drift-type (a slow slide) or shock-type (a single large loss) in the sense of Spine Definition 10.3a.6? Measured first on Sweet Briar College and the University of Phoenix, then on every documented closure since 2005.

## 2. Measures, for each college and fiscal year t

- **Total work** W(t): total expenses (IPEDS finance).
- **Exchange** E_exch(t): net tuition and fees only, what students actually pay.
- **Exchange base** N(t): 12-month full-time-equivalent enrollment. **Per-partner exchange** ē(t) = E_exch(t) / N(t).
- **Coverage** c(t) = W(t) / E_exch(t).
- **Anchor capacity** A(t) (Spine Definition 10.3a.7), in dollars of outside support per year:
  - private nonprofit: private gifts and contributions plus endowment spending for operations: the reported spending distribution from fiscal 2020; before then an estimate, 4.5% of the beginning-of-year endowment value, labelled an estimate on every value it touches;
  - public: federal, state and local appropriations plus gifts (matching src/v3_anchors.py). Public endowments are left out: the public form has no spending distribution in any year, and many public endowments are held by separate foundations, so reported values are incomplete (a stated limitation);
  - for-profit: not observable, recorded as missing, never as zero (an extractive owner's negative anchor is invisible in IPEDS).
- **Gap coverage** g(t) = W(t) / (E_exch(t) + A(t)), defined where A is observable.

Exact IPEDS fields for each measure, form and year: section 7.

## 3. States and the anchored share

Each college-year is in one of three states: **self-covering** (c ≤ 1); **held up by anchors** (c > 1 and g ≤ 1); **short beyond its anchors** (g > 1), the only state counted as true collapse risk. Reported alongside: the **anchored share** A / (W − E_exch) for every year with c > 1. This is the first working version of the anchor-quantification sensor (future-projects/Anchor-Quantification Sensor - Seed Note.md).

## 4. The window

- **Primary (crossing into collapse risk).** From the first available year (fiscal 2005) to the first year g(t) > 1. For-profits, with no observable anchor, use the first year c(t) > 1 instead, and are labelled as using the coverage crossing.
- **Check (coverage, reported alongside).** From fiscal 2005 to the first year c(t) > 1; for a college already past c = 1 in fiscal 2005, from fiscal 2005 to its closure year.
- A college that closed without ever crossing g = 1 is reported as its own group (closed without crossing), never dropped.
- **Sweet Briar** ends at fiscal 2015, the year of the closure announcement; what followed is the rescue, not part of the approach.
- **Phoenix** has not closed: its approach to date is reported (the long enrollment decline against the campus-closure steps), not a collapse type.
- Every crossing that falls in a year using the pre-2020 endowment estimate is flagged.

## 5. Decomposition and the rule

- Over the window [t₀, t*], the change in log g (primary) or log c (check) is the sum of its year-to-year changes (Proposition 10.3a.1). Since log c = log W − log N − log ē, and log g adds the anchor term, each year's change can be split into its parts.
- **A jump** is a year whose fall in log N (enrollment), or, in the primary measure, whose fall in log A (anchors), lies beyond three robust standard deviations of that college's own year-to-year changes in that quantity (robust standard deviation = 1.4826 × the median absolute deviation from the median). A state budget cut or a collapse in gifts can therefore be a shock.
- **Jump part:** the sum of the year-to-year changes in the ratio in jump years. **Drift part:** the sum over all other years.
- **Shock-type** if a single jump year accounts for more than half of the window's change. **Drift-type** if the drift part does.
- **Mixed** if neither holds (for example, two jumps each under half and a drift part under half); reported as its own group. Jumps are never added together to reach a shock-type label, since shock-type means a single loss.
- **Too short to classify** if the college has fewer than five year-to-year changes (six years of data) in the quantity being judged, since its own robust standard deviation is then not meaningful; reported, never dropped.

## 6. Closures since 2005

Degree-granting colleges with a documented closure in the IPEDS header files, 2005 onward, using the tracker's own closure coding. Chain campuses folded into another report are separated from real closures with the check built for item 16 (extractive anchor test.py) and are not counted as closures. **Gap, to be written up in the results and README:** this leaves out the colleges that disappear from the files with no closure record (487 in the openings-against-closures count), many of them for-profit campuses, so the for-profit rate of each ending type is a count of documented closures only.

## 7. Fields

Checked against the data dictionaries for every year (data/ending types/field check.json, commit a9cc37a). Finance file Fyyzz (for example F0405) is fiscal year 20zz (July to June) and is paired with the 12-month enrollment file EFIA of the same year (F0405 with EFIA2005). Finance runs fiscal 2005 to 2024 (F2425 not yet released when checked).

| Measure | Public (F1A) | Private nonprofit (F2) | For-profit (F3) |
|---|---|---|---|
| Net tuition and fees, E_exch | F1B01 (after discounts and allowances) | F2D01 (net of allowances) | F3D01 |
| Total expenses, W | F1D02 | F2B02 | F3B02 (F3D09 total revenues only where F3B02 is missing, as in src/v3_anchors.py, flagged) |
| Appropriations | F1B10 + F1B11 + F1B12 | F2D02 + F2D03 + F2D04 | not used (anchor not observable) |
| Gifts | F1B16 | F2D08A + F2D09 from fiscal 2008; fiscal 2005 to 2007, F2D08 (gifts, grants and contracts combined) + F2D09, every value flagged as including grants and contracts, and any crossing it could affect flagged | not used |
| Endowment spending | left out (section 2) | F2H03C (spending distribution) from fiscal 2020; before then 0.045 × F2H01 (beginning-of-year value), flagged as an estimate | not used |

Enrollment N: the IPEDS-estimated 12-month FTE, EFTEUG + EFTEGD, computed by IPEDS from credit hours the same way for every college and year. The college-reported counts (FTEUG, FTEGD, and FTEDPP from 2012) are not used: they changed shape in 2012 and are computed differently across colleges, which could look like a jump.

A value IPEDS reports as missing or imputed-missing is left missing; a year missing W, E_exch or N is not counted as a year-to-year change. The change across such a gap is reported as a separate gap part, counted in neither the drift nor the jump part, while the shares in section 5 remain shares of the window's whole change. A college whose gap part exceeds half the change is labelled too short to classify.

## 8. Records

Script src/ending types.py; workflow ending_types.yml ("item 15 - measure ending types"); outputs in data/ending types/: Sweet Briar and Phoenix series and decompositions, the classification of every closure (primary and check), the three-state series and anchored share for every college measured, and a results file. The field check is src/ending types field check.py (ending_types_field_check.yml).

## 9. Afterwards (not part of this protocol)

The anchor-and-voice prediction (to-do item 15, November 18) needs case-level information (whether a rescue or reorganization followed each ending) that IPEDS does not hold; it is done afterwards as case studies, using the types fixed here.
