# Tell

## Start here

- **What Tell is.** A reader of institutional distress in U.S. higher education, not a closure forecast: it measures how far a college's official picture has drifted from what its own records show, and whether an outside anchor (a state, a church, a system, donors) is carrying the strain.
- **What it does (November 2026).** Tracker v3 passed its pre-registered test on 987 held-out institutions, with closures from 2019 to 2025: it caught 32 of 56 closures while flagging 79 of 931 survivors (J 0.49). It beat the standard alternatives, flagging every for-profit college (J 0.31) and the complex-systems early-warning method, critical slowing down (J −0.02, no better than chance), and it has skill among public and nonprofit colleges alone (J 0.29), where earlier versions had none. Its anchor sensor clears false flags on colleges that outside support is holding up (14 cleared, none of them closures). And it reads the slow kind of collapse that is easiest to miss: most colleges that closed since 2005 drifted toward closure rather than being knocked over by a single loss (see "How colleges approach closure").
- **What comes next.** The two-channel v3 is the tracker that will be tested blind against the 2026–27 IPEDS release; candidate additions are tested first and enter only if they pass (see "Testing new channels").
- **The dashboard** still runs the original tracker (v1); it will be rebuilt on v3.
- **To check or rerun anything:** [docs/QUICKSTART.md](docs/QUICKSTART.md). Every protocol is at the top level, every result in [data/](data/), and every error with its fix in [history of fixes/](<history of fixes/>).
- **Software and theory.** Tell is software: the higher-education adapter in [src/](src/), which implements part of Recursive Information-Container Dynamics (RICD) against IPEDS and College Scorecard data. RICD is the theory, domain-independent, in [docs/](docs/) (the RICD 17.7 Spine and Catalog); a result about Tell tests this adapter's implementation, so a gap in Tell is not by itself a gap in RICD.

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
[`docs/RICD 17.7 Spine.docx`](<docs/RICD 17.7 Spine.docx>)
(also available as [`.tex`](<docs/RICD 17.7 Spine.tex>)), and the Catalog of
Mechanisms, which holds every further mechanism, edge case and audit protocol,
[`docs/RICD 17.7 Catalog.docx`](<docs/RICD 17.7 Catalog.docx>)
(also available as [`.tex`](<docs/RICD 17.7 Catalog.tex>)).**
The two share section numbers, so a reference to a section not in one is in the
other. Everything in this repository's code implements a real subset of that
framework (Parts 6, 7, 8, and 10.5b specifically) against U.S. higher-education
data; the manuscript itself is domain-independent and covers considerably more
than the tracker uses.

## Related and future work

