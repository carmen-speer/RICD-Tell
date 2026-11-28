# Docs

This folder holds the RICD manuscript and the live public dashboard —
the theory and its one public-facing view, not the tracker's code or
process record (see [`reports/`](../../reports/) and [`src/`](../../src/) for those).

## Contents

- [`RICD 17.9 Spine.docx`](<../RICD 17.9 Spine.docx>)
  (also [`RICD 17.9 Spine.tex`](<../RICD 17.9 Spine.tex>)) and
  [`RICD 17.9 Catalog.docx`](<../RICD 17.9 Catalog.docx>)
  (also [`RICD 17.9 Catalog.tex`](<../RICD 17.9 Catalog.tex>)) —
  the full, domain-independent RICD theory, in two documents that share
  section numbers, each opening with How to Read RICD. The Spine holds the
  foundational axioms and the core theory; the Catalog of Mechanisms is a
  manual of edge cases and fixes, for diagnosing a tracker that does not
  work and for building highly specific trackers with few parameters.
  Version 17.9 states the theory's core thesis: every container carries a
  self-model that must be accurate and open, and health is a relation to
  conditions. It adds the self-model and its degrees (self-model,
  sentience, self-awareness), how identity forms through internal and
  external channels (with trust and receptivity), the regimes read through
  core valence and self-belief accuracy with three high-entropy types,
  overshoot at the level of each host, the history-weighted advantage of
  containers that have integrated past excursions, trait tracking as health
  under changing conditions, the grid cycle by which dominance hierarchies
  reproduce, and the tracker profiles: the C-CT, which uses the Spine alone
  with about five to eight free parameters, and the C-CAT, which would draw
  on the Catalog to investigate agents. Version 17.8 added to §10.3a the
  mathematics of what anchors carry and of the strain on the grid, and to
  §10.5a the mathematics of normalized drift. This repository's code
  implements a real subset of the Spine (Parts 6, 7, 8 and 10) against
  U.S. higher-education data; the manuscript covers considerably more than
  the tracker uses.
- [`index.html`](<../index.html>) — the public dashboard, served via
  GitHub Pages at
  [carmen-speer.github.io/RICD-Tell](https://carmen-speer.github.io/RICD-Tell/).
  It shows tracker v3 on all 2,780 colleges in the current frame, scored
  under [`live tracker protocol.md`](<../../protocols/live tracker protocol.md>):
  each college's anchored flag, its v3 flag and probability, and the
  anchors that clear a flag. A flag marks risk of closure, not a forecast
  that a college will close (see
  ["Distress, not collapse"](<../../explanations/Distress, not collapse.md>)
  for what an elevated score means for a public flagship specifically).
- `data/live v3 scores.json` — the live v3 scores `index.html` reads.
  Not meant to be read on its own; it exists to feed the dashboard.
- [`v1.html`](<../v1.html>) — the v1 prototype, kept on record at
  [carmen-speer.github.io/RICD-Tell/v1.html](https://carmen-speer.github.io/RICD-Tell/v1.html):
  the 54-institution development panel and the 15 colleges the original
  pipeline scored, read from `data/panel.json` and `data/live_scores.json`.
  What each of those scores does and doesn't mean is in
  [Known gaps and record of fixes](<../../history of fixes/Known gaps and record of fixes.md>).

This folder is the one place in the repository built to be viewed
directly by someone who isn't reading the code — everything here should
stay checkable against the root README rather than drifting into its own
separate account of what's true.
