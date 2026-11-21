# Anchor-and-voice protocol (item 15b): how anchors and aligned voice shape the end of a collapse

Fixed November 21, 2026, before any case is collected, any voice record is read, or any outcome is tabulated against ending type, anchoring or voice. Exploratory: outcomes are public and known in general, so this is a case-study test of item 15's prediction, not a blind one. The rule is fixed here, applied to every case, then frozen for the retest. Nothing here enters a tracker until the retest protocol says so.

## 1. Question and prediction

Item 15 (fixed November 18, before any ending outcome was looked at) predicts that how a collapse ends depends on its type, on anchoring at onset, and on whether voice stays aligned with the operational core during the slide:

- **P1.** Shock-type collapse with anchors ends more often in rescue or reorganization than drift-type collapse without anchors, which ends more often in closure.
- **P2.** Among drift-type cases, aligned voice during the slide is followed more often by rescue or reorganization; normalization or silence is followed more often by closure.
- **P3 (outsider check, report-only).** If anchors respond to salience, gifts and appropriations rise after a shock and stay flat through a drift of the same financial size.

The mechanism (Spine Definitions 10.3a.6 to 10.3a.8): a shock is easy to see, so potential anchors activate and the point of no return moves; a drift is normalized inside (the official layer in denial) and outside (decline read as the normal state of things), so the anchors never activate before Δ_PNR ≤ 0. Aligned metamessengers resist the internal normalization and recruit anchors before the end.

## 2. Cases

**Rescued and reorganized cases.** Every public or private nonprofit degree-granting college in Higher Ed Dive's tracker of closings, mergers and acquisitions (2016 to the present) whose entry, or the reporting it links to, records any of the following, read from the entry as of the collection date:

- an announced closure that was reversed (the college still operating under its own name);
- a merger or acquisition in which the college's campus still operates, where the college was in the held-up-by-anchors or short-beyond-its-anchors state (ending types protocol §3) in at least one of the three fiscal years before the announcement. This keeps mergers of distressed colleges and leaves out mergers of healthy ones, using only the frozen measure, never the outcome.

**Reversed closures from a second list.** The tracker may record a reversed closure only as an open college, or leave it out. Reversed closures are therefore also taken from two named second lists, Bryan Alexander's surveys of closures, mergers and cuts (Future Trends Forum blog) and Inside Higher Ed's yearly closure and merger lists, read for every announced closure later reversed, 2016 to the present. Each case's source is recorded.

Sweet Briar College is added as a named case (closure announced March 2015, reversed June 2015), flagged as outside the tracker's window. Other reversed closures before 2016 may be added only from a published list named in the results, never one by one.

**Matched closures.** For each rescued or reorganized case, two documented closures from data/ending types/closures.csv, drawn without replacement by src/anchor and voice.py with seed 20261121 before any voice record is read: same sector; a closure classified on the same measure (primary, else check); nearest in 12-month FTE at onset (section 3), then nearest in onset year. The draw takes closures of every ending type, so drift and shock closures both enter; P1's drift-without-anchors cell is filled from them as they fall. For-profit closures are left out of the matched sample, since their anchor is not observable (ending types protocol §2) and the tracker lists only public and nonprofit colleges.

**Ending type of each rescued case.** Rescued and reorganized colleges are not in closures.csv. Their ending type is measured by the frozen rule of ending types protocol.md (including Amendments 1 to 3), with the window ending at the fiscal year before the announcement in place of the closure year. No setting of that rule is changed.

## 3. Onset and anchoring

**Onset year** t_on: the end of the college's ending-type window, that is, its crossing year on the primary measure (first g > 1); else its crossing year on the check measure (first c > 1); else, for a college past both crossings at the start or never crossing, the last fiscal year before its announcement. The rule used is recorded for each case.

**Anchored at onset:** the anchored share A / (W − E_exch − O) in t_on (ending types protocol §3 and Amendment 2), compared with the median anchored share of all colleges of the same sector in the same fiscal year with c > 1. The frozen run (data/ending types/) measured only closures and the named cases, so src/anchor and voice.py computes the anchored share for every college in the IPEDS finance files with the frozen rule's own code and settings, unchanged. At or above the median: anchored; below: unanchored. The comparison group comes from every college, not the cases, so the split is fixed before outcomes are read. A case with no observable anchor or with c ≤ 1 in t_on is reported as unclassified on anchoring, never dropped.

