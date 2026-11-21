# Anchor efficiency protocol (item 15c): overleverage, what anchors buy, the strain on the grid, and the edge cases

Fixed November 21, 2026 (decisions A and B approved), before anything is computed. Exploratory where outcomes are already known (closures through HD2025); the rules are then frozen and carried into the blind retest.

## 1. Why this test

In a heavily anchored domain, anchoring stands in for health: an anchored college rarely closes whatever its own condition, so a proxy for anchoring (size and sector) predicts closure well on its own. The tracker is not built to beat that proxy. It is built to do what the proxy cannot: catch the edge cases, show the causes of divergence, measure how often anchored systems overleverage their anchors, and measure the anchors themselves, to learn how efficient they are and how much strain inefficient, chronically overleveraged systems place on the larger grid that carries them (RICD Spine Definitions 10.3a.7 and 10.3a.8; Catalog §10.5b.13). Until now Tell has measured the share of colleges short beyond their anchors each year and who carries the gap, but not these. This protocol measures them. The causes of divergence inside the college (which spending lines drive the gap) are item 23f, a separate protocol.

## 2. Data and measures

The frozen item-15 rule (ending types protocol.md with Amendments 1 to 3), applied to every public and private nonprofit college in the IPEDS frame, fiscal 2005 to 2024, with src/ending types.py imported unchanged: total work W (expenses less depreciation), exchange E_exch, other operating income O, anchor capacity A by source (federal, state and local appropriations; gifts; the endowment draw), coverage c, gap coverage g, and each college-year's state (self-covering, held up by anchors, short beyond its anchors). For-profit colleges are left out: their anchor is not observable in IPEDS.

## 3. Overleverage: how often, and how chronic

For each college, over its years with data: the number of years short beyond its anchors (g > 1), the longest run of consecutive such years, and the share of its years spent there; the same three for years held up by anchors.

**Classes (decision A, approved):** *never short* (no year with g > 1); *episodic* (at least one such year, but no run of three or more); *chronic* (a run of three or more consecutive years with g > 1). A college with fewer than five years of data is *too short to classify*.

Reported by sector and by size: counts and shares of each class, and closure rates by class.

## 4. What anchors buy: efficiency

**Episodes.** An episode begins in the first year a college is short beyond its anchors (g > 1) after at least one year at g ≤ 1. Episodes are defined on gap coverage, not on coverage, because c > 1 is the designed state of a public college (its state funds it) and common at private nonprofits, so needing anchors is not itself overleverage; exceeding them is. Its outcome is read over the next five fiscal years (**decision B, approved: episodes on g, five years**): *recovered* (back to g ≤ 1 in two consecutive years), *still short* (g > 1 at the end of the window), *closed* (a documented closure within the window), or *censored* (the window runs past fiscal 2024). The anchor dollars of the episode are those in its start year and the years it lasts.

**Efficiency.** For each episode, the anchor dollars spent during it (the sum of A over its years) and its outcome. Reported by sector and anchor source:

- the share of anchor dollars that went to episodes ending in recovery, against those still short at the end or closed;
- recovery and closure rates by anchor intensity at the start (the anchored share A / (W − E_exch − O), in thirds within each sector);
- anchor dollars per recovered episode.

An anchor is efficient where its dollars go mostly to episodes that recover, and inefficient where they go mostly to colleges that stay short beyond their anchors or close. Descriptive; no model is fitted.

## 5. Strain on the grid

For each anchor source, sector and fiscal year: the dollars covering gaps (A by source, against W − E_exch − O), split by the college's overleverage class (section 3); and the uncovered shortfall, W − E_exch − O − A in years with g > 1, which the college must draw from reserves or borrowing. **The strain share** is the part of each source's gap-covering dollars going to chronic colleges. Reported over time, so a growing strain share shows anchors carrying more and more chronic overleverage.

## 6. The edge cases, fixed for the retest

At tracker v3's committed cut points, using the v3 test (exploratory, outcomes known) and then the blind retest (prospective), four lists with names and counts:

1. closures the tracker caught that the frozen size-and-sector model missed;
2. closures the size-and-sector model caught that the tracker missed;
3. colleges the size-and-sector model flagged that the tracker did not flag once their anchors were counted, and whether they survived (the church-anchored seminaries are the first known group);
4. colleges whose flag the anchor sensor cleared and that closed anyway (an anchor that failed).

Each list is reported with each college's overleverage class (section 3) and anchored share, so the edge cases can be read against the anchors. The retest's lists are committed with its flags, before its outcomes are released.

## 7. Records

Script src/anchor efficiency.py; workflow anchor_efficiency.yml; outputs in data/anchor efficiency/ (college classes, episodes, strain by source, edge-case lists, results). Exploratory parts are labelled as such in every output.

## 8. A stated limit

Public endowments are left out of anchor capacity, as in item 15 (the public form reports no spending distribution, and many public endowments sit in separate foundations), so public colleges' anchors are slightly understated and they appear short beyond their anchors a little more often than they are. The frozen rule is kept and the limit is stated with every public result, rather than an unverifiable draw estimated.
