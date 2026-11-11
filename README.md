# Tell

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
project, covered in full in
["Distress, not collapse"](#distress-not-collapse-what-an-elevated-score-means-for-a-public-flagship)
below. Read that section before concluding that an elevated score for a
large, well-resourced institution is either an error or a limitation.

Tell is a Bayesian state-space model and validated classifier for
institutional financial collapse risk **and** degree of financial
distress in U.S. higher education, built on the Recursive
Information-Container Dynamics (RICD) framework. It was developed under
the working name "RICD Higher-Education Collapse Tracker"; Tell is its
name now that what it actually reads -- a real signal in the data, not a
prediction of an outcome -- is the more accurate description of what it
does.

**The full RICD manuscript (the complete, domain-independent theory) lives at
[`docs/RICD 16.1 manuscript.docx`](<docs/RICD 16.1 manuscript.docx>)
(also available as [`.tex`](<docs/RICD 16.1 manuscript.tex>)).**
Everything in this repository's code implements a real subset of that
framework (Parts 6, 7, 8, and 10.5b specifically) against U.S. higher-education
data; the manuscript itself is domain-independent and covers considerably more
than the tracker uses.

**Provenance materials** -- the framework's original source documents, its
earlier versions, and the full verification record (an integration manifest
quoting the exact manuscript text for every mechanism confirmed built into the
framework) -- are archived separately and available on request.

**The narrative, findings, and process record of how this tracker was built
live in [`reports/`](reports/):** [`RICD Tracker Findings Final.pdf`](<reports/RICD Tracker Findings Final.pdf>),
[`RICD Tracker Narrative Final.pdf`](<reports/RICD Tracker Narrative Final.pdf>), and
[`RICD Tracker Process Log Final.pdf`](<reports/RICD Tracker Process Log Final.pdf>) --
the findings document, the narrative account of how each result was actually
reached, and the consolidated process log -- alongside
[`Higher Ed Sector Findings.pdf`](<reports/Higher Ed Sector Findings.pdf>) (a
separate analysis of what the results imply about the U.S. higher-education
sector as a whole), and [`RICD Adapter Instructional Manual.pdf`](<reports/RICD Adapter Instructional Manual.pdf>) (an instructional manual for
engineers working with the RICD adapter contract directly).

**Not-yet-built or not-yet-funded work lives in [`future-projects/`](future-projects/):**
[`Next Project for RICD - Four Adapter Build Roadmap.pdf`](<future-projects/Next Project for RICD - Four Adapter Build Roadmap.pdf>)
(a proposed one-year build plan for four new RICD tracker adapters --
banking, hospitals, public schools, and nursing homes/long-term care --
chosen for having both large public datasets and realistic commercial
application, prepared for grant application documentation),
[`RICD Ongoing Projects Roadmap.docx`](<future-projects/RICD Ongoing Projects Roadmap.docx>)
(the broader roadmap of further RICD-based trackers planned beyond the four
adapters and the higher-ed tracker in this repository),
[`Collapse-Causal Agent Tracker (C-CAT) Seed Note.pdf`](<future-projects/Collapse-Causal Agent Tracker (C-CAT) Seed Note.pdf>)
(a seed note for a genuinely different kind of tracker: an agent tracker,
investigating the specific real decisions and agents behind a collapse --
board minutes, depositions, investigative findings -- rather than the
aggregate financial and enrollment effects the higher-ed tracker measures),
and
[`Anchor-Quantification Sensor - Seed Note.md`](<future-projects/Anchor-Quantification Sensor - Seed Note.md>)
(a proposed quantification of anchor-eligibility -- external support
capable of preventing collapse without appearing in the classifier's own
math -- planned to run alongside the validated 8-feature panel and
cross-reference against it rather than merge into it; see "Tell's
Upcoming Project" below for the full summary).

**Two related projects live in their own repositories**, since they draw on
RICD but are not part of Tell:
[Plurimo](https://github.com/carmen-speer/plurimo), a teaching-optimization
platform for private tutors and independent educators whose site-health
monitoring and anti-capture/anti-trolling detection are designed around RICD,
and which would depend on RICD first being tested against real data in further
domains; and the
[Web–Field Model of Cognitive Trait Distributions and Social Evolution](https://github.com/carmen-speer/web-field-model),
an early-stage application of RICD's mathematics to human cognitive traits,
modeling them as regions on a continuous manifold rather than discrete types
and proposing a learning-style metric, the Cognitive Trait Manifold Ratio
(CMTR).

The planned future tracker mentioned above is an
**agent tracker**, which would investigate the specific real decisions and
agents behind a collapse (board minutes, depositions, investigative
findings), rather than the aggregate financial and enrollment effects this
higher-ed tracker measures. The two are complementary, not competing —
see the seed note itself for why an agent tracker needs a different kind of
evidence entirely, and why it wasn't attempted here.

## What this is

A real, working pipeline — not a report about known outcomes — that:

1. Models an institution's official and operational representations as
   latent stochastic processes (`src/model.py`), including a genuine
   shock-type latent process for debt (`src/jump_diffusion.py`), since
   debt behaves as long stable stretches punctuated by rare large jumps
   rather than continuous drift.
2. Extracts eight validated, independently-tested features from real
   IPEDS data: informational trajectory (d_A trend and endpoint),
   resource debt severity and its own trend (δR, δR-trend), a debt-spike
   signature, a regime-classification fraction, scale-normalized reserve
   adequacy (endowment relative to enrollment, not to debt — see the
   note on that below), and a research-to-instruction expenditure ratio.
3. Applies a direct External Governance Attestation override for
   institutions with a real, independent, confirmed governance verdict
   (an accreditor's show-cause order or withdrawal), bypassing the
   statistical classifier entirely for those cases rather than fitting
   it as a weighted feature — confirmed empirically to be the correct
   approach (`src/classifier.py`).
4. Detects shared external shocks across the panel from cross-sectional
   co-movement alone (`src/common_cause.py`), run on raw adapter-level
   data rather than model output, since latent-variable smoothing
   washes out exactly the sharp signal this diagnostic needs.

## Validated result

100.00% leave-one-out cross-validated accuracy on a real, 54-institution
panel (23 confirmed closures spanning seven distinct collapse
mechanisms, 31 confirmed-stable comparisons), with zero misclassifications.
Reproduce this directly:

pip install -r requirements.txt
cd src
python -c "
from classifier import RICDClassifier, load_panel
panel = load_panel('../data/panel/panel.json')
clf = RICDClassifier()
acc, misclassified = clf.leave_one_out_accuracy(panel)
print(f'Accuracy: {acc:.2%}')
print(f'Misclassified: {misclassified}')
"

**What that 100% figure is actually a statement about, checked directly rather than left implicit:** of the panel's 23 confirmed closures, only 2 (Northland College, King's College NY) are classified via the direct External Governance Attestation override described above — the other 21 are correctly classified by the fitted statistical model itself, not exempted from it. So the 100% accuracy claim is overwhelmingly a statement about the classifier, not about the override rule doing the real work. Separately, `reserve_adequacy`'s coefficient — the largest-magnitude one in the model — is stable across all 52 real leave-one-out refits that actually pass through the fitted model (the 2 override folds never do): it stays in a tight -1.79 to -1.93 band around its full-panel value of -1.88, and none of the eight features flip sign in any of the 52 folds. No single institution's removal is quietly driving the result. This is a real answer to "is the panel too small/one feature too dominant for this to be trustworthy," not a claim that it resolves the separate, still-open gap below: coefficient stability says the fit isn't fragile to which institution gets held out; it says nothing about whether `reserve_adequacy` is well-calibrated against real public-sector distress, which it structurally is not (see Known Gaps).

**A live public dashboard is at
[carmen-speer.github.io/Recursive-Information-Container-Dynamics](https://carmen-speer.github.io/Recursive-Information-Container-Dynamics/)**
(built from [`docs/index.html`](docs/index.html) via GitHub Pages), showing
both the validated 54-institution panel ([`docs/data/panel.json`](docs/data/panel.json))
and, in a separate section below it, real institutions scored live by the
pipeline described in Known Gaps below ([`docs/data/live_scores.json`](docs/data/live_scores.json)).

## Tell's Upcoming Project

**First: a confirmatory out-of-sample test on 300 institutions nobody
hand-picked.** The 54-institution panel above was designed to be
representative, not random, so its 100% leave-one-out accuracy shows the
classifier is internally consistent; it does not show how the classifier
performs on institutions no one chose. The rules for that test were fixed
in [`sampling protocol.md`](<sampling protocol.md>) and committed before any
institution was drawn or scored: systematic sampling from the IPEDS 2019
institutional header file (public, private nonprofit, and private for-profit
four-year, degree-granting institutions, ordered by UNITID); a collision rule
that skips panel and pilot institutions; an insufficient-data rule under which
any institution that fails a data, convergence, or three-seed stability check
is skipped and replaced, never debugged; scoring on fiscal year 2019 data only,
with the classifier frozen; and scores committed before any outcome is looked
up. The 16 live-scored institutions from earlier are reported separately as an
exploratory pilot, not pooled into the test.

The draw itself is done and committed
([`data/confirmatory/`](data/confirmatory/), drawn by
[`src/draw confirmatory sample.py`](<src/draw confirmatory sample.py>)): a
frame of 2,876 institutions, a step size of 9, and 300 institutions selected
(90 public, 171 private nonprofit, 39 for-profit), with 13 collisions
(11 panel, 2 pilot) skipped and logged, and 25 ordered backups recorded for
every slot. Scoring comes next, applying the insufficient-data rule slot by
slot; the results will then be checked against which institutions actually
closed or merged after 2019, and compared head to head against the standard
critical-slowing-down early-warning indicators (rising variance and
autocorrelation) on the same data.

**Alongside it: anchor quantification.**

**A separate anchor-quantification sensor is now being built as its own
project, planned to run alongside Tell's validated 8-feature panel and
cross-reference against it -- not merged in as a 9th feature.** Tell's
manuscript already establishes a two-layer distinction between internal
financial distress (what the classifier above measures) and an
institution's anchor eligibility -- external support such as state
appropriations, state-backed debt, or a rescue campaign, capable of
preventing collapse without appearing anywhere in the classifier's own
math (see "Distress, not collapse" below). So far that distinction has
been qualitative, real and load-bearing but not measured; this project is
that measurement. It's being built separately because there's no real
anchor-failure/closure data anywhere to fit a coefficient against -- the
same structural data-scarcity problem already documented for
`reserve_adequacy`'s public-sector gap in Known Gaps below -- so folding
an unvalidated coefficient into the panel's own fitted classifier would
be exactly the kind of unverified change this project doesn't make. The
combining math isn't a blank slate either: RICD's own Proposition
10.5b.13.1 already defines a fitted additive correction combining a
container's own margin with a separately-computed anchor term, the same
shape this sensor's output will take against Tell's classifier score,
adapted for one-directional anchoring rather than the mutual case the
proposition was written for. Sweet Briar College and University of
Phoenix-Arizona are the two live test cases, chosen because they diverge
sharply in their real outcomes -- a resolved philanthropic rescue versus
an unresolved ownership restructuring -- while both currently read as
thin or flat under the panel's own experimental recovery-detection
feature (see Known Gaps below); if anchor quantification separates them
the way their actual outcomes suggest it should, that's real
corroborating evidence for the approach, and if it doesn't, that's a real
negative result worth stating plainly.

Full detail -- including the live panel's own institution count (15
scored so far of 50 planned, distinct from the 54-institution validated
backtest panel below) and exactly what's not yet built -- is in the seed
note:
[`Anchor-Quantification Sensor - Seed Note.md`](<future-projects/Anchor-Quantification Sensor - Seed Note.md>).

## The panel is a validation set, not a survey

The 54 institutions in `data/panel/panel.json` were assembled specifically
to test the classifier, including a deliberate rebalancing pass mid-project
after an audit found the panel had drifted toward roughly three times the
real-world rate of dramatic, easily-searchable closure cases. Nothing here
should be read as a claim about what fraction of U.S. higher education is
at risk. It supports a narrower, real claim: these specific mechanisms and
relationships showed up clearly enough in independently-verified data to
resolve a hard classification problem.

## Distress, not collapse: what an elevated score means for a public flagship

**Before reading any score below: this tracker does not output a
probability of closure.** It outputs a classifier's raw read of an
institution's internal financial dynamics -- whether they currently
resemble the panel's real closures. Whether that internal distress
converts into an actual closure is governed separately, by a documented,
pre-existing external-anchor mechanism (§10.5b.13), and the classifier
deliberately does not fold that mechanism into its own number. That is
not an unfinished integration waiting to happen; merging the two would
erase the distinction the two-layer design exists to preserve. A
tire-pressure sensor that reads 0 PSI after a blowout is not wrong, and
it is not "failing to account for" the car's run-flat tires -- it is
correctly reporting the tire, while a separate system (the run-flat
capability) determines whether that failure actually stops the car. The
classifier is the sensor; the anchor is the run-flat capability. When a
large public university scores `high_risk` below, read it the same way:
a correctly identified internal shock, at an institution whose separate,
real anchor status is a documented fact about that institution (see the
anchor status shown for each institution on the live dashboard), not a
property this number was ever built to include.

**Read this first if you're forming a judgment about this project from an
elevated flagship score.** This is not a flaw in the classifier, not a
workaround, and not a patch added after the fact to explain away an
inconvenient result. The anchor eligibility criterion (§10.5b.13) that
explains why an anchored institution's real, elevated distress does not
convert to collapse was written into RICD's core theory *before this
tracker was ever built* -- the original manuscript explicitly anticipated
that a high-entropy, externally-anchored system would show real divergence
without collapsing, and gave that pattern a name and a formal treatment
well in advance of any specific institution's live score triggering it.
When the classifier flags UCF or FSU as `high_risk`, it is doing exactly
what it was built to do: correctly detecting a real liability shock. The
theory, not a bolted-on exception, is what explains why that correctly-
detected shock doesn't mean the university is closing. Reading a score
like that as "the model is broken" or "the model doesn't apply to
flagships" gets it backwards -- collapse risk and distress are two
different, both-intentional things this project measures, not one thing
the project does well and a workaround for cases where it doesn't.

The classifier's job is to catch collapse, not distress; a few
institutions which are not at risk of closing nevertheless score elevated
because they carry real financial strain, yet they have structural
support preventing their collapse (read on for further detail). The
anchor eligibility criterion is a pre-existing RICD formalism (§10.5b.13)
which describes how an external anchor may prevent collapse even in
high-entropy systems; the anchoring mechanism was written into RICD's
core theory prior to the building of this tracker to catch precisely this
pattern when assessing collapse risk in systems showing divergence.

Florida State (65.03%) and UCF (85.11%) are the live scores this applies to:
real, currently-elevated `high_risk` scores -- elevated relative to a
stable flagship like Michigan (5.8%), comparable instead to Houston's
pre-fix reading. In both cases the classifier is working exactly as
intended, correctly detecting a real, sizable jump in reported
liabilities; each institution holds what RICD's own framework formalizes
as an external anchor (§10.5b.13, Anchor Eligibility): a structurally
distinct system that absorbs a shock so the anchored container doesn't
have to, whether by a vigilant neighbor actively maintaining zero
extraction flux toward it, a structurally inert boundary with nothing to
extract, or a purpose-built buffering structure sized to its designed
capacity.

For a public university flagship, that anchor is rarely one single thing;
it typically has several concrete, independent parts: direct state
appropriations able to flex upward in a crisis (a subsidy channel no
tuition-dependent private college has); state-backed or state-supported
borrowing, which changes both the cost and the systemic risk of new debt
relative to an institution borrowing on its own unsupported credit;
political stakes large enough to make intervention likely rather than
hypothetical, since a flagship's closure is a state-level event no
legislature wants attached to its name; revenue diversified well beyond
tuition (sponsored research, hospital and clinical operations, athletics
revenue); system-level cross-subsidization across a multi-campus public
system, which no freestanding private college has access to; and a large,
stable in-state applicant base insulated -- though not immune, see Cal
State Long Beach below -- from the demographic pressure driving
small-college enrollment collapse. None of the panel's real closures had
access to anchors like these, which is exactly why the eight features were
built and validated against institutions that didn't have them, not
flagships that do.

Florida State's and UCF's scores are a further, independently confirmed
instance of the same structural point, not just an analogy. FSU's $437M
athletics-related debt and UCF's $144M student-housing bond are each
structured as project-specific revenue bonds, not general obligations of
the university: FSU's is secured only by athletics-department revenue and
Seminole Boosters membership fees and capital gifts, and UCF's only by net
revenues of its own housing system, with each bond program's own governing
documentation stating explicitly that "these bonds do not constitute a
general obligation of the State of Florida or the University, and the full
faith and credit of the State of Florida is not pledged to payment"
(Florida State Board of Administration bond-finance program pages for each
issue). A default on either bond would stress that specific auxiliary
enterprise -- athletics at FSU, the housing system at UCF -- not the
university's general credit, alongside each institution's otherwise-stable
overall bond rating (Florida Board of Governors filing, 2/27/26). This is
the mechanism behind the "real but bounded problem" framing used throughout
Known Gaps below, not an assertion; it's checkable against each program's
own bond documentation.

**Clemson and West Virginia are a different case, not a milder version of
this one, and don't belong under this mechanism.** Both carry real,
seriously documented financial distress -- Clemson's $2.65B in long-term
liabilities, up $231.9M year-over-year; West Virginia's real 2023
financial crisis and program/faculty cuts -- and both are currently scored
`stable` (37.58% and 41.63%), not elevated: the opposite direction from FSU
and UCF. That is not the anchor mechanism above at work. An anchor
explains why a shock the classifier *did* detect doesn't convert to
collapse; Clemson and West Virginia's distress was never detected as
elevated risk in the first place. Clemson's `frac_high_entropy` measured
0.0000, and its full 8-feature vector sits closest to other confirmed-stable
flagships in feature space, not near any real closure -- the same scale
mismatch already documented for `reserve_adequacy` (a liability increase
that would be extreme for a small private college is ordinary at flagship
scale), extending here across the feature vector as a whole rather than
one feature alone. West Virginia's `stable` call rests on a different
mechanism again -- the fitted classifier's own feature weighting settling
a genuinely mixed peer comparison -- detailed in full in Known Gaps below.
Both are real, checked resolutions, not smoothed-over gaps, but they answer
"why didn't the classifier flag this at all," not "why doesn't this
flagged score mean collapse" -- a different question from the one this
section is about.

An elevated or borderline score anywhere in this project, live or in the
panel, should be read as "this institution's raw financial dynamics
resemble the ones that produced real closures" -- not as a probability of
actual collapse. Whether distress converts to collapse depends on an
anchor this classifier does not measure at all. Buffalo (removed from the
live batch; see Known Gaps below) is a third, further-distinct case, not
an instance of this section's mechanism either: its problem isn't a
missing anchor, it's a kind of strain -- a federal research-funding cut --
that none of these eight features were ever built to detect in the first
place.

What these flagships' real data turned out to show is distress, not
imminent closure, which is prevented by various forms of external
anchoring as described above -- state appropriations, state-backed debt,
political stakes, and diversified revenue among them -- and while that
anchoring could in principle be traced and measured directly for a given
institution, that work hasn't been done yet: the anchor eligibility
criterion accounts for the mechanism, not yet a quantified adjustment to
what the classifier itself outputs (the various forms of anchors have not
yet been mathematically calculated, in other words).

**Measuring the degree of distress at an anchored institution is useful
in its own right, independently of whether closure is ever on the table,
for several concrete reasons -- not as a consolation-prize interpretation
of a score that "should" have meant something else:**

- **It quantifies the load on the anchor itself.** Distress at an
  anchored institution doesn't disappear just because it doesn't convert
  to closure -- it gets absorbed by something: a state legislature, a
  multi-campus system's other institutions, taxpayers. The whole grid
  those anchors are part of carries that strain, whether or not the
  anchored institution itself ever shows up as a closure statistic, and
  the degree of that strain is real, useful information about how much
  the surrounding system is currently being asked to absorb.
- **It distinguishes real variation a binary can't.** "Stable" or
  "high_risk" alone would erase the real difference between a genuinely
  unstressed flagship like Michigan (5.8%) and one carrying serious,
  documented project-specific strain like UCF (85.1%) or FSU (65.0%) --
  both nominally "protected from collapse by an anchor," but not
  remotely the same situation.
- **It localizes exactly where the strain is concentrated** -- FSU's
  athletics-department debt, UCF's student-housing bond -- which is
  specific, actionable information for anyone actually responsible for
  managing these institutions, independent of whether the institution as
  a whole is ever at risk.
- **It functions as an early-warning signal for the real, non-closure
  consequences distress produces on the way to being absorbed** --
  program cuts, tuition increases, deferred maintenance, credit-rating
  pressure on the specific auxiliary enterprise carrying the debt.
  Collapse is not the only outcome worth tracking; these are real costs
  that land on real students, staff, and programs well before -- and
  regardless of whether -- any anchor fully absorbs the shock.

None of this requires collapse to be a live possibility to matter. Whether
this model could *also* double as a full stress-calculator for flagships --
cross-referencing specific anchor types against the specific causes of
distress the 8-feature panel measures, in order to generate
recommendations rather than just a score -- remains a real, open,
not-yet-executed next step (see the note above on quantifying anchor
mechanisms). But that future capability is not a prerequisite for today's
distress-degree readings to already be useful, for the reasons just given.

## Documentation standard for this section (and the live dashboard)

Adopted 2026-09-20, as a standing rule for every entry below and for
`docs/index.html`'s live-interpretation notes: no result is ever left as a
bare "we don't know why." Every open or anomalous result documented in this
project states three things together, not just one or two — (1) whether it
is actively being investigated right now or deliberately deferred, and why;
(2) the specific next diagnostic or fix step(s), not just "needs more
investigation"; and (3) the known or plausible cause, labeled as confirmed
or unconfirmed. A gap that genuinely can't be investigated with current data
gets that limitation stated as its own answer, not silence.

Adopted 2026-09-22, a second standing rule: a term reserved for a
*confirmed, real, historical outcome* (e.g. "closure") is never reused as
the label, CSS class, or variable name for a *predicted* or *flagged*
state, anywhere in this project's code or markup, even when styled
identically. The validation panel's `outcome` field and the word
"Closure" describe real institutions that actually closed; the live
pipeline's `prediction` field and its `high_risk` flag describe the
classifier's live output and are rendered with their own distinct label
(`flagged`, not `closure`) for exactly this reason -- a tool doing
structured extraction on the page, or a person skimming it, should never
be able to read a predicted state as an asserted real-world fact from the
markup alone, independent of the surrounding prose.

## Known gaps — stated honestly, not smoothed over

This is a live, ongoing project, not a finished product, and it's more
useful to state clearly what still needs real work than to imply
everything below is complete:

- **The live-scoring pipeline (`src/score_institution.py`) is confirmed
  working end to end against real, live data** (first successful run:
  2026-09-15, University of Michigan-Ann Arbor, UNITID 170976 -- a real
  classification produced from data fetched live from NCES and the
  College Scorecard API, not from any pre-downloaded local file). Its
  result is saved to [`docs/data/live_scores.json`](docs/data/live_scores.json)
  and shown in a "Live-scored institutions" section on the
  [public dashboard](https://carmen-speer.github.io/Recursive-Information-Container-Dynamics/).
  It still only scores one hardcoded institution per run, as a smoke
  test -- turning this into a tracker that scores a real, broader list
  of institutions on its own schedule is the next real step, genuine
  not-yet-done work, not a configuration problem.
- **IPEDS finance data has no stable API, and its distribution mechanism
  has changed more than once during this project -- now confirmed
  working, not just attempted.** `src/fetch_live_data.py` tries two
  real, live addresses in order: the newest year or two at
  `nces.ed.gov/ipeds/complete-data-files/<table>.zip`, falling back
  automatically to `nces.ed.gov/ipeds/datacenter/data/<table>.zip` for
  older years -- both confirmed directly against NCES's own live pages
  on 2026-09-15, via GitHub Actions (the only environment used on this
  project that can actually reach nces.ed.gov; every sandboxed
  development environment used for this code is blocked from it). A live
  run that same day downloaded all 11 real fiscal years for a real
  institution and produced a real classification. NCES has changed
  this mechanism multiple times before across this project's history
  and may again -- automated re-scoring should still be monitored, not
  trusted blindly forever, but this is no longer an unverified
  assumption.
- **Four institutions in the original research (three small closed
  colleges, one for-profit) have no real endowment data to find** — three
  because it was only located after checking earlier filing years than
  initially tried, one (a for-profit) because for-profit institutions do
  not report an endowment field at all, a genuine structural fact rather
  than a gap.
- **The harder half of the coupling machinery (asymmetric, predatory
  resource extraction between containers, as opposed to a clean merger
  or a mutual-benefit arrangement) has one real, worked instance
  (documented in the manuscript) but has not been validated against a
  full retrospective panel fit** — the subordinate institution's own
  chaotic collapse left no single clean container to test against.
- **The `frac_high_entropy` feature could not distinguish a large positive
  shock from a destabilizing one — found 2026-09-15, fixed at the source
  and validated 2026-09-20, with new open questions from that fix's own
  live re-score (see the end of this item — not a clean resolution).**
  `dynamics.py`'s `rolling_causal_variance()`
  computes plain `.var()` on a channel's first differences, and
  `classify_regime()` compares two of these variances to flag
  "high-entropy" periods; variance is a squared-deviation measure, so
  it is symmetric by construction and cannot represent the *direction*
  of a swing, only its size. Live-scoring University of Houston (UNITID
  225511) surfaced this directly: its `frac_high_entropy` came back
  1.0000 (every one of the last 5 periods flagged high-entropy) against
  exactly 0.0000 for every comparable public flagship already in the
  validated panel (Michigan, UVA, UNC-Chapel Hill, Florida, Wisconsin)
  — yet Houston's real 2025 financial condition is the opposite of
  distressed (S&P upgraded its bond rating to AA+, citing a $287M
  operating surplus and $3.3B in reserves), and the university received
  a real $1.3B infusion from the new Texas University Fund in this same
  period. Live-scoring a further batch (UCF, FSU, University at Buffalo,
  Clemson, Cal State Long Beach) surfaced the same shape of problem: UCF
  and FSU both carry real, confirmed stable bond ratings (Florida Board
  of Governors filing, 2/27/26: UCF Moody's Aa2/Fitch AA stable, FSU
  Moody's Aa1/Fitch AA+ stable, neither on negative outlook) directly
  contradicting high-risk scores driven substantially by this same
  feature.
  **The shape of this problem was identified before it was formally
  diagnosed**, as the same kind of ambivalent signal
  the project had already encountered once before, in the
  facilities-and-athletics-spending and online-enrollment-share proxies
  tested (and rejected) during original feature selection — a magnitude
  that can mean either health or sickness depending on what's actually
  driving it, and that only resolves against corroborating evidence,
  never read alone. The real-time diagnosis, stated directly in the
  project record before Houston's specific mechanism (the state
  windfall) was confirmed: "I bet it's that massive grant, that this is
  just like what happened with sports-and-facilities and
  online-enrollment share, which can indicate either health or
  sickness, depending on whether they are justified and making revenue,
  or indicate divergence between either debt and revenue or between
  tuition and quality of education (which predicts drop in enrollment);
  the signal reads that as noise (could go either way) unless you check
  it against other signs... read alone, it's an ambivalent signal."
  That hypothesis was confirmed correct, and the underlying failure mode
  was formally named **sign blindness**: the math
  correctly detects that a system has been shaken — a real, large
  disturbance in the data — but, from magnitude alone, has no way to
  tell which direction the shake is pushing the system in. The fix
  concept followed directly from that diagnosis: grade positive
  shocks back down toward zero instead of treating every large swing as
  equally alarming, regardless of which way it points — what became, in
  the code, the shift from symmetric variance to a genuinely
  directional, downside-only entropy measure described below. From
  first noticing Houston's anomaly to identifying sign blindness,
  proposing that fix, validating it against the full panel, and
  diagnosing the Clemson/West Virginia fallout it produced, this entire
  arc ran as one continuous, roughly 12-hour push.
  This is not a hypothetical: the validated panel itself
  already contains real closures (Green Mountain, Marygrove, MacMurray)
  sitting at the same 0.8–1.0 `frac_high_entropy` values Houston shows,
  so the fitted classifier had no basis in its training data for
  separating "erratic because collapsing" from "erratic because of a
  sudden windfall." This is the same failure mode already documented
  for the facilities-and-athletics-spending and online-class-share
  proxies (see `reports/RICD Tracker Findings Final.pdf`) — except this
  instance made it into the final 8 validated features rather than
  being caught beforehand.
  **First fix (2026-09-19, since superseded): gated `frac_high_entropy`
  on `debt_spike`'s sign** — zeroed whenever `debt_spike <= 0`. Checked
  against the panel's already-computed features (no live re-fit needed
  for that check) and looked safe: changed exactly 2 of 54 institutions
  (Spelman, Clark Atlanta — both real confirmed-stable, previously
  flagged from debt *declining*, not spiking), leave-one-out accuracy
  held at 100.00%. **Proven insufficient by a real, live re-score run**
  (2026-09-19/20, after the gate was already deployed): Houston, UCF,
  FSU, Buffalo, Clemson, and Cal State Long Beach all still scored
  `high_risk` at essentially the same probabilities as before the gate
  existed — the gate never fired for them, most likely because their own
  `debt_spike` came back *positive* (ordinary capital-project borrowing,
  not distress), which this coarse sign-check cannot distinguish from
  genuine debt-driven stress.
  **Second fix, applied 2026-09-20** in `dynamics.py` /
  `score_institution.py`: the debt_spike gate is removed, and
  `frac_high_entropy` is now built from a genuinely directional
  entropy measure at its source — `dynamics.rolling_causal_downside_variance()`
  replaces plain symmetric variance for the operational channel, so only
  *declines* (not any large swing) count toward high-entropy
  classification, independent of `debt_spike` entirely (see that
  function's own docstring for the full reasoning, including a synthetic
  sanity check confirming a positive shock now scores zero while an
  equivalent negative shock does not). `debt_spike` itself is untouched
  and still stored as its own independent feature — it no longer gates
  anything. **FIXED and validated, 2026-09-20:** unlike the first fix,
  this one changes how `frac_high_entropy` is computed from raw
  posterior trajectories, which the panel never cached (only the final
  8-feature vectors are stored anywhere in this repo), so it needed a
  live re-fit of all 54 institutions to check — `src/recompute_panel_entropy.py`
  and its matching manual-only workflow did exactly that on GitHub
  Actions (the one environment on this project confirmed able to reach
  NCES/College Scorecard). Result: leave-one-out accuracy holds at
  100.00% on the refit panel, zero misclassifications — the recomputed
  panel was promoted to `data/panel/panel.json` the same night. A fresh
  live re-score of Houston/UCF/FSU/Clemson/Long Beach was also run
  against the fix. Real result, not fully clean either way: Houston —
  the case that motivated this whole fix — is resolved, now scoring
  `stable` (40.6%), consistent with its real AA+ bond rating and $3.3B
  reserves. But two new, unexplained results surfaced in the same run,
  not smoothed over: Clemson (39.0%) and West Virginia University
  (44.2%) both flipped to `stable` under this fix despite each carrying
  real, independently documented financial distress (Clemson's $2.65B
  in long-term liabilities, up $231.9M year-over-year; West Virginia's
  real 2023 financial crisis and program/faculty cuts) — whether the
  new downside-only entropy measure has swung too far the other
  direction for these two, suppressing a real signal it used to
  (over)detect, was the open question at the time. An overcorrection
  was suspected — a false positive produced by the fix itself rather
  than a genuine result — so a two-step diagnostic
  (`src/diagnose_clemson_wvu.py`) was written to test that directly and
  run through GitHub Actions, the only environment used on this project
  with live network reach to NCES/College Scorecard. **Executed 2026-09-20, and the
  two institutions resolved differently, not identically.** Step 1
  ruled out MCMC non-convergence as a confound for BOTH: re-run at 4x
  sampling precision (1000 draws/1000 tune/4 chains/target_accept=0.95,
  the same settings `diagnose_window_mismatch.py` uses), `frac_high_entropy`
  held at exactly 0.0000 for each institution at both settings — neither
  `stable` call is a sampling artifact. Step 2, comparing each
  institution's full 8-feature vector against the entire validated panel
  via `RICDClassifier.peer_density()`, is where they split. **Clemson is
  resolved:** its 4 nearest real panel neighbors (Florida, Michigan, UVA,
  UNC-Chapel Hill, distance 1.23–1.41) are all confirmed-stable, with the
  nearest real closure (Northland) meaningfully farther away (1.57) — a
  clean, overwhelmingly-stable pattern. Clemson's distress is real and
  financial (in-domain for these features, unlike Buffalo below), but on
  this evidence it is genuinely not legible to any of the eight as
  currently constructed, and the `stable` call is real, not suppressed
  signal — the same status as Buffalo's gap, reached by a different
  mechanism (feature-space evidence here, domain mismatch there).
  West Virginia was narrowed but not yet resolved at that point: convergence is ruled
  out the same way, but its peer comparison is genuinely mixed — its
  nearest neighbor is Wisconsin (stable, 0.86), but its second-nearest is
  Trinity Christian, a real confirmed closure, at 1.10 (closer than three
  of Clemson's four stable comparisons), with a second real closure
  (Lourdes University) also nearby (1.30). That does not clear the bar
  for "overwhelmingly stable" the way Clemson's does, so it is not being
  closed out the same way. Framed plainly, West Virginia sits
  between two close cousins — one thriving (Wisconsin), one that
  actually collapsed (Trinity Christian) — and until that tie breaks
  further, it doesn't get the same clean resolution Clemson's evidence
  produced. **Executed 2026-09-21, in two passes**, via
  `src/diagnose_west_virginia_feature_comparison.py` (GitHub Actions):
  the feature-by-feature comparison against Wisconsin and Trinity
  Christian individually (the same kind of check
  `diagnose_feature_values.py` already runs for Houston/UCF/FSU). At
  production settings (300/300/2/0.9), the seven non-entropy features
  split evenly: three leaned toward Wisconsin (`d_A_trend`, `d_A_final`,
  `debt_spike`), three toward Trinity Christian (`delta_R_final`,
  `delta_R_trend`, `reserve_adequacy`), with `research_ratio`
  uninformative (pinned at 0.0000 for all public institutions by the
  same structural gap documented elsewhere in this section). But two of
  the three features leaning toward Trinity Christian —
  `delta_R_final` and `delta_R_trend` — are posterior-derived, and this
  run's own log showed the same `rhat > 1.01`/low-ESS warning that
  motivated `diagnose_window_mismatch.py` and
  `diagnose_clemson_wvu.py`'s Step 1. Re-run at high-precision settings
  (1000/1000/4/0.95), both flipped to Wisconsin, moving the tally to 5
  leaning Wisconsin against 1 leaning Trinity Christian. This is a
  real, not cosmetic, distinction from Clemson's clean resolution: the
  one holdout, `reserve_adequacy`, is computed directly from parsed
  finance data with no MCMC step at all, so its lean toward Trinity
  Christian (West Virginia at 10.37 — distance 1.11 to Trinity
  Christian's 9.26 vs. 1.39 to Wisconsin's 11.76) cannot be a
  convergence artifact, and it is the single largest-magnitude
  coefficient in the fitted classifier. So while a real majority of
  features now favor Wisconsin once sampling noise is removed —
  corroborating `peer_density()`'s aggregate nearest-neighbor verdict
  rather than overturning it — the model's most heavily-weighted
  feature still points the other way, which a raw feature tally alone
  cannot settle. **Resolved, 2026-09-21:** feeding West Virginia's
  real, high-precision feature vector directly through the fitted
  `RICDClassifier` — the properly-weighted model output, not an
  unweighted feature tally — gives 40.6% probability of `high_risk`
  (down from the production-settings live score of 44.2%), the same
  standard already used to call Houston resolved. This is what
  actually settles it: the 5-1 feature tally above undercounts how
  much `reserve_adequacy`'s closure-leaning value should matter, since
  it treats all seven features as equally weighted when the fitted
  model does not — but the model's own coefficients already price
  that in, and the real output still comes back stable, not a coin
  flip. `docs/data/live_scores.json` deliberately stays at its
  production-settings 44.2% (`score_batch.py` runs every institution
  at the same production settings for consistency, not case-by-case),
  and the two numbers agreeing on the call, with only a small,
  explainable difference in margin, is corroboration rather than a
  live discrepancy needing its own fix.
  UCF (currently 85.11% as of the most recent live batch run; 83.4%
  immediately after this fix, down from 95.4% pre-fix) and FSU
  (currently 65.03% as of the most recent live batch run; 57.1%
  immediately after this fix, down from 87.1% pre-fix) are
  still `high_risk`, meaningfully lower than before the fix and now fully
  explained (see "Distress, not collapse" above): each traces to a real,
  bounded debt problem -- FSU's athletics debt, UCF's housing bond --
  structured and secured as project-specific revenue bonds rather than
  general obligations of the university, alongside an otherwise-stable
  overall institutional bond rating (Florida Board of Governors filing,
  2/27/26). Cal State Long Beach (currently 95.59%, previously 95.8%)
  and Sweet Briar (currently 79.55%, previously 80.1%) remain `high_risk`;
  Sweet Briar's case is
  still believed to be the separate reset/recovery gap below, not this
  one. University of Phoenix-Arizona remains `high_risk` at effectively
  100% (currently 99.9961%, previously 99.997%). University at Buffalo was removed from the live batch
  entirely after this fix — see `score_batch.py`'s own docstring: its
  score sat at a near-50/50 that didn't map to any mechanism this
  model's features are built to detect (its real strain is a $47M
  federal research-funding cut). **No plan to resolve Buffalo, and this
  is a real distinction from Clemson/West Virginia above, now that both
  of those are actually resolved.** Clemson and West Virginia's distress
  is financial (debt, liabilities, budget cuts) — exactly the domain
  these eight features were built to measure, so each reached a real
  resolution within that same feature space: Clemson's `stable` call is
  real, not suppressed signal, even though its distress isn't legible to
  any of the eight as currently constructed (the same status as
  Buffalo's gap, reached by a different mechanism — see above); West
  Virginia's `stable` call held up once its real feature vector was run
  through the fitted classifier's own weighting, resolving the tie a raw
  feature tally couldn't settle. Buffalo's distress isn't in that domain
  at all: a federal research-funding cut doesn't move debt, reserves, or
  enrollment, so no version of `frac_high_entropy` — or any of the other
  seven features — could be expected to detect it, not even in
  principle. Building a feature for that would need a real, confirmed
  research-funding-cut closure or near-closure in the training panel to
  validate against, and none exists there; adding an untested feature
  with nothing to validate it against would be exactly the kind of
  unverified change this project doesn't make. Buffalo stays out of the
  live batch until a case like it actually shows up in real, confirmed
  outcome data — not something to build toward speculatively.
- **The model has no separate state for "collapse, but already reset" —
  found 2026-09-19, not yet built.** Every feature currently in the
  vector is a function of an institution's *most recent* observed
  window (`frac_high_entropy` looks at the last 5 periods; `d_A_trend`
  and `delta_R_trend` compare a mid-period average to a late-period
  one). None of them ask whether a large disruption is still in
  progress or has already been absorbed. University of Phoenix-Arizona
  scoring 100.0% is the live case: it underwent a real, large
  enrollment contraction and restructuring, and the working hypothesis
  (not yet confirmed against its real data, which this environment
  can't fetch) is that the model is reading the *aftermath* of a
  completed reset as ongoing collapse, because both look identical to
  every feature currently computed only over the tail window. Sweet
  Briar College (52.4%) is the panel's own version of this same
  question, and the reason it's the more useful test case: it had a
  real, documented near-closure and recovery in 2015, so a real
  post-recovery time series already exists for it, unlike Phoenix.
  A scoped candidate, **tested 2026-09-20 via `src/diagnose_reset_recovery.py`
  (GitHub Actions), with a real but thin result — not yet good enough
  evidence to promote, and not left unstated either.** The candidate: a
  *within-window* trajectory feature (`within_window_trend`) comparing
  `frac_high_entropy` in the mid-window slice against the most recent 5
  periods — high-then-declining reads as stabilizing after a shock,
  high-and-still-rising reads as ongoing collapse. Sweet Briar's real,
  full 2010-2023 trajectory (fetched live specifically to span its 2015
  crisis and 2016+ recovery) came back at `within_window_trend = -0.20`,
  the predicted direction — and a convergence recheck at 4x sampling
  precision reproduced the identical value and identical last-period
  regime, confirming this is a real result, not sampling noise.
  **But the evidence is thin, and this project's own standard requires
  saying so plainly:** that -0.20 is driven almost entirely by a single
  most-recent period (2023) flipping from high-entropy to baseline —
  the entire 2014-2022 span, which contains virtually all of Sweet
  Briar's real, documented recovery, stays classified high-entropy
  throughout under this construction. A feature that only distinguishes
  the single latest period, not a genuine multi-year decline through a
  known recovery, is not yet a validated detector of "already reset."
  University of Phoenix-Arizona's result was flat (`within_window_trend
  = 0.00`, also confirmed real and not noise at both sampling
  precisions) — no signal either way, consistent with its restructuring
  outcome not being independently confirmed as complete. **Plan, not yet
  executed:** refine the candidate to use a real multi-point trend
  across the full window rather than a two-segment average, since the
  current construction is too sensitive to one endpoint; only if a
  refined version shows a cleaner signal against Sweet Briar's real
  recovery would this be worth the full 54-institution panel refit and
  leave-one-out re-validation (the `recompute_panel_entropy.py`-scale
  step) that adding a genuine 9th feature requires. Not shipped, not
  abandoned — a real, partially-supportive experiment with a specific,
  named next step.
- **A separate anchor-quantification sensor, now being built as its own
  project to run alongside this 8-feature panel and cross-reference
  against it — not as a 9th feature merged into it — is summarized in
  full in ["Tell's Upcoming Project"](#tells-upcoming-project) near the
  top of this README, with complete detail in the project's own seed
  note.** One thing worth flagging here specifically, since it bears
  directly on this section's documentation standard: the sensor is
  planned to test whether it can resolve the reset/recovery gap
  described above for Sweet Briar and Phoenix, and the reasoning that
  connects it to the same public-sector data-scarcity problem already
  documented below for `reserve_adequacy` is spelled out there in full,
  not repeated twice here.
- **`reserve_adequacy` — confirmed the classifier's single strongest
  feature (largest-magnitude fitted coefficient, -1.88 on the
  standardized panel, next closest -1.38 for `d_A_trend`) — has no
  real distress example to calibrate against anywhere in the public
  sector, and this is a structural gap in the data that exists, not a
  data-collection failure in this project's pipeline.** The validated
  panel's five public institutions (Michigan, UVA, UNC-Chapel Hill,
  Florida, Wisconsin) are all real, confirmed-stable outcomes, sitting
  at `reserve_adequacy` 10.89–12.93 against a panel-wide median of
  11.62 — not extreme outliers within this panel, but all five were
  selected into the original research specifically for being large,
  wealthy, well-documented flagships, not as a representative sample
  of the roughly 600 public four-year institutions nationally, most of
  which carry far less endowment per student than any of the five.
  There is no confirmed-closure public institution in the panel to set
  against them, and this is not something this project failed to find:
  Kelchen, Ritter & Webber, "Predicting College Closures and Financial
  Distress" (Federal Reserve Bank of Philadelphia, WP 24-20, Dec.
  2024) — a national study covering 2002-2023 — found only two
  four-year public closures in that entire 21-year period nationally
  (one tribal college, one graduate health-sciences-focused
  institution, neither a broad-based comprehensive or flagship public
  university), and excluded public institutions from its own
  closure-prediction model for exactly this reason: too rare a base
  rate to fit against. The paper's own explanation is direct: "Closing
  a public college is a deeply political decision, similar to closing
  a military base," so states use mergers and consolidations instead
  of closure when a public institution is in real distress (a live,
  current example: East Georgia State College's 2026 merger into
  Georgia Southern University, not a closure by this project's outcome
  definition). **Practical consequence: `reserve_adequacy`-driven
  scores for any public institution that is not itself an unusually
  well-endowed flagship — Houston, UCF, FSU, Buffalo, Clemson, Cal
  State Long Beach, and any future one like them — are extrapolating
  outside the range of outcomes this feature was ever validated
  against for that sector, on both sides: no distress example, and no
  ordinary-wealth stable example either.** This is not expected to
  resolve on its own. Fixing it for real needs either a genuine new
  confirmed public four-year closure to add to the panel (rare by the
  numbers above, not something to wait on) or a deliberate, disclosed
  decision to widen this project's own outcome definition for the
  public sector specifically — e.g., treating a distress-driven merger
  or consolidation as the public-sector analogue of a private closure
  — and that would be a real change to what "confirmed outcome" means
  in this project, not a quiet patch, so it should be made openly and
  argued for on its own, not slipped in to make an inconvenient gap
  disappear. **The most concrete real path to actually closing this
  gap is tracked as its own item, next.**
- **Penn State York is the first real, tracked candidate for the one
  thing that would actually fix `reserve_adequacy`'s public-sector
  calibration gap above: a genuine, confirmed public four-year
  closure driven by financial distress — not yet usable, but this is
  the concrete path being watched, not a hypothetical one.** Checked
  against three other candidates a broader search surfaced (2026-09-20) —
  IUPUI's 2024 split into IU Indianapolis and Purdue Indianapolis, and
  UT Brownsville's 2015 dissolution into UT Rio Grande Valley, were
  both ruled out on the merits: IUPUI's own announcement frames the
  split as strategic expansion, not distress ("dramatically growing
  needs of our state," new investment pledged by both universities, no
  financial or enrollment rationale at all); UT Brownsville was a real
  financial-distress case but resolved the same way East Georgia State
  College did above — a rescue-by-merger with the campus, students,
  and faculty carried into the new institution, plus an affirmative
  strategic upside (Permanent University Fund access, a new medical
  school) — not a termination. Penn State York is different in kind:
  real, cited financial losses, 61% enrollment decline from its peak
  (703 students, Fall 2024), $29.9M in deferred maintenance, explicitly
  announced (May 2025) as closing for exactly those reasons, not a
  merger. It is not yet usable for two independent reasons, not one:
  first, it hasn't happened yet — Penn State York is set to close
  after the Spring 2027 semester, and this project's outcome standard
  is a completed, confirmed event, not a scheduled one; second, and
  unresolved as of this writing, Penn State York is a commonwealth
  campus operating under Pennsylvania State University's single
  overall accreditation, not a separately accredited institution, and
  it is not yet confirmed whether IPEDS carries separate
  institution-level Finance data for it or whether its finances are
  consolidated into Penn State's university-wide filing — the latter
  would leave nothing for this project's per-institution pipeline to
  extract, since Penn State as a whole is a stable, thriving R1
  university, not a closing one. Confirming the IPEDS finance-reporting
  question needs live network access this development environment
  doesn't have (same limitation noted throughout this section);
  revisiting Penn State York after Spring 2027, once its closure is a
  completed fact rather than an announced plan, is the concrete next
  check, not something to chase down early.
- **Seven additional private liberal-arts colleges — Bucknell
  University, Haverford College, Thomas Aquinas College, Hampden-Sydney
  College, Augustana College, Holy Cross College, and Wittenberg
  University — were added to the live batch on 2026-09-22**, selected
  using the same neutral-selection methodology already documented in
  `score_batch.py`'s own docstring (no institution added because of an
  expected outcome; a substitution made only when a first-choice
  candidate had an unrelated collision with the pipeline). Current live
  scores as of the most recent batch run: Bucknell 9.45%, Haverford
  9.22%, Hampden-Sydney 36.16%, Augustana 46.80%, Holy Cross 4.84% —
  all `stable`, none showing an anomaly requiring individual treatment
  under this section's documentation standard. Thomas Aquinas and
  Wittenberg get a combined entry below: Thomas Aquinas because its
  reproducibility instability triggered a multi-day investigation across
  three independent fixes, now resolved with a real, evidence-backed
  production number; Wittenberg because its elevated convergence rhat,
  once investigated, needed the same backend fix.
- **A real bookkeeping gap, not a scoring problem, for two institutions
  currently on the live dashboard — Thomas Aquinas College and
  Wittenberg University: neither institution's sampler has driven its
  own formal convergence diagnostic (rhat) below PyMC's textbook
  threshold of 1.01, across any fix tried.** This does not mean either
  institution's score is unreliable, and that's been checked directly,
  not assumed: Thomas Aquinas's classification came back identical
  across 20 separate real runs — 10 at this project's usual fixed seed
  across separate dispatches, 10 more at genuinely varied random seeds —
  regardless of rhat ranging from 1.03 to 1.47 across those runs.
  Wittenberg's production score (95.45% probability `high_risk`) and an
  independent, higher-precision re-run (97.20%) agree closely as well.
  Three specific fixes were tested directly against Thomas Aquinas's
  worst-converging parameter, a financial observation-noise scale
  historically shared across all four of the model's financial channels.
  Splitting that shared scale into four independent per-channel scales
  fully resolved one channel and substantially improved two more, but
  left the instructional-spending channel essentially unchanged, whose
  own noise parameter then became the single worst in the model. A
  hypothesis that this channel's real data was too volatile for its
  fixed model parameters was tested directly against real IPEDS data and
  rejected outright — it's actually the least volatile of the four
  channels, the opposite of the prediction. A follow-up check found the
  strongest funnel-geometry signature of all four channels specifically
  here, and applying the same non-centered reparameterization already
  proven elsewhere in this model produced a real, meaningful rhat
  improvement — but also a large increase in sampling divergences,
  trading one diagnostic problem for a different one rather than
  resolving it cleanly. **Testing stops here for now, as a practical
  choice, not because the question is closed.** If this is picked back
  up, the concrete next step is direct: address the new divergence
  problem the reparameterization introduced, or test the most plausible
  remaining explanation — not itself directly tested — that this
  reflects how little real annual finance data exists per institution
  (as few as 11 real years) relative to the model's complexity, a
  genuine estimation-difficulty limit rather than a single fixable bug.
  Neither institution's live score is affected by any of this.

## Repository structure

sampling protocol.md      Pre-committed rules for the 300-institution confirmatory test
src/
  model.py               Bayesian state-space model (PyMC)
  jump_diffusion.py       Shock-type latent process for debt
  common_cause.py         Shared-external-shock detector
  real_adapter.py          Real IPEDS/Scorecard data loading (historical, local files)
  fetch_live_data.py       Live data fetching (College Scorecard API + IPEDS bulk files)
  classifier.py             The 8-feature + governance-override classifier
  score_institution.py       End-to-end scoring entry point for one institution (see Known Gaps)
  score_batch.py              Scores a fixed, disclosed list of real institutions in one run (see Known Gaps)
  render_dashboard.py          Bakes docs/data/live_scores.json into docs/index.html as static HTML
  dynamics.py                   Core RICD dynamical-system equations used by the model
  legacy_peer_density_reference.py   Retained reference implementation from an earlier peer-density approach
  diagnose_scorecard_gaps.py    One-off diagnostic: real per-year, per-field College Scorecard completeness for a given institution
  diagnose_feature_values.py    One-off diagnostic: real 8-feature vectors for given institutions vs. real validated-panel reference values (see Known Gaps)
  diagnose_f3_fields.py         One-off diagnostic: confirmed the real F3 (for-profit) finance form's column codes against a live filing
  diagnose_ipeds_access.py      One-off diagnostic: found NCES's real, current bulk-file URL pattern for the newest 1-2 years, after the old one went dead
  diagnose_ipeds_access2.py     One-off diagnostic: found NCES's real, current bulk-file URL pattern for older years (FY2013-FY2021), served from a different location than the newest years
  diagnose_panel_pipeline_consistency.py   One-off diagnostic: checks the panel-loading pipeline's path resolution and data consistency
  diagnose_window_mismatch.py    One-off diagnostic: separates a real live-vs-panel data-window mismatch from ordinary MCMC non-convergence
  recompute_panel_entropy.py     Real validation for the directional-entropy fix: re-fits all 54 panel institutions live and compares leave-one-out accuracy (see Known Gaps)
  diagnose_clemson_wvu.py        Two-step diagnostic (convergence check + panel peer-density comparison) that resolved Clemson and narrowed West Virginia (see Known Gaps)
  diagnose_west_virginia_feature_comparison.py   Feature-by-feature comparison of West Virginia against Wisconsin and Trinity Christian individually, at production and high-precision settings (see Known Gaps)
  diagnose_reset_recovery.py     Tests the candidate within-window trend feature for the reset/recovery gap against Sweet Briar and Phoenix, with a convergence recheck (see Known Gaps)
  diagnose_thomas_aquinas_highprecision.py   High-precision MCMC convergence check for Thomas Aquinas's reproducibility instability (see Known Gaps)
  diagnose_thomas_aquinas_perchain.py        Per-chain diagnostic ruling out within-run chain multimodality for Thomas Aquinas (see Known Gaps)
  diagnose_clemson_wvu_cores1.py             Re-validates Clemson and West Virginia's live scores under cores=1 (see Known Gaps)
  diagnose_phoenix_cores1.py                 Re-validates Phoenix's live score under cores=1 (see Known Gaps)
  diagnose_thomas_aquinas_batch_position.py  Cold-vs-warm test ruling out batch-position/in-process state leakage for Thomas Aquinas (see Known Gaps)
  diagnose_thomas_aquinas_conda_blas.py      Tests whether a conda-forge (real BLAS-linked) PyTensor install resolves Thomas Aquinas's reproducibility instability -- confirmed NOT a fix, made rhat worse (see Known Gaps)
  diagnose_thomas_aquinas_extreme_precision.py  Pushes MCMC settings far beyond production (2000/2000/4 chains, target_accept=0.99) to test whether Thomas Aquinas's posterior can converge at all given enough sampling effort (see Known Gaps)
  diagnose_thomas_aquinas_pinned_env.py      Single-evaluation diagnostic run inside a byte-identical pinned Docker environment, to isolate environment drift from runner-hardware-level non-determinism (see Known Gaps)
  diagnose_thomas_aquinas_numba.py           Tests PyTensor's Numba backend as an alternative to its default non-BLAS-linked path, with direct linker-class confirmation that Numba is really engaged -- the adopted fix (see Known Gaps)
  diagnose_thomas_aquinas_varied_seed.py     Tests genuinely varied random seeds (not this project's usual fixed seed) under the Numba backend, after random_seed became a real parameter (see Known Gaps)
  diagnose_wittenberg_numba.py               High-precision convergence check for Wittenberg University under the Numba backend, the deferred follow-up to the Thomas Aquinas investigation (see Known Gaps)
  draw confirmatory sample.py   Draws the 300-institution confirmatory sample under sampling protocol.md (run once)
data/
  panel/panel.json           The real, validated 54-institution panel
  confirmatory/draw log.csv     Every institution the confirmatory draw touched, and why each was kept or skipped
  confirmatory/draw slots.json  The 300 drawn institutions, with frame size, step size, source checksum, and 25 ordered backups per slot
docs/
  RICD 16.1 manuscript.docx, .tex    The full, domain-independent RICD theory
  index.html                      Public results dashboard (GitHub Pages)
  data/panel.json                  Validated 54-institution panel data
  data/live_scores.json            Real institutions scored live by score_institution.py / score_batch.py
reports/
  RICD Tracker Findings Final.pdf        Final findings document
  RICD Tracker Narrative Final.pdf       Narrative account of how results were reached
  RICD Tracker Process Log Final.pdf     Consolidated process record
  Higher Ed Sector Findings.pdf           What the results imply about the sector
  Collapse-Causal Tracker (C-CT) Description Document.pdf   What a collapse-causal tracker is as a category, and how it differs from C-CAT
  RICD Adapter Instructional Manual.pdf  Adapter-contract implementation guide, for engineers
  readme.md                                Guide to this folder's contents
future-projects/
  Collapse-Causal Agent Tracker (C-CAT) Seed Note.pdf         Seed note for a mechanism-layer (agent) tracker, planned for later
  Next Project for RICD - Four Adapter Build Roadmap.pdf      One-year build plan for four new tracker adapters (banking, hospitals, public schools, nursing homes/long-term care)
  RICD Ongoing Projects Roadmap.docx                            Broader roadmap of further planned RICD-based trackers
.github/workflows/
  rescore.yml                     Scheduled re-scoring workflow (score_batch.py + score_institution.py + render_dashboard.py)
  claude.yml                       Claude Code GitHub Action (handles @claude-triggered edits made directly on GitHub)
  draw confirmatory sample.yml      Manual-only: runs draw confirmatory sample.py once and commits the draw
  diagnose_scorecard_gaps.yml      Manual-only: runs diagnose_scorecard_gaps.py
  diagnose_feature_values.yml      Manual-only: runs diagnose_feature_values.py
  diagnose_f3_fields.yml            Manual-only: runs diagnose_f3_fields.py
  diagnose_ipeds.yml                Manual-only: runs the IPEDS-access diagnostics
  diagnose_panel_pipeline_consistency.yml   Manual-only: runs diagnose_panel_pipeline_consistency.py
  diagnose_window_mismatch.yml      Manual-only: runs diagnose_window_mismatch.py
  recompute_panel_entropy.yml        Manual-only: runs recompute_panel_entropy.py (see Known Gaps)
  diagnose_clemson_wvu.yml            Manual-only: runs diagnose_clemson_wvu.py (see Known Gaps)
  diagnose_west_virginia_feature_comparison.yml   Manual-only: runs diagnose_west_virginia_feature_comparison.py, with an optional high-precision checkbox (see Known Gaps)
  diagnose_reset_recovery.yml         Manual-only: runs diagnose_reset_recovery.py (see Known Gaps)
  diagnose_thomas_aquinas_highprecision.yml       Manual-only: runs diagnose_thomas_aquinas_highprecision.py (see Known Gaps)
  diagnose_thomas_aquinas_perchain.yml            Manual-only: runs diagnose_thomas_aquinas_perchain.py (see Known Gaps)
  diagnose_clemson_wvu_cores1.yml                 Manual-only: runs diagnose_clemson_wvu_cores1.py (see Known Gaps)
  diagnose_phoenix_cores1.yml                     Manual-only: runs diagnose_phoenix_cores1.py (see Known Gaps)
  diagnose_thomas_aquinas_batch_position.yml      Manual-only: runs diagnose_thomas_aquinas_batch_position.py (see Known Gaps)
  diagnose_thomas_aquinas_conda_blas.yml          Manual-only: runs diagnose_thomas_aquinas_conda_blas.py, installing dependencies via conda-forge instead of pip (see Known Gaps)
  build_thomas_aquinas_pinned_image.yml           Manual-only: builds and pushes the byte-identical pinned Docker image (Dockerfile.thomas_aquinas_pinned) to GHCR, used by diagnose_thomas_aquinas_pinned_env.yml (see Known Gaps)
  diagnose_thomas_aquinas_pinned_env.yml          Manual-only: runs diagnose_thomas_aquinas_pinned_env.py inside the pinned Docker image (see Known Gaps)
  diagnose_thomas_aquinas_numba.yml               Manual-only: runs diagnose_thomas_aquinas_numba.py -- one evaluation per dispatch, run several separate times and compared across dispatches (see Known Gaps)
  diagnose_thomas_aquinas_varied_seed.yml         Manual-only: runs diagnose_thomas_aquinas_varied_seed.py, testing 10 varied seeds within one job (see Known Gaps)
  diagnose_wittenberg_numba.yml                   Manual-only: runs diagnose_wittenberg_numba.py, 3 replicates at high precision under the Numba backend (see Known Gaps)

## Re-scoring cadence

IPEDS is not live data — it releases on a fixed institutional schedule
(provisional data a few times a year, final data annually). The scheduled
workflow in `.github/workflows/rescore.yml` runs periodically and checks
for new data rather than assuming a fixed release date; a run that finds
nothing new is a normal, expected outcome, not a failure.