## 4. Outcomes

Read from the tracker entry and the reporting it links to, as of the collection date:

- **Rescue:** the closure was reversed, or the college survives under its own name with new support;
- **Reorganization:** merger or acquisition, campus still operating;
- **Closure:** the campus ends, including through a teach-out or a merger that closes the campus.

## 5. Voice

**Window.** Voice is read in two windows: **during the slide**, from t_on to the day before the first public announcement of closure, merger or crisis; and **after the announcement**, the first twelve months. Only the first window enters P2. The second is report-only and measures the speed of response (the credibility-decay refinement of item 15).

**Aligned voice** (insiders or outside stakeholders publicly naming the institution's distress and seeking a remedy): alumni or donor campaigns; faculty or staff votes of no confidence citing finances or governance; AAUP censures (Amendment 15's campus rule for system censures); public fundraising appeals; lawsuits by faculty, students, alumni or donors challenging a closure or merger; trustee or official dissent made public. Each event is recorded with its date, actor, source and link.

**Normalization or silence:** no aligned voice event found in the first window under the search procedure below. A college whose official statements in the window describe it as sound while its g or c is rising is labelled normalization; with no statements either way, silence. P2 counts both together.

**Search procedure, fixed for every case.** Sources: the AAUP censure list; the college's student newspaper archive where online; Inside Higher Ed; Higher Ed Dive; the Chronicle of Higher Education where reachable; the main local newspaper; CourtListener for lawsuits naming the college. Terms: the college's name with each of "alumni", "no confidence", "censure", "lawsuit", "save", "petition", "fundraising" and "deficit". Every search is logged with its date and result count, including searches that find nothing, so silence is a record, not an assumption. Voice events are recorded before the outcome column of the case table is filled in.

## 6. Analysis

- **P1:** the two-by-two of ending type (shock against drift) by anchoring (anchored against unanchored), with each cell's shares of rescue, reorganization and closure. Supported if shock-with-anchors has the highest rescue-or-reorganization share and drift-without-anchors the highest closure share.
- **P2:** among drift-type cases, rescue-or-reorganization share with aligned voice against without, with Fisher's exact test and an exact 95% interval for each share.
- **P3:** for every case, gifts and appropriations (ending types protocol §7 fields) in the two fiscal years after the announcement against the two before, by ending type, report-only.
- Mixed, too-short and unclassified cases are reported in their own rows, never dropped.
- Small counts are expected; every share is reported with its count and interval, and the cases are described individually.

## 7. Limits of the design

Outcomes are known and news reporting often mentions them, so voice coding cannot be blind; recording voice events before the outcome column and logging every search keeps the coding auditable. Higher Ed Dive lists public and nonprofit colleges from 2016 and records major events, so smaller reversals may be missing. Mergers are read through the frozen financial states, which depend on IPEDS reporting in the years before.

## 8. Records

