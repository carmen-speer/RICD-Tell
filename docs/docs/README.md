# Docs

This folder holds the RICD manuscript and the live public dashboard —
the theory and its one public-facing view, not the tracker's code or
process record (see [`reports/`](../../reports/) and [`src/`](../../src/) for those).

## Contents

- [`RICD 17.8 Spine.docx`](<../RICD 17.8 Spine.docx>)
  (also [`RICD 17.8 Spine.tex`](<../RICD 17.8 Spine.tex>)) and
  [`RICD 17.8 Catalog.docx`](<../RICD 17.8 Catalog.docx>)
  (also [`RICD 17.8 Catalog.tex`](<../RICD 17.8 Catalog.tex>)) —
  the full, domain-independent RICD theory, in two documents: the Spine
  holds the core engine, and the Catalog of Mechanisms holds every
  further mechanism, edge case and audit protocol, under the same section
  numbers. Version 17.8 adds to §10.3a the mathematics of what anchors
  carry (anchor stocks and flows, the gap ratio, the anchored share) and
  of overleverage, anchor efficiency and the strain on the grid, and to
  §10.5a the mathematics of normalized drift. This repository's code
  implements a real subset of it (Parts 6, 7, 8, and 10.5b specifically)
  against U.S. higher-education data; the manuscript itself covers
  considerably more than the tracker uses.
- [`index.html`](<../index.html>) — the public dashboard, served via
  GitHub Pages at
  [carmen-speer.github.io/RICD-Tell](https://carmen-speer.github.io/RICD-Tell/).
  It shows tracker v3 on all 2,780 colleges in the current frame, scored
  under [`live tracker protocol.md`](<../../live tracker protocol.md>):
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
