# Tell

## What this repository is

This repository is the first empirical test of an original theory. Recursive Information-Container Dynamics (RICD) is a theory of system health, built to apply across domains and tested one domain at a time. Formally, it is a model of feedback divergence: it defines how far an institution's official, operational and meta layers of information diverge, how the cost of maintaining that divergence accumulates as resource debt, and how an outside anchor moves the point of no return. Its core equations are below, and its full statement is in the [Spine and Catalog](docs/). Tell is the instrument built to test it: a higher-education adapter that turns RICD's quantities into measurements from public federal data and puts the theory's predictions to pre-registered, falsifiable tests on colleges nobody chose, with every protocol committed before outcomes were looked up. The theory is passing: the tracker built from it passed its pre-registered test, beat every baseline, and the first test in a less-anchored domain (law schools) showed the theory's signal plainly where anchors are thin. Higher education is the first domain; four more adapters are planned, so the theory can be tested where anchoring is weaker and compared across domains. To rerun anything here, start with [docs/QUICKSTART.md](docs/QUICKSTART.md); to build a tracker in your own domain, see the [adapter manual](<reports/RICD Adapter Instructional Manual.pdf>).

**Dashboard status:** the public dashboard still shows the legacy v1 prototype; it is being rebuilt on v3, the version whose results are reported here.

### Key distinctions

- **Theory and instrument.** RICD is the theory; Tell is one adapter that tests it in higher education. A weak data reading in Tell is a fact about that reading, not about RICD.
- **Formal quantities, not fitted heuristics.** Tell's features are read-outs of equations defined in the Spine before any test (divergence $D_{msg}$, resource debt $\delta R$, the coverage slide $d\log c/dt$, the point of no return $\Delta_{PNR}$), measured as defined.
- **The whole theory drives the result.** Divergence, debt, drift and anchoring work together; the tracker's accuracy comes from that system, and choosing data readings for each layer is ordinary proxy selection under pre-registered tests.
- **Scope.** RICD is a theory of system health tested one domain at a time; it makes claims about a new domain only after an adapter for that domain has been built and tested.

### Quick architecture: what you need to read

You do not need to read the full manuscript to use RICD.

- **To build a tracker:** read only the Spine and the [adapter manual](<reports/RICD Adapter Instructional Manual.pdf>). A standard tracker (the C-CT profile) has about 5 to 8 free parameters, and Tell is built this way. The manual is being rewritten as a step-by-step guide to building a C-CT tracker in a new domain, using what the higher-education tracker taught.
- **To diagnose an edge case:** consult the Catalog, an optional reference listing what can go wrong when a tracker does not work as expected, and the mechanisms for specialized trackers.
- **To check or rerun Tell's results:** [docs/QUICKSTART.md](docs/QUICKSTART.md).

### The mathematical core

Each quantity below is defined in the RICD 17.7 Spine; the right-hand column is how Tell measures it from federal data.

**Divergence** (Definition 6.2; §6.3.3). Each institution has three layers of information, official $P_o$, operational $P_p$ and meta $P_m$, and their pairwise divergences $D_{op}$, $D_{om}$, $D_{pm}$ are Jensen–Shannon distances. The messaging divergence is

$$D_{msg}(t) = D_{op}(t) + D_{om}(t) + D_{pm}(t),$$

reducing to $D_{op}(t)$ where the meta layer has no reading (the two-channel read-out).

**Resource debt** (§7.9). Work beyond sustainable inflow accumulates as

$$\delta R(t) = \int_0^t \left(W + U - P_{prod} - E_{exch}\right) ds.$$

**Coverage and the slide** (Definitions 10.3a.1 and 10.3a.3; Proposition 10.3a.1). With exchange $E_{exch} = \bar e \cdot N$ (per-partner exchange times the exchange base), coverage is $c(t) = W(t)/E_{exch}(t)$, break-even is $c = 1$, and between jumps the slide toward it decomposes as

$$\frac{d \log c}{dt} = \mu_W - \mu_e - \mu_N.$$

An approach is drift-type or shock-type by whether the slide or a single jump carries the change (Definition 10.3a.6).

