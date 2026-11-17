# Tell

**Status (November 16, 2026):** tracker v3 passed its pre-registered out-of-sample test on 987 institutions. Exploratory follow-up analyses are done. The tracker's official and operational channels are now being redesigned as tracker v4, which will be tested first on two-year colleges and then blind against the 2026–27 IPEDS data (expected around late July 2027). Details below.

Built to measure feedback divergence (an institution's official metrics versus its operational reality), Tell tracks institutional distress -- financial distress, upheaval, recovery, and the anchoring metrics which determine distress risk vs. collapse risk -- in higher ed institutions.

**Why "Tell":** in poker, a tell is an involuntary sign -- a hesitation, a
shift in posture, a change in breathing -- that reveals what a player is
actually holding, independent of how they're betting or what they're
saying at the table. This project reads the financial equivalent. Its
core model tracks three separate channels for every institution --
official, operational, and meta -- specifically to measure the
divergence between how an institution represents itself and what its own
underlying financial and enrollment data actually show. That divergence
is the tell: not a prediction of what happens next, but a real signal,
read directly off the data, of what's going on underneath the public
narrative. And critically, a tell in poker doesn't mean a player has
already lost the hand -- it means their hand differs from their table
talk. In the same way, an elevated score from this project doesn't mean
an institution is closing; it means its real financial dynamics diverge
from its projected stability. That distinction -- a real signal of
distress, not a verdict on the outcome -- is the whole design of this
project, summarized in ["Distress, not collapse"](#distress-not-collapse) below.

Tell is a Bayesian state-space model and tested classifier for
institutional financial collapse risk **and** degree of financial
distress in U.S. higher education, built on the Recursive
Information-Container Dynamics (RICD) framework. It was developed under
the working name "RICD Higher-Education Collapse Tracker"; Tell is its
name now that what it actually reads -- a real signal in the data, not a
prediction of an outcome -- is the more accurate description of what it
does.

**The full RICD manuscript (the complete, domain-independent theory) is in two
documents: the Spine, which holds the core engine,
[`docs/RICD 17.6 Spine.docx`](<docs/RICD 17.6 Spine.docx>)
(also available as [`.tex`](<docs/RICD 17.6 Spine.tex>)), and the Catalog of
Mechanisms, which holds every further mechanism, edge case and audit protocol,
[`docs/RICD 17.6 Catalog.docx`](<docs/RICD 17.6 Catalog.docx>)
(also available as [`.tex`](<docs/RICD 17.6 Catalog.tex>)).**
The two share section numbers, so a reference to a section not in one is in the
other. Everything in this repository's code implements a real subset of that
framework (Parts 6, 7, 8, and 10.5b specifically) against U.S. higher-education
data; the manuscript itself is domain-independent and covers considerably more
than the tracker uses.

## Related and future work

- **Reports** on how the tracker was built and what it found are in [`reports/`](reports/).
- **Related projects, in their own repositories:** [Plurimo](https://github.com/carmen-speer/RICD-Plurimo), a teaching platform for tutors and independent educators built around RICD; and the [Web–Field Model of Cognitive Trait Distributions](https://github.com/carmen-speer/RICD-Web-Field-Model-Systems-Cognition), an early application of RICD to human cognitive traits.
- **Not yet built:** four new RICD adapters (banking, hospitals, public schools, and nursing homes and long-term care), each planned as its own dedicated, named repository, as Tell is ([build roadmap](<future-projects/Next Project for RICD - Four Adapter Build Roadmap.pdf>)); the wider [roadmap of planned trackers](<future-projects/RICD Ongoing Projects Roadmap.docx>); and an [agent tracker](<future-projects/Collapse-Causal Agent Tracker (C-CAT) Seed Note.pdf>) that would investigate the specific decisions and people behind a collapse rather than its financial effects.
- **Built since it was planned:** the anchor sensor, tested in tracker v3 (see Results). Its original [seed note](<future-projects/Anchor-Quantification Sensor - Seed Note.md>) is kept as a record.
- **Provenance materials** (the framework's source documents, earlier versions and the full verification record) are archived separately and available on request.

## What the tracker is testing

RICD's claim, applied to colleges, is this: an institution heads toward failure when what it presents officially (its stated price, its reported outcomes) drifts away from what is actually happening inside it (who enrolls, what students pay, what they learn), and the cost of maintaining that gap accumulates as a kind of debt that erodes the institution's capacity to adapt, unless an outside anchor (a state, a church, a system, a rescuer) absorbs the cost for it. The tracker reads these quantities from public federal data (IPEDS and the College Scorecard), and each test asks one question: do they identify the colleges that later close, better than simple alternatives such as flagging every for-profit college, or the standard early-warning method in complex-systems research (rising variance and autocorrelation, "critical slowing down")?

Every test below was fixed in a protocol committed to this repository before the institutions were scored, and every score was committed before any outcome was looked up. Results are reported in full, failures included. "J" (Youden's J) is the share of closures caught minus the share of survivors flagged: 0 is no better than chance and 1 is perfect.

## Results

### Tracker v1: not passed, and why

The first confirmatory test ([`sampling protocol.md`](<sampling protocol.md>)) scored 278 of 300 randomly drawn institutions with a classifier trained on the 54-institution development panel. It flagged 12 of the 13 institutions that later closed or merged, but it also flagged 253 of the 278, which is no use as a warning.

Two mistakes produced that result. The first was training on the panel at all: the panel had been assembled to teach the tracker what healthy and failing colleges look like, so nearly half of it (23 of 54) were closures, far above the real rate of about 5% over six years. A classifier that learns from a world in which almost half of colleges fail flags almost everything in the real one. The second was the insufficient-data rule, adopted after the scores of one college (Thomas Aquinas College) would not reproduce reliably: any candidate whose records were incomplete, or whose results were unstable, was skipped and replaced. That rule passed over 476 candidates, and 54 of them later closed or merged, four times the 13 closures among the institutions actually scored. Colleges in trouble are exactly the ones whose records thin out, so the rule threw away the signal it should have been reading.

### Tracker v2: passed, narrowly

Protocol v2 ([`sampling protocol v2.md`](<sampling protocol v2.md>)) fixed both mistakes. The classifier was trained on a random draw of 600 institutions from 2014, with their real outcomes over the next five years, so it learned the real rate of failure. And missing data became a signal instead of a reason for exclusion: two new features measure gaps in an institution's reporting (years missing at the end of its record, and years missing in between), institutions that still could not be scored were kept in the record rather than replaced, and their outcomes are reported alongside every result.

Tested on 245 scorable institutions from 2019, v2 passed (J 0.40, 95% interval 0.08 to 0.72), catching 6 of 11 closures. But it passed almost entirely by flagging for-profit colleges, which close far more often than others; among public and nonprofit colleges it caught only 1 of 6 closures.

### Tracker v3: passed, with skill among nonprofits

Before v3, an analysis of the development data showed two things. Among public and nonprofit colleges, an institution's size alone (its enrollment) predicted closure better than the tracker's own features. And most nonprofit closures were not sudden shocks but slow slides toward break-even. Protocol v3 ([`sampling protocol v3.md`](<sampling protocol v3.md>)) responded with three additions, all built and frozen before any test institution was listed:

1. **Size and sector** became features alongside the tracker's own, and a second model using only size and sector was frozen beside it, so the test could ask separately whether the tracker's features add anything beyond them.
2. **Drift-type collapse** (RICD 17.4, §10.3a). The model already read shock-type distress, the sudden jumps in debt that come from a single large loss. It now also reads the slow kind: an enrollment base sliding toward the break-even point, with a recovery window that narrows as the slide continues and a point of no return beyond which recovery is no longer possible. Five read-outs of that slide became features.
3. **The anchor sensor**, a separate layer that reads each institution's outside support (state and local appropriations and gifts as shares of its expenses, and membership in a public or nonprofit system). It cannot add risk; it can only clear a flag.

The test used all 1,382 institutions remaining in the 2019 frame, 987 of them scorable. Of those 987, 56 closed or failed. v3 flagged 111, catching 32 closures while flagging 79 of 931 survivors: **J 0.49 (0.35 to 0.62). Passed.** It beat flagging every for-profit (J 0.31) and critical slowing down (J −0.02, no better than chance), and unlike v2 it has skill among public and nonprofit colleges alone (J 0.29, 0.14 to 0.45, catching 12 of 32 private nonprofit closures). The anchor sensor passed both of its tests: outside support separated the flagged institutions that survived from those that closed (area under the ROC curve 0.68), and the anchored flag improved slightly on v3's own (J 0.50 against 0.49), clearing 14 flags, none of them closures.

**What v3 did not show.** The second verdict did not show that the tracker's own features add value beyond size and sector (among public and nonprofit colleges, area under the ROC curve 0.87 against 0.85; the difference's interval includes zero). Within the for-profit sector it has no skill: it flags almost all of them. And institutions that could not be scored, usually because their records are missing, closed far more often than those that could (18%, and 40% of those that file no finance record of their own, against 6%): a missing record is itself a warning sign.

### Why size and sector carry so much of the signal

Most likely, largely because of anchoring. Large and public institutions are the anchored ones: state appropriations that can flex in a crisis, state-backed borrowing, membership in a system that can cross-subsidize, an established donor base, and political stakes that make a rescue likely. Small private colleges and for-profit colleges usually have none of these, so the same distress that a large public university absorbs can close them. The evidence fits: past the break-even point, institutions with substantial outside support closed at about a fifth the rate of those without it, while below break-even support made almost no difference, which is the pattern RICD's point-of-no-return mathematics predicts. It is not the whole explanation, though. Size also stands for demand (an enrollment base that is not sliding), and for-profit colleges close partly for regulatory reasons, as when federal enforcement brought down large chains such as Corinthian and ITT. Anchoring and size overlap so heavily that the two have not yet been separated; doing so is part of the work ahead.

### The meta-channel error, and what it revealed

The model reads three channels for every institution: an **official** channel (what the institution presents; so far, its sticker tuition), an **operational** channel (what actually happens; so far, its completion rate), and a **meta** channel (the institution's capacity to monitor and correct itself, carried by the people who can raise an alarm). Divergence is the largest gap between them. In every run so far the meta channel was never measured, and the model's fallback value for it sat outside the range any real value can take, so the gaps involving it always dominated. The tracker's "divergence" was therefore measuring how low an institution's tuition and completion were, not how far its official and operational layers had split: RICD's divergence mechanism had not actually been tested.

A reanalysis ([`reanalysis protocol.md`](<reanalysis protocol.md>); exploratory, since the outcomes were already known) removed the error using the two-channel mode now defined in RICD 17.6 (Spine §6.3.3), which computes divergence from the official and operational channels alone when the meta channel is unavailable. The tracker performed the same or slightly better (J 0.50; among nonprofits 0.32) and still did not beat size and sector. Its refitted weights showed why: divergence built from sticker tuition and completion carries little closure signal of its own. Sticker price mostly marks a college as established, and completion can be inflated from inside, for example when instructors under pressure pass students who have not learned the material. Those two proxies, not the idea of divergence, are what failed, and they are being replaced (see "What we're working on now").

### The search for the meta channel (exploratory)

Two hypotheses about who carries the meta channel were measured from the IPEDS staffing files and tested on the development colleges, then the first was retested on the held-out v3 colleges under a pre-registered protocol ([`administrative layer retest protocol.md`](<administrative layer retest protocol.md>)):

- **The administrative layer.** The hypothesis: the meta layer is the administrative class, and the thicker it is, the more it spends on form rather than function, forms a firewall between official and operational values, and drives divergence and debt. Result: compared at equal size and wealth, a thicker administrative layer goes with more of the tracker's resource debt across all colleges, but it does not predict closure, and it rises together with full-time faculty rather than replacing them. Among private nonprofits, the colleges that closed most often were those with a thin administrative layer and fast-growing debt: a college too starved to hire, not one bloated with administrators. The administrative layer looks less like the meta channel than like a cost on resources in its own right.
- **Tenure protection.** The hypothesis (RICD Spine §15.2): the meta channel is the population that can transmit dissent accurately, and job security is what makes that possible, so a college with more tenure-protected faculty catches and corrects divergence. Result: compared at equal size and wealth, a higher tenure share did not predict less closure, and it went with more, not less, of the tracker's resource debt.

Both candidates point the "wrong" way against the same debt measure, the one built from sticker tuition and completion that barely predicts closure. That points to the yardstick rather than settling the candidates, so the meta channel will be re-judged once the official and operational channels are redesigned.

### Texas transfer test (pre-registered; exploratory)

The hypothesis ([`transfer test protocol.md`](<transfer test protocol.md>)): contingent (adjunct) instructors are paid only for class hours, and can lose their jobs to a single unprovable complaint simply by not being rehired, so teaching under those conditions is simplified to match the wage and to avoid complaints. Community colleges that rely heavily on contingent instructors would then pass students on less prepared than their grades say, and those students would struggle after transferring, where faculty at another institution grade them. The test uses the Texas Higher Education Coordinating Board's reports on every community-college-to-university pair: first-year university GPA, whether students return the next fall, and whether they graduate, compared within the same receiving university and among colleges serving similar students. Because the outcomes already existed, the test is labeled exploratory.

**Result: not supported.** Across 61 community colleges and about 320,000 transfers (fall cohorts 2014 to 2024), students from colleges with a higher contingent share did no worse at the same receiving university: not in first-year GPA below 2.0, not in returning the following fall, and not in graduating within four years. All three predictions came out "not decided," with estimates close to zero, and the intervals rule out more than a small effect: each 10-point rise in a college's contingent share moves any of the three outcomes by less than about three-quarters of a percentage point, in either direction. The check across sending colleges agreed: transfers' graduation rates do not track their college's contingent share. Students' backgrounds did matter: colleges serving more Pell-grant students sent transfers who did worse on all three measures (no direction had been predicted for this). A first run was set aside before its results were used, because a parsing error had dropped the largest colleges; the correction is disclosed as Amendment 2 of the protocol. What the test cannot see: contingent share here is a headcount, which does not capture working conditions, and only students who transferred are observed, so pressure on grading could still show up in who transfers rather than in how they do afterward. Neither was tested.

The full v3 write-up, with every number, is being prepared as a report for [`reports/`](reports/).

## What we're working on now

- **Redesigning the official and operational channels.** The two early proxies are being replaced by two separate, traceable gaps: a **price gap** (an institution's listed price against what students actually pay, so a deepening discount shows up as divergence) and an **outcome gap** (reported completion against outcomes judged outside the college, such as transfer performance, licensure exam results or retention). Loan repayment and graduates' earnings were considered and set aside as the main measure, because they reflect the wider economy at least as much as the education. The formal mathematics for two gaps goes into the RICD manuscript first.
- **Choosing the meta channel**, re-tested against the corrected divergence: the candidates are the tenure-protected share of faculty and the balance between full-time faculty and the administrative layer, with documented governance failures (faculty censures, accreditor findings) as direct overrides.
- **A sector-level measure of degree inflation:** how many graduates, at every degree level and in every field, find full-time, living-wage work in what they studied, with adjunct and other contingent academic posts counted as underemployment, not employment. This measures the divergence of higher education as a whole, and will separate the pressure it puts on every college from each college's own choices, such as continuing to produce graduates into fields that are oversupplied, whether through failing to adapt to a changing economy, or by hiding poor outcomes or overstating graduates' financial prospects to keep tuition revenue in that field steady or growing as its value to graduates falls. A college whose stated mission makes no claims about the economic return of its programs, and rests instead on values (for example, a small liberal arts college with a strong philosophy department, or a Christian college that educates theologians), is not counted as diverging.
- **The extractive anchor.** In RICD, an anchor is a party that absorbs a struggling institution's losses and so keeps it alive, and the current definitions treat an anchor and an extractor (a party drawing resources out) as exclusive. But an extractor can act as a temporary anchor: it absorbs losses and builds dependence first (for students, through the promise of a career and through student-loan debt), cuts off the exits (credits other colleges will not accept), and only then extracts. If so, campuses that depend on an extracting parent should close less at first, close together when the parent fails, and over a long enough horizon catch up with and pass independent colleges' closure rates, while their spending shifts away from instruction. Because an extractor tends to believe its own official story, the divergence is measured from what happens to its dependents, not from its own reports. The first trace is in the v3 data: for-profit chain campuses closed less often than independent for-profits (23% against 42%; not statistically significant). The formal mathematics goes into the RICD manuscript first.
- **Where the strain goes.** The Texas test found transfer students from colleges that rely heavily on adjuncts doing no worse, which fits a different explanation: committed adjuncts refuse to lower their standards and absorb the cost themselves, through unpaid preparation and grading, so the arrangement continues because in the short term it works, the way a team stays on schedule because a few members work unpaid overtime, or the way a structure stays standing on a few overloaded supports: from outside it looks sound, while the stress accumulates in the parts carrying it. The plan is to measure the strain where it lands: adjunct retention and turnover, how many adjuncts move into tenure-track posts against how many leave higher education, publication rates against teaching loads, and whether colleges ever hire from their own adjunct pool. The model predicts that such a system collapses only if its adjuncts decouple together and cannot be replaced, for example in a nationwide strike too large to break.
- **Faculty alignment and kinds of endings:** measures of faculty voice, exit and silence, and a test of whether different endings (abrupt closure, merger, rescue, reset without closure) carry different warning signatures.

## What comes when the 2026–27 IPEDS data is released

A **blind retest**. Every institution will be scored on the newest data with tracker v4 (the two-channel v3 with the redesigned official and operational channels built in), and also with the two-channel v3 as a fallback, and the scores, flags, predicted kinds of endings and a short protocol will be committed here before the National Center for Education Statistics releases the 2026–27 institutional header file (HD2026, expected around late July 2027). The extractive-anchor predictions above will be committed with them. Closures that first appear in that file then judge the committed flags, and the same flags are judged again as each later file arrives. Every outcome looked up so far runs only through HD2025, so nothing in that test can be known in advance.

## Distress, not collapse

This tracker does not output a probability of closure. It reads whether an institution's internal financial dynamics resemble those that produced real closures. Whether that distress turns into a closure depends separately on an external anchor (RICD §10.5b.13): state appropriations, state-backed borrowing, system membership, a rescue campaign. A large public university can read as distressed and still be in no danger of closing, because its anchor absorbs the strain. Like a tire-pressure sensor that correctly reads a flat on a car with run-flat tires, the score is right about the tire; the anchor decides whether the car stops. Measuring that distress still matters: it shows how much strain the anchor is carrying and where it is concentrated. The full explanation, with the public-flagship examples, is in [explanations/Distress, not collapse.md](<explanations/Distress, not collapse.md>).

## The development panel

The 54-institution panel ([`data/panel/panel.json`](data/panel/panel.json); 23 real closures across seven collapse mechanisms and 31 stable comparisons) was assembled to teach the classifier what healthy and failing colleges look like, and the classifier reached 100% leave-one-out accuracy on it. That figure is in-sample on a designed panel, not evidence of real-world performance; tracker v1 showed what a classifier trained on it does on institutions nobody chose. The out-of-sample tests above are the evidence.

## The live dashboard

A public dashboard is at [carmen-speer.github.io/RICD-Tell](https://carmen-speer.github.io/RICD-Tell/) (built from [`docs/index.html`](docs/index.html)). It shows the development panel and institutions scored by the original live pipeline, which is tracker v1 and is now outdated. The plan: finish the new channel mathematics, build it into the two-channel v3 as tracker v4, test v4 under a pre-registered protocol on two-year colleges (which no version of the tracker has ever been trained or tested on, and whose outcomes have not been looked up), and rebuild the live tracker once, on v4, after it passes. The HD2026 retest then tests v4 blind on four-year colleges. The rebuilt dashboard will explain plainly that a flag marks risk of closure, not a forecast that a college will close.

## Known limits (current)

- The meta channel has not yet been measured in any tested version of the tracker, and the official and operational channels are being replaced.
- The tracker's own features have not been shown to add value beyond size and sector, and it has no skill within the for-profit sector.
- Institutions without usable records cannot be scored, and they close far more often.
- The wealth measure (endowment per student) is poorly calibrated for public institutions, whose support comes mainly from state appropriations.
- A comment in the frozen model file `src/model.py` cites the drift-versus-shock classification as RICD §9.4; it is §15.2. The file is frozen with classifier v3 (any edit would change its checked fingerprint), so the error is recorded here and corrected in the next model.

The full history of gaps, diagnostics and fixes, kept intact, is in [history of fixes/Known gaps and record of fixes.md](<history of fixes/Known gaps and record of fixes.md>).

## Repository structure

- **Protocols** (top level): [`sampling protocol.md`](<sampling protocol.md>), [`sampling protocol v2.md`](<sampling protocol v2.md>), [`sampling protocol v3.md`](<sampling protocol v3.md>), [`reanalysis protocol.md`](<reanalysis protocol.md>), [`administrative layer retest protocol.md`](<administrative layer retest protocol.md>), [`transfer test protocol.md`](<transfer test protocol.md>).
- [`src/`](src/): the model, the scoring pipelines for every test and the measurements.
- [`data/`](data/): every test's draws, scores, outcomes and results, by version (`confirmatory`, `v2`, `v3`, `v3 reanalysis`, `v3 exploratory`, `meta channel`, `transfer test`, `panel`).
- [`docs/`](docs/): the RICD manuscript (Spine and Catalog) and the dashboard.
- [`reports/`](reports/) and [`future-projects/`](future-projects/): reports and planned work.
- [`explanations/`](explanations/) and [`history of fixes/`](<history of fixes/>): longer explanations and the full record of fixes.
- [`.github/workflows/`](.github/workflows/): every workflow that scored, measured or tested anything, each named for its step.
- [`archive/`](archive/): the one-off diagnostic scripts and workflows from building and testing the tracker, moved with their history intact; what each found is in the record of fixes.

## Re-scoring cadence

IPEDS is not live data — it releases on a fixed institutional schedule
(provisional data a few times a year, final data annually). The scheduled
workflow in `.github/workflows/rescore.yml` runs periodically and checks
for new data rather than assuming a fixed release date; a run that finds
nothing new is a normal, expected outcome, not a failure.