Script src/anchor and voice.py (draws the matched sample, measures the rescued cases' ending types, onset and anchoring); workflow anchor_and_voice.yml ("item 15b - anchor and voice cases"); case research recorded in data/anchor and voice/cases.csv (one row per case: identifiers, ending type, onset rule and year, anchored share and sector median, voice events, outcome) and data/anchor and voice/search log.csv; results in data/anchor and voice/results.json.

## Amendment 1 (November 21, 2026, at case collection, before any case was classified or any voice record read): pending outcomes, the tracker's coverage, acquirers

**What collection showed.** Higher Ed Dive's live tracker now shows 100 spotlighted events, January 2020 to November 2026, not the full list since 2016; the 2016 to 2018 table survives in a reprint dated November 20, 2018 (cappsonline.org), and the Internet Archive's copies of the page do not hold the table, which the page drew with a script. No list covering December 2018 to December 2019 was found. The tracker records no reversed closures: every entry ends in a closure or a merger, acquisition, consolidation or affiliation. Several outcomes were not yet final on the collection date (deals awaiting approval; closures dated 2026 or 2027).

**The changes.** (1) The tracker's case universe is the 2018 reprint and the live spotlight list together, both recorded in data/anchor and voice/tracker entries.csv with their source and date. The December 2018 to December 2019 gap is a stated limitation, and is filled only from a published list named in the results. (2) A case whose outcome is not final on the collection date is listed as **pending**, kept out of the P1 and P2 counts, and given its outcome when the deal closes or the campus ends; announced outcomes are never counted in advance, since deals fall through (Medaille, Marymount California and the San Francisco Art Institute each ended in closure after a failed merger). (3) In a merger or acquisition, only the absorbed or acquired college is a case; the acquiring partner's row is dropped. Everything else is unchanged.

## Amendment 2 (November 21, 2026, at case collection, before any case was classified or any voice record read): lasting and temporary rescues; the search as a completeness check

**What collection showed.** Most reversed closures found so far did not last: the college announced a closure, reversed it, and closed for good a few years later (Dowling College, reversed and closed in 2016; the San Francisco Art Institute, reversed in 2020 after $4 million in gifts, closed in 2022; Iowa Wesleyan, kept open in 2018, closed in 2023; Northland College, kept open in 2024 under a refocused model, closed in 2025). Read as of the collection date, each would be a plain closure, losing the reset attempt that item 15's prediction turns on (drift without anchors ends in closure with no reset attempt on the record). These cases were found by a general search, not from the two named lists.

**The changes.** (1) The rescue outcome is split in two. **Lasting rescue:** the closure was reversed and the college is still open on the collection date, at least three years after the reversal. **Rescue attempt, then closure:** the closure was reversed and the college closed later. A reversal less than three years before the collection date is pending (Amendment 1). Both count as a reset attempt on the record. In P1 and P2 only a lasting rescue counts as rescue; a rescue attempt that ended in closure counts as closure, and the two are compared directly in a report-only row: anchoring at onset, the voice record and the timing of the rescue against the onset year, under the prediction that lasting rescues come mostly from anchoring at onset and temporary ones from anchors that came after the point of no return (Δ_PNR ≤ 0, Spine Definition 10.3a.8). (2) Bryan Alexander's surveys and Inside Higher Ed's yearly lists remain the source of record for reversed closures. A general web search is run as a completeness check, and any case it finds that the named lists miss is added and flagged as found by search, so a reader can rerun the result without them. Everything else is unchanged.

## Amendment 3 (November 21, 2026, at case collection, before any case was classified or any voice record read): near-closure defined

**What collection showed.** Several colleges in the rescue group never announced a closure outright: each faced a public condition it had to meet or close (Bennett College's accreditation loss and fundraising deadline in 2019; Hampshire College's 2019 crisis; Birmingham-Southern College's 2023 vote; Northland College's 2024 appeal for $12 million). Item 15b names near-closures as cases but did not define them.

**The change.** A **near-closure** is a public statement, by the college itself or by its accreditor or state regulator, that the college would close, lose accreditation or stop operating unless a stated condition was met (a fundraising target, an appeal, a partner, a loan). Its date is the date of that statement, and it stands in for the announcement date wherever the protocol uses one (the end of the ending-type window, the onset fallback, the voice windows). Reports of trouble without such a statement do not qualify. Every case's qualifying statement is recorded with its source. Everything else is unchanged.

## Amendment 4 (November 21, 2026, before the measuring run): onset for the matched closures; one reading of the window end

**What building the script showed.** IPEDS records no announcement date for a closure, so the onset fallback of section 3 (the last fiscal year before the announcement) cannot be read for the matched closures, and a closure already past both crossings in its first year with data would have no onset and could not be matched. Separately, the item-15 run ended Sweet Briar's window at fiscal 2015, the fiscal year containing the March 2015 announcement, while section 2 here ends every case's window at the fiscal year before the announcement.

**The changes.** (1) For a matched closure, the onset fallback is the end of its item-15 window: its closure year in the header files, capped at the last finance year (fiscal 2024), the same end point item 15 froze. (2) Every case, Sweet Briar included, ends its window at the last fiscal year that ended before the announcement (or near-closure statement): for a date from July to December, the fiscal year ending that June; for January to June, the fiscal year ending the June before. Sweet Briar's window here therefore ends at fiscal 2014; item 15's own Sweet Briar result is unchanged. Where only a year is recorded, the fiscal year ending the June before that year is used; an entry listed as TBD in the November 2018 reprint is read as announced by 2018. Each is flagged. Everything else is unchanged.

## Amendment 5 (November 21, 2026, after the measuring run and before any voice record is read or any outcome tabulated): timing of the step against the margin

**Why.** The frog-in-pot draft for RICD 17.8 (Spine §10.5a, Propositions 10.5a.2 to 10.5a.6) predicts that a drift is rescued only when something converts it into a step in the signal (an announcement, an accreditor's action, a public deadline) while the margin is still positive, and that anchors widen the gap between shock and drift endings because they absorb the shocks they see. Sweet Briar is the named example: a drift, an announcement while the college still had an endowment, and a rescue. These tests read statement dates and the frozen financial states only, and are added now, before any voice record or outcome is read.

**Margin at the step.** The frozen financial state (ending types protocol §3, Amendments 1 to 3) in the last fiscal year before the qualifying statement (Amendment 4's reading). **Margin positive:** self-covering or held up by anchors. **Margin gone:** short beyond its anchors, the frozen stand-in for Δ_PNR ≤ 0. A case with no year with data is reported as unmeasured, never dropped.

**The tests (all report-only; P1 to P3 are unchanged).**

- **S1.** Among reversed closures and near-closures, the share with a positive margin at the statement. Every such case has a discrete statement by definition (Amendment 3), so S1 measures timing only. Prediction: most reversals began with a positive margin.
- **S2.** Among matched closures of drift type, the share whose margin was gone in the last fiscal year of their window (Amendment 4, part 1). Prediction: higher than S1's share with the margin gone, since in a drift closure the first step in the signal comes too late.
- **S3.** Lasting rescues against rescue attempts that ended in closure (Amendment 2): margin at the statement, compared directly. Prediction: lasting rescues had the positive margin more often. This extends Amendment 2's report-only row.
- **S4.** Across every public and private nonprofit closure in data/ending types/closures.csv with an ending type and an anchoring class (section 3, measured for every closure by the same code), the drift-type share of closures among anchored colleges against unanchored, with Fisher's exact test. Prediction (Proposition 10.5a.6): the drift-type share is higher among anchored closures, since anchors rescue the shocks they see and fail the drifts they do not.

Each test reports its counts and exact 95% intervals, with every case listed.

**Converted colleges left out of the matched closures.** Section 2 leaves for-profit closures out because their anchor is not observable. A college that was for-profit and converted to nonprofit before closing (for example, campuses sold by Corinthian Colleges to a nonprofit buyer in 2015) carries the same problem under a nonprofit label. Any closure listed as for-profit (CONTROL 3) in any header file from 2005 on is therefore left out of the closure pool, and the matched closures are redrawn by section 2's rule with the same seed. The colleges left out are listed in data/anchor and voice/converted closures left out.csv. No case is affected; the redraw is made before any voice record is read.

**Search procedure (replaces the terms of section 5's search procedure; sources unchanged).** Sizing the searches showed that section 5 as written (eight terms across seven sources for each of about one hundred drift-type colleges) runs past a thousand searches. Each college searched instead gets two logged searches: one of the national sources (Inside Higher Ed, Higher Ed Dive, the Chronicle of Higher Education, CourtListener and the AAUP site, including its censure list), and one of the local and student press, each with the college's name and all eight terms combined in one query. A search that turns up a candidate event is followed by opening the source to confirm the event, its date and its actor. Every search is logged with its date, query and result count, including searches that find nothing. Voice is searched for every college that enters P2 (drift-type cases and drift-type matched closures) and for every case in S3; other cases are searched only if a later count needs them. A combined query can miss events that separate queries would find; this applies equally to rescued colleges and closures, so it lowers the count of voice events without favouring either group, and is reported as a limitation.

The searches and the outcome column then follow, in that order. Everything else is unchanged.