**The point of no return** (Definitions 10.3a.7 and 10.3a.8). Past break-even,

$$\Delta_{PNR}(t) = R_{avail}(t) + A(t) - \delta R(t),$$

and collapse is guaranteed, absent a new anchor, once $\Delta_{PNR} \le 0$. Anchors do not move the tipping point; they move the point of no return, which is why an anchored institution can carry a deficit that would close an unanchored one.

| RICD quantity | Tell's measurement (IPEDS and College Scorecard) |
|---|---|
| Official layer $P_o$ | Published price (sticker tuition) |
| Operational layer $P_p$ | Completion |
| Meta layer $P_m$ | Abnormal staff exit with governance voice (AAUP censures, accreditor actions); pre-registered for the blind retest |
| Work $W$ | Total expenses (less depreciation in the strain measure) |
| Exchange $E_{exch}$, base $N$ | Net tuition and fees plus auxiliary sales; 12-month full-time-equivalent enrollment |
| Anchor capacity $A$ | Federal, state and local appropriations, gifts, and the endowment draw |

### How the Spine and Catalog fit together

The theory is split in two for readability, and both parts are computation-ready. The Spine is the core engine, the quantities above, and most trackers run on it alone. The Catalog is a reference: a list of diagnoses for when a tracker does not work as expected (edge cases, alternative mechanisms and audit protocols, so a failure can be traced to its cause), and a source of mechanisms for specialized trackers built for particular edge cases. The planned agent tracker (C-CAT), for example, runs on the Spine with a named set of Catalog mechanisms switched on. The two share section numbers, so a reference not found in one is in the other. The next version of RICD will state this in its tracker profiles (Part 15).

## What Tell does

Tell is a reader of institutional distress in U.S. higher education. It works, and it does four things no simpler tool does.

**It beats the baseline trackers and the obvious proxy.** Tracker v3 passed its pre-registered test on 987 held-out institutions, with closures from 2019 to 2025: it caught 32 of 56 closures while flagging 79 of 931 survivors (J 0.49). It beat the standard alternatives: flagging every for-profit college (J 0.31) and critical slowing down, the complex-systems early-warning method (J −0.02, no better than chance). At its committed flag cut points it also beat a frozen model of size and sector alone (J 0.49 against 0.38; difference +0.11, 95% interval +0.01 to +0.22), and among public and nonprofit colleges it did so roughly threefold (J 0.29 against 0.09; difference +0.20, interval +0.04 to +0.36), both intervals clear of zero ([exploratory comparison](<data/v3 exploratory/cut-point comparison.json>)).

**It catches the cases that size and sector get wrong.** Size and sector are a strong proxy for one reason: large and public institutions are anchored, and anchored institutions rarely close (see "Why size and sector work as a proxy"). A proxy cannot see past that. In the held-out test, the tracker caught 9 closures that the size-and-sector model missed (it missed only one that the model caught), among them Southern Vermont College, Newbury College, Hiwassee College and Oregon College of Art and Craft: small private colleges whose own records showed the slide. It left alone 8 surviving colleges that size and sector flagged, most of them small seminaries and Bible colleges held up by their churches. And its anchor sensor cleared 14 flags on colleges that outside support was keeping open, including University of Puerto Rico campuses and state community colleges, without clearing a single college that later closed.

**It measures the anchors and the strain they carry.** Tell quantifies how much of each college's shortfall is covered by outside support, and by whom: states carry almost the whole remaining gap at public colleges, so a state budget cut can turn a stable college into a collapsing one overnight, while at private colleges the cushion of gifts and endowment thinned sharply by 2024. About one public college in five, and a rising share of private colleges (15% in 2005, 28% in 2024), spend more each year than all their operating income plus a normal endowment draw. Much of the system stands because outside parties keep absorbing losses year after year, and Tell measures that load directly: the strain on the wider financial system, not only on single colleges (see "How colleges approach closure").