- **Reports** on how the tracker was built and what it found are in [`reports/`](reports/).
- **Related projects, in their own repositories:** [Plurimo](https://github.com/carmen-speer/RICD-Plurimo), a teaching platform for tutors and independent educators built around RICD; and the [Web–Field Model of Cognitive Trait Distributions](https://github.com/carmen-speer/RICD-Web-Field-Model-Systems-Cognition), an early application of RICD to human cognitive traits.
- **Not yet built:** four new RICD adapters (banking, hospitals, public schools, and nursing homes and long-term care), each planned as its own dedicated, named repository, as Tell is ([build roadmap](<future-projects/Next Project for RICD - Four Adapter Build Roadmap.pdf>)); the wider [roadmap of planned trackers](<future-projects/RICD Ongoing Projects Roadmap.docx>); and an [agent tracker](<future-projects/Collapse-Causal Agent Tracker (C-CAT) Seed Note.pdf>) that would investigate the specific decisions and people behind a collapse rather than its financial effects.
- **Built since it was planned:** the anchor sensor, tested in tracker v3, and its first working quantification, the anchored share and who carries the strain (see "How colleges approach closure"). The original [seed note](<future-projects/Anchor-Quantification Sensor - Seed Note.md>) is kept as a record.
- **Provenance materials** (the framework's source documents, earlier versions and the full verification record) are archived separately and available on request.

## What the tracker is testing

RICD's claim, applied to colleges, is this: an institution heads toward failure when what it presents officially (its stated price, its reported outcomes) drifts away from what is actually happening inside it (who enrolls, what students pay, what they learn), and the cost of maintaining that gap accumulates as a kind of debt that erodes the institution's capacity to adapt, unless an outside anchor (a state, a church, a system, a rescuer) absorbs the cost for it. The tracker reads these quantities from public federal data (IPEDS and the College Scorecard), and each test asks one question: do they identify the colleges that later close, better than simple alternatives such as flagging every for-profit college, or the standard early-warning method in complex-systems research (rising variance and autocorrelation, "critical slowing down")?

Every test below was fixed in a protocol committed to this repository before the institutions were scored, and every score was committed before any outcome was looked up. Results are reported in full, failures included. "J" (Youden's J) is the share of closures caught minus the share of survivors flagged: 0 is no better than chance and 1 is perfect.

## Results

### Tracker v1: not passed, and why

The first confirmatory test ([`sampling protocol.md`](<sampling protocol.md>)) scored 278 of 300 randomly drawn institutions with a classifier trained on the 54-institution development panel. It flagged 12 of the 13 institutions that later closed or merged, but it also flagged 253 of the 278, which is no use as a warning.

Two mistakes produced that result. The first was an omitted step. The panel had been assembled to teach the tracker what different kinds of collapse look like, so nearly half of it (23 of 54) were closures, far above the real rate of about 5% over six years. Building a model on a sample enriched with rare events is a standard design (case-control sampling), but it requires a correction for the true base rate before the model scores the real population (King and Zeng, 2001, "Logistic Regression in Rare Events Data"), and that correction was omitted. The model's ranking held, catching 12 of 13 closures, but its cutoff was set for a world in which almost half of colleges fail, so it flagged almost everything in the real one. The second was the insufficient-data rule, adopted after the scores of one college (Thomas Aquinas College) would not reproduce reliably: any candidate whose records were incomplete, or whose results were unstable, was skipped and replaced. That rule passed over 476 candidates, and 54 of them later closed or merged, four times the 13 closures among the institutions actually scored. Colleges in trouble are exactly the ones whose records thin out, so the rule threw away the signal it should have been reading.

### Tracker v2: passed, narrowly

Protocol v2 ([`sampling protocol v2.md`](<sampling protocol v2.md>)) fixed both mistakes. The classifier was trained on a random draw of 600 institutions from 2014, with their real outcomes over the next five years, so it learned the real rate of failure. And missing data became a signal instead of a reason for exclusion: two new features measure gaps in an institution's reporting (years missing at the end of its record, and years missing in between), institutions that still could not be scored were kept in the record rather than replaced, and their outcomes are reported alongside every result.

Tested on 245 scorable institutions from 2019, v2 passed (J 0.40, 95% interval 0.08 to 0.72), catching 6 of 11 closures. But it passed almost entirely by flagging for-profit colleges, which close far more often than others; among public and nonprofit colleges it caught only 1 of 6 closures.


### Tracker v3: passed, with skill among nonprofits

Before v3, an analysis of the development data showed two things. Among public and nonprofit colleges, an institution's size alone (its enrollment) predicted closure better than the tracker's own features. And most nonprofit closures were not sudden shocks but slow slides toward break-even. Protocol v3 ([`sampling protocol v3.md`](<sampling protocol v3.md>)) responded with three additions, all built and frozen before any test institution was listed:

1. **Size and sector** became features alongside the tracker's own, and a second model using only size and sector was frozen beside it, so the test could ask separately whether the tracker's features add anything beyond them.
2. **Drift-type collapse** (RICD 17.4, §10.3a). The model already read shock-type distress, the sudden jumps in debt that come from a single large loss. It now also reads the slow kind: an enrollment base sliding toward the break-even point, with a recovery window that narrows as the slide continues and a point of no return beyond which recovery is no longer possible. Five read-outs of that slide became features.
3. **The anchor sensor**, a separate layer that reads each institution's outside support (federal, state and local appropriations and gifts as shares of its expenses, and membership in a public or nonprofit system). It cannot add risk; it can only clear a flag.


The test used all 1,382 institutions remaining in the 2019 frame, 987 of them scorable. Of those 987, 56 closed or failed. v3 flagged 111, catching 32 closures while flagging 79 of 931 survivors: **J 0.49 (0.35 to 0.62). Passed.** It beat flagging every for-profit (J 0.31) and critical slowing down (J −0.02, no better than chance), and unlike v2 it has skill among public and nonprofit colleges alone (J 0.29, 0.14 to 0.45, catching 12 of 32 private nonprofit closures). The anchor sensor passed both of its tests: outside support separated the flagged institutions that survived from those that closed (area under the ROC curve 0.68), and the anchored flag improved slightly on v3's own (J 0.50 against 0.49), clearing 14 flags, none of them closures. Institutions that could not be scored, usually because their records are missing, closed far more often than those that could (18%, and 40% of those that file no finance record of their own, against 6%): a missing record is itself a warning sign.

**Size and sector.** A model of size and sector alone does nearly as well among public and nonprofit colleges (area under the ROC curve 0.85 against v3's 0.87; the difference's interval includes zero), as expected: size and sector stand in for anchoring, as the next section explains, so a tracker reading distress was never expected to beat them outright. What the tracker is built to add is what they cannot see: the colleges that size and sector misread (small colleges that are anchored, large ones that are sliding), how much strain the anchors are carrying, and whether a college is drifting. Within the for-profit sector the tracker has no skill: it flags almost all of them.

### Why size and sector carry so much of the signal

Most likely, largely because of anchoring. Large and public institutions are the anchored ones: state appropriations that can flex in a crisis, state-backed borrowing, membership in a system that can cross-subsidize, an established donor base, and political stakes that make a rescue likely. Small private colleges and for-profit colleges usually have none of these, so the same distress that a large public university absorbs can close them. The evidence fits: past the break-even point, institutions with substantial outside support closed at about a fifth the rate of those without it, while below break-even support made almost no difference, which is the pattern RICD's point-of-no-return mathematics predicts. It is not the whole explanation, though. Size also stands for demand (an enrollment base that is not sliding), and for-profit colleges close partly for regulatory reasons, as when federal enforcement brought down large chains such as Corinthian and ITT. Anchoring and size overlap so heavily that the two have not yet been separated; doing so is part of the work ahead.

### The meta-channel error, and what it revealed

The model reads three channels for every institution: an **official** channel (what the institution presents; so far, its sticker tuition), an **operational** channel (what actually happens; so far, its completion rate), and a **meta** channel (the institution's capacity to monitor and correct itself, carried by the people who can raise an alarm). Divergence is the largest gap between them. In every run so far the meta channel was never measured, and the model's fallback value for it sat outside the range any real value can take, so the gaps involving it always dominated. The tracker's "divergence" was therefore measuring how low an institution's tuition and completion were, not how far its official and operational layers had split: RICD's divergence mechanism had not actually been tested.

A reanalysis ([`reanalysis protocol.md`](<reanalysis protocol.md>); exploratory, since the outcomes were already known) removed the error using the two-channel mode defined in the RICD manuscript (Spine §6.3.3, added in RICD 17.6), which computes divergence from the official and operational channels alone when the meta channel is unavailable. The tracker performed the same or slightly better (J 0.50; among nonprofits 0.32) and still did not beat size and sector. Its refitted weights showed why: divergence built from sticker tuition and completion carries little closure signal of its own. Sticker price mostly marks a college as established, and completion can be inflated from inside, for example when instructors under pressure pass students who have not learned the material. Those two proxies, not the idea of divergence, are what failed, and they are being replaced (see "Testing new channels").

### The search for the meta channel (exploratory)

Two hypotheses about who carries the meta channel were measured from the IPEDS staffing files and tested on the development colleges, then the first was retested on the held-out v3 colleges under a pre-registered protocol ([`administrative layer retest protocol.md`](<administrative layer retest protocol.md>)):

- **The administrative layer.** The hypothesis: the meta layer is the administrative class, and the thicker it is, the more it spends on form rather than function, forms a firewall between official and operational values, and drives divergence and debt. Result: compared at equal size and wealth, a thicker administrative layer goes with more of the tracker's resource debt across all colleges, but it does not predict closure, and it rises together with full-time faculty rather than replacing them. Among private nonprofits, the colleges that closed most often were those with a thin administrative layer and fast-growing debt: a college too starved to hire, not one bloated with administrators. The administrative layer looks less like the meta channel than like a cost on resources in its own right.
- **Tenure protection.** The hypothesis (RICD Spine §15.2): the meta channel is the population that can transmit dissent accurately, and job security is what makes that possible, so a college with more tenure-protected faculty catches and corrects divergence. Result: compared at equal size and wealth, a higher tenure share did not predict less closure, and it went with more, not less, of the tracker's resource debt.

Both candidates point the "wrong" way against the same debt measure, the one built from sticker tuition and completion that barely predicts closure. That points to the yardstick rather than settling the candidates. A staffing share describes who makes up a college, not what its people read, so neither is used as the meta channel; its first reading, staff exit, is described under "Testing new channels," and whether staffing composition adds anything beyond it will be tested separately.

### Testing new channels (pre-registered, November 2026)

Every candidate addition was tested on the development colleges under [`channel selection protocol.md`](<channel selection protocol.md>), committed before anything was fitted, with every later choice added as a dated amendment before the data it governed were read. Each was compared with a model of size and sector alone, on out-of-sample predictions, first on the 2014 frame (every four-year college; closures 2015 to 2019) and then, for anything that showed a gain, confirmed on the untouched 2019 frame (closures 2019 to 2025). An addition enters the tracker only if its gain is confirmed there with an interval above zero. None was confirmed, so the two-channel v3 stands as the tracker for the blind retest, and promising readings are tested prospectively instead.

- **The price gap, the outcome gap and the four-year gap** (discounting beyond what is usual for colleges serving students with similar need; reported completion against the completion retention predicts; completers finishing later than the degree's stated length): none added anything beyond size and sector, which alone reach an area under the ROC curve of 0.91 to 0.93 on the 2014 frame. **Prediction P1** (excess discount widening while the published price held): not supported in either frame.
- **Staff exit** (full-time staff leaving faster than at comparable colleges of the same sector and wealth, the meta reading of the soundness claim): a real gain on the 2014 frame (+0.016, interval +0.006 to +0.027), the first claim reading in Tell's history to do so, and a gain in the same direction on the 2019 frame (+0.013) whose interval included zero. Not confirmed; it is tested prospectively together with governance voice (AAUP censures and accreditor actions), as one channel in several parts.
- **The endowment draw** cannot be measured before fiscal 2020 and is tested prospectively from the fiscal 2024 spending distribution.
- **The value dimension** (borrowers repaying, from the College Scorecard) exists only from the 2018–19 file; its one held-out comparison gained +0.016 over size and sector, interval −0.001 to +0.033. Not entered; tested prospectively.
- **Staffing shares** (part-time and secure faculty): neither adds reliably beyond size, sector and staff exit. **System-level AAUP censures** count only the campus the report names.

Every result is in [`data/v4 channels/`](<data/v4 channels/>).

### Law schools (exploratory, November 2026)

Law schools publish their own outcomes (bar passage and employment, in ABA disclosures), so failure should show plainly in outcome data before the end. Five of seven closed law schools sat in the bottom tenth on bar passage or employment in at least two of their last three years (the exception, Concordia, closed with its parent university). In the larger test, severe first-year enrollment collapse within three years, bottom-tenth schools collapsed ten times as often as others (10.3% against 1.0% of school-years, 2017 to 2022; interval 3.8 to 38.6; area under the ROC curve 0.81), holding without the closures and within size thirds. The same test in nursing and pharmacy programs is next.

### How colleges approach closure (exploratory, November 2026)

Most colleges that closed got there through a slow slide, not a sudden blow, so most closures were preventable early. The warning sat in their records for years, which is the kind of collapse that normalization hides from the people who could stop it, and the kind this tracker exists to read. Under [`ending types protocol.md`](<ending types protocol.md>), each college's approach to the break-even point was split into a drift part and a jump part (Spine Definition 10.3a.6). Among private nonprofit closures since 2005, drift-type approaches outnumber shock-type about six to one (69 against 12), and among for-profit closures about thirteen to one (145 against 11). Sweet Briar College is the worked case of the escape route: it ran modest deficits for a decade, and its 2015 closure announcement turned that drift into a single shock, the one jump carrying the whole rise, which is what rallied the alumnae and the wider network that rescued it. The University of Phoenix, which has not closed, shows a pure slide so far.

The same measurement gives the first working version of the anchor sensor's quantification: each college-year is self-covering, held up by anchors, or short beyond them (spending more than all its operating income plus a normal endowment draw). About one public college in five is short beyond its anchors (25% in 2005, 18% in 2024); among private nonprofits the share nearly doubled after 2015 (15% in 2005, 17% in 2015, 28% in 2024). States carry almost the whole remaining gap at public colleges, so a state budget cut can turn a stable college into a collapsing one; at private colleges, gifts and endowment together covered well over the gap on average, but that cushion thinned sharply by 2024, just as more colleges needed it. Exits recorded as mergers (403) or as disappearances with no closure record (453, many of them for-profit campuses) are not classified, so the for-profit counts cover documented closures only. Three corrections to the measurement, each made after a run showed the comparison incomplete, are recorded as the protocol's amendments. Results are in [`data/ending types/`](<data/ending types/>).

### Other exploratory results (November 2026)

- **Professions and trades** ([`lifetime earnings protocol.md`](<lifetime earnings protocol.md>)): graduates of the professions start at or above their occupations' median wage, not below it as predicted, and climb a longer ladder; the trades' advantage is cost (median debt $11,400 against $120,000). Medicine and law fit the prediction; dentistry, pharmacy and veterinary medicine do not.
- **For-profit chains** (the extractive anchor): chain campuses closed far more often than independent for-profits after 2013 (by 2025, 51% against 27% counting documented closures only), with closures clustered within chains and no early protection.
- **Adjunct reliance:** colleges relying most on part-time instructors closed more often than others at equal wealth from the first year, with no lower on-time completion; whether that is cause or symptom is tested prospectively.
- **Openings against closures:** small for-profit colleges refilled until federal enforcement, then shrank; small private nonprofits stopped replacing their closures after 2016; liberal arts colleges appear to survive mainly by converting away from the liberal arts model (Carnegie reclassification), a reorganization rather than an ending.
- **The Texas transfer test** (adjunct reliance and transfer students' outcomes): not supported; archived in [`archive/Texas transfer test.md`](<archive/Texas transfer test.md>).

The full v3 write-up, with every number, is being prepared as a report for [`reports/`](reports/).

## What we're working on now

- **The anchor-and-voice test,** as case studies: whether shock with anchors ends in rescue or reorganization, drift without anchors in quiet closure, and voice that stays aligned during a drift (alumni campaigns, faculty votes, censures, public appeals) predicts rescue, using every reversed or rescued closure against a matched sample of drift closures.
- **Where the strain comes from inside a college:** which spending lines drive the growth of the gap the anchors are carrying.
- **Outcome failure in licensed fields:** the law-school test repeated in nursing and pharmacy programs, which publish pass rates by school.
- **The live tracker,** rebuilt on v3.
- **A sector-level measure of degree inflation:** how many graduates, at every degree level and in every field, find full-time, living-wage work in what they studied, with adjunct and other contingent academic posts counted as underemployment, not employment. A college whose stated mission rests on values rather than claims about economic return is not counted as diverging.

## What comes when the 2026–27 IPEDS data is released

A **blind retest**. Every institution will be scored on the newest data with the two-channel v3, and the scores, flags, predicted kinds of endings and a short protocol will be committed here before the National Center for Education Statistics releases the 2026–27 institutional header file (HD2026, expected around late July 2027). The prospective tests (staff exit with governance voice, the endowment draw, the value dimension, adjunct timing, the extractive-anchor predictions, ending types) will be committed with them. Closures that first appear in that file then judge the committed flags, and the same flags are judged again as each later file arrives. Every outcome looked up so far runs only through HD2025, so nothing in that test can be known in advance.

## Distress, not collapse

This tracker does not output a probability of closure. It reads whether an institution's internal financial dynamics resemble those that produced real closures. Whether that distress turns into a closure depends separately on an external anchor (RICD §10.5b.13): state appropriations, state-backed borrowing, system membership, a rescue campaign. A large public university can read as distressed and still be in no danger of closing, because its anchor absorbs the strain. Like a tire-pressure sensor that correctly reads a flat on a car with run-flat tires, the score is right about the tire; the anchor decides whether the car stops. Measuring that distress still matters: it shows how much strain the anchor is carrying and where it is concentrated. The full explanation, with the public-flagship examples, is in [explanations/Distress, not collapse.md](<explanations/Distress, not collapse.md>).

## The development panel

The 54-institution panel ([`data/panel/panel.json`](data/panel/panel.json); 23 real closures across seven collapse mechanisms and 31 stable comparisons) was assembled to teach the classifier what healthy and failing colleges look like, and the classifier reached 100% leave-one-out accuracy on it. That figure is in-sample on a designed panel, not evidence of real-world performance; tracker v1 showed what a classifier trained on it does on institutions nobody chose. The out-of-sample tests above are the evidence.

## The live dashboard

A public dashboard is at [carmen-speer.github.io/RICD-Tell](https://carmen-speer.github.io/RICD-Tell/) (built from [`docs/index.html`](docs/index.html)). It shows the development panel and institutions scored by the original live pipeline, which is tracker v1 and is now outdated. It will be rebuilt once, on v3, and will explain plainly that a flag marks risk of closure, not a forecast that a college will close.

## Known limits (current)

- The meta channel has not yet been measured in any tested version of the tracker; staff exit, its first reading, is a residual estimated from staffing counts, not an observed count of departures.
- The tracker has no skill within the for-profit sector.
- Institutions without usable records cannot be scored, and they close far more often.
- The wealth measure (endowment per student) is poorly calibrated for public institutions, whose support comes mainly from state appropriations.
- Ending types: pension costs could not be separated (IPEDS has no pension expense field), and exits recorded as mergers or disappearances are not classified.
- A comment in the frozen model file `src/model.py` cites the drift-versus-shock classification as RICD §9.4; it is §15.2. The file is frozen with classifier v3 (any edit would change its checked fingerprint), so the error is recorded here and corrected in the next model.

The full history of gaps, diagnostics and fixes, kept intact, is in [history of fixes/Known gaps and record of fixes.md](<history of fixes/Known gaps and record of fixes.md>).

## Repository structure

- **Protocols** (top level): [`sampling protocol.md`](<sampling protocol.md>), [`sampling protocol v2.md`](<sampling protocol v2.md>), [`sampling protocol v3.md`](<sampling protocol v3.md>), [`reanalysis protocol.md`](<reanalysis protocol.md>), [`administrative layer retest protocol.md`](<administrative layer retest protocol.md>), [`transfer test protocol.md`](<transfer test protocol.md>), [`channel selection protocol.md`](<channel selection protocol.md>), [`lifetime earnings protocol.md`](<lifetime earnings protocol.md>), [`ending types protocol.md`](<ending types protocol.md>).
- [`src/`](src/): the model, the scoring pipelines for every test and the measurements.
- [`data/`](data/): every test's draws, scores, outcomes and results, by version (`confirmatory`, `v2`, `v3`, `v3 reanalysis`, `v3 exploratory`, `meta channel`, `transfer test`, `v4 channels`, `ending types`, `openings and closures`, `item 13`, `panel`).
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
