# Docs

This folder holds the RICD manuscript and the live public dashboard —
the theory and its one public-facing view, not the tracker's code or
process record (see [`reports/`](../../reports/) and [`src/`](../../src/) for those).

## Contents

- [`RICD 16.0 manuscript.docx`](<../RICD 16.0 manuscript.docx>)
  (also [`RICD 16.0 manuscript.tex`](<../RICD 16.0 manuscript.tex>)) —
  the full, domain-independent RICD theory. This repository's code
  implements a real subset of it (Parts 6, 7, 8, and 10.5b specifically)
  against U.S. higher-education data; the manuscript itself covers
  considerably more than the tracker uses. Checked against the
  [Integration Manifest](<../../reports/RICD Integration Manifest.docx>)
  in `reports/`, which records every mechanism confirmed built into the
  framework against the exact manuscript text.
- [`index.html`](<../index.html>) — the public results dashboard, served via
  GitHub Pages at
  [carmen-speer.github.io/Recursive-Information-Container-Dynamics](https://carmen-speer.github.io/Recursive-Information-Container-Dynamics/).
  Shows the validated 54-institution panel and, separately, real
  institutions scored live by the tracker pipeline (see the root
  README's Known Gaps section for what each live score does and doesn't
  mean, and "Distress, not collapse" for what an elevated score means
  for a public flagship specifically).
- `data/panel.json` and `data/live_scores.json` — the two real data files
  `index.html` reads directly: the validated panel and the live-scored
  institutions, respectively. Not meant to be read on their own; they
  exist to feed the dashboard.

This folder is the one place in the repository built to be viewed
directly by someone who isn't reading the code — everything here should
stay checkable against `reports/RICD Integration Manifest.docx` and the
root README rather than drifting into its own separate account of
what's true.