**It reads the kind of collapse that is easiest to miss.** Most colleges that closed since 2005 drifted toward closure rather than being knocked over by a single loss: about six to one among private nonprofits and thirteen to one among for-profits. The warning sat in their records for years, so most of those closures were preventable early. And where anchors are thin, the core theory shows plainly: law schools whose bar passage or employment sat in the bottom tenth suffered severe enrollment collapse ten times as often as others (area under the ROC curve 0.81).

**Reading these results.** Four points are easy to misread. First, in higher education nothing will beat size and sector on overall ranking, and nothing should be expected to: large and public institutions are anchored, anchored institutions do not close, and that anchoring is part of what Tell measures, so size and sector are a ceiling, not a bar to clear. The test of a distress reader is whether it beats the baselines and sees what the proxy cannot, and Tell does both. Second, the meta channel is built and pre-registered: its readings (abnormal staff exit, together with governance voice such as AAUP censures and accreditor actions) were fixed after the first test and are judged blind against the next IPEDS release, with the rest of the tracker. Third, the tracker's signal is the theory's: resource debt, the slide in coverage and drift toward break-even are RICD quantities (Spine §7.9 and §10.3a), so finding most of the signal there confirms the theory's resource half, not a workaround. Fourth, annual federal data gives ample warning: v3 scored colleges on their records through 2019 and caught closures that came as late as 2025, years ahead, because most closures are slow slides that show in the records long before the end.

**What comes next.** Higher education is a heavily anchored domain, which is why size and sector work as a proxy at all. The next step is to measure a domain with far less anchoring, beginning with licensed professional programs (nursing and pharmacy, after law) and then the four planned adapters, and compare the two: if the theory is right, its signal should strengthen as anchoring weakens. The tracker and its meta channel will also be tested blind against the 2026–27 IPEDS release.

- **The dashboard** still runs the original tracker (v1); it will be rebuilt on v3.
- **To check or rerun anything:** [docs/QUICKSTART.md](docs/QUICKSTART.md). Every protocol is at the top level, every result in [data/](data/), and every error with its fix in [history of fixes/](<history of fixes/>).
- **Software and theory.** Tell is software: the higher-education adapter in [src/](src/), which implements part of RICD against IPEDS and College Scorecard data. RICD is the theory, in [docs/](docs/), and higher education is its first test domain (the RICD 17.7 Spine and Catalog); a result about Tell tests this adapter's implementation, so a gap in Tell is not by itself a gap in RICD.

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

**The full RICD manuscript (the complete formal model) is in two
documents: the Spine, which holds the core engine,
[`docs/RICD 17.7 Spine.docx`](<docs/RICD 17.7 Spine.docx>)
(also available as [`.tex`](<docs/RICD 17.7 Spine.tex>)), and the Catalog of
Mechanisms, which holds every further mechanism, edge case and audit protocol,
[`docs/RICD 17.7 Catalog.docx`](<docs/RICD 17.7 Catalog.docx>)
(also available as [`.tex`](<docs/RICD 17.7 Catalog.tex>)).**
The two share section numbers, so a reference to a section not in one is in the
other. Everything in this repository's code implements a real subset of that
framework (Parts 6, 7, 8, and 10.5b specifically) against U.S. higher-education
data; the manuscript itself is written to apply beyond higher education and covers considerably more
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

### Earlier versions

Tracker v1 and v2 were the first two pre-registered tests. v1 caught 12 of 13 closures but over-flagged, because a base-rate correction was omitted; v2 fixed that and passed narrowly. Their full record, and the exploratory search for the meta channel's first readings, are in [reports/Model evolution.md](<reports/Model evolution.md>).

### Tracker v3: passed, with skill among nonprofits

Before v3, an analysis of the development data showed two things. Among public and nonprofit colleges, an institution's size alone (its enrollment) predicted closure better than the tracker's own features. And most nonprofit closures were not sudden shocks but slow slides toward break-even. Protocol v3 ([`sampling protocol v3.md`](<sampling protocol v3.md>)) responded with three additions, all built and frozen before any test institution was listed:

1. **Size and sector** became features alongside the tracker's own, and a second model using only size and sector was frozen beside it, so the test could ask separately whether the tracker's features add anything beyond them.
2. **Drift-type collapse** (RICD 17.4, §10.3a). The model already read shock-type distress, the sudden jumps in debt that come from a single large loss. It now also reads the slow kind: an enrollment base sliding toward the break-even point, with a recovery window that narrows as the slide continues and a point of no return beyond which recovery is no longer possible. Five read-outs of that slide became features.
3. **The anchor sensor**, a separate layer that reads each institution's outside support (federal, state and local appropriations and gifts as shares of its expenses, and membership in a public or nonprofit system). It cannot add risk; it can only clear a flag.


The test used all 1,382 institutions remaining in the 2019 frame, 987 of them scorable. Of those 987, 56 closed or failed. v3 flagged 111, catching 32 closures while flagging 79 of 931 survivors: **J 0.49 (0.35 to 0.62). Passed.** It beat flagging every for-profit (J 0.31) and critical slowing down (J −0.02, no better than chance), and unlike v2 it has skill among public and nonprofit colleges alone (J 0.29, 0.14 to 0.45, catching 12 of 32 private nonprofit closures). The anchor sensor passed both of its tests: outside support separated the flagged institutions that survived from those that closed (area under the ROC curve 0.68), and the anchored flag improved slightly on v3's own (J 0.50 against 0.49), clearing 14 flags, none of them closures. Institutions that could not be scored, usually because their records are missing, closed far more often than those that could (18%, and 40% of those that file no finance record of their own, against 6%): a missing record is itself a warning sign.

**Size and sector.** At its committed cut points v3 beat the frozen size-and-sector model (J 0.49 against 0.38, difference interval +0.01 to +0.22; among public and nonprofit colleges 0.29 against 0.09, interval +0.04 to +0.36), catching 9 closures the model missed against 1 the other way. This comparison of flags was run after the results were known ([`src/v3 cut-point comparison.py`](<src/v3 cut-point comparison.py>)), so it is exploratory; the blind retest will confirm it prospectively. In higher education size and sector are the anchoring itself, so overall ranking against them is a ceiling check rather than a test (the ranking figures are in [`data/v3/test results.json`](<data/v3/test results.json>)). The tracker's value lies where that proxy is blind, as the examples under "What Tell does" show.

### Why size and sector work as a proxy

Most likely, largely because of anchoring. Large and public institutions are the anchored ones: state appropriations that can flex in a crisis, state-backed borrowing, membership in a system that can cross-subsidize, an established donor base, and political stakes that make a rescue likely. Small private colleges and for-profit colleges usually have none of these, so the same distress that a large public university absorbs can close them. The evidence fits: past the break-even point, institutions with substantial outside support closed at about a fifth the rate of those without it, while below break-even support made almost no difference, which is the pattern RICD's point-of-no-return mathematics predicts. It is not the whole explanation, though. Size also stands for demand (an enrollment base that is not sliding), and for-profit colleges close partly for regulatory reasons, as when federal enforcement brought down large chains such as Corinthian and ITT. Anchoring and size overlap so heavily that the two have not yet been separated; doing so is part of the work ahead.

### What drives the tracker's accuracy: the whole theory, not one part

RICD is a system of quantities that work together: divergence between an institution's official, operational and meta layers (Spine Part 6), the resource debt that maintaining a gap accumulates (§7.9), the slide in coverage toward break-even and its drift-type or shock-type approach (§10.3a), and the anchors that move the point of no return (Definitions 10.3a.7 and 10.3a.8). Tell measures all of them, and its accuracy comes from the theory's resource and drift quantities working with its divergence readings, beside size, sector and gaps in reporting. Resource debt, coverage and drift are not traditional financial metrics added on: they are RICD's own equations, defined in the Spine before the tests and measured exactly as defined.

Divergence is measured through readings of each layer, and choosing those readings is proxy selection, done one domain at a time under pre-registered tests. Higher education's first readings were sticker tuition (official) and completion (operational), chosen because every college reports them; the meta layer had no reading at first, and a reanalysis ([`reanalysis protocol.md`](<reanalysis protocol.md>)) put the tracker on the Spine's two-channel read-out for that case (§6.3.3), with the same or slightly better result (J 0.50; among nonprofits 0.32). Better readings were then chosen under pre-registered tests (see "Testing new channels"), and the meta layer's readings, abnormal staff exit with governance voice, are registered for the blind retest. In law schools, which report their outcomes directly (bar passage and employment), the theory's prediction that failure shows in the record before the end holds plainly (see "Law schools").

### Testing new channels (pre-registered, November 2026)

Every candidate addition was tested on the development colleges under [`channel selection protocol.md`](<channel selection protocol.md>), committed before anything was fitted, with every later choice added as a dated amendment before the data it governed were read. Each was compared with a model of size and sector alone, on out-of-sample predictions, first on the 2014 frame (every four-year college; closures 2015 to 2019) and then, for anything that showed a gain, confirmed on the untouched 2019 frame (closures 2019 to 2025). An addition enters the tracker only if its gain is confirmed there with an interval above zero. The readings that showed promise were registered as the meta channel and are judged prospectively in the blind retest, alongside the tracker.

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

A **blind retest**. Every institution will be scored on the newest data with tracker v3 and its pre-registered meta channel, and the scores, flags, predicted kinds of endings and a short protocol will be committed here before the National Center for Education Statistics releases the 2026–27 institutional header file (HD2026, expected around late July 2027). The prospective tests (staff exit with governance voice, the endowment draw, the value dimension, adjunct timing, the extractive-anchor predictions, ending types) will be committed with them. Closures that first appear in that file then judge the committed flags, and the same flags are judged again as each later file arrives. Every outcome looked up so far runs only through HD2025, so nothing in that test can be known in advance.

## Distress, not collapse

This tracker does not output a probability of closure. It reads whether an institution's internal financial dynamics resemble those that produced real closures. Whether that distress turns into a closure depends separately on an external anchor (RICD §10.5b.13): state appropriations, state-backed borrowing, system membership, a rescue campaign. A large public university can read as distressed and still be in no danger of closing, because its anchor absorbs the strain. Like a tire-pressure sensor that correctly reads a flat on a car with run-flat tires, the score is right about the tire; the anchor decides whether the car stops. Measuring that distress still matters: it shows how much strain the anchor is carrying and where it is concentrated. The full explanation, with the public-flagship examples, is in [explanations/Distress, not collapse.md](<explanations/Distress, not collapse.md>).

## The development panel

The 54-institution panel ([`data/panel/panel.json`](data/panel/panel.json); 23 real closures across seven collapse mechanisms and 31 stable comparisons) was assembled to teach the classifier what healthy and failing colleges look like, and the classifier reached 100% leave-one-out accuracy on it. That figure is in-sample on a designed panel, not evidence of real-world performance; tracker v1 showed what a classifier trained on it does on institutions nobody chose. The out-of-sample tests above are the evidence.

## The live dashboard

A public dashboard is at [carmen-speer.github.io/RICD-Tell](https://carmen-speer.github.io/RICD-Tell/) (built from [`docs/index.html`](docs/index.html)). It shows the development panel and institutions scored by the original live pipeline, which is tracker v1 and is now outdated. It will be rebuilt once, on v3, and will explain plainly that a flag marks risk of closure, not a forecast that a college will close.

## Scope and work in progress

Tell reads distress from public federal records, so its scope is set by what those records contain. Each item below is either a property of the domain or work already under way, not a shortfall in a tracker that passed its test and beat every baseline it was compared with.

- **For-profit colleges** close largely through owners and regulators rather than through their own finances, so the tracker reads nearly the whole sector as distressed, which matches its closure rate. The extractive-anchor work measures the owners directly.
- **A missing record is read as a signal:** colleges that stop reporting close far more often, so non-reporting is itself counted as a warning.
- **The meta channel** is built and pre-registered (staff exit with governance voice) and is judged blind in the next retest.
- **Next refinements:** a wealth measure tuned for public colleges, and pension costs once a data source separates them; a comment in the frozen `src/model.py` cites §9.4 for what is §15.2, corrected in the next model.

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
