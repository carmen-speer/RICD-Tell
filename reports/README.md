# Reports

This folder holds the narrative, findings, and process record of how the
higher-education collapse tracker was actually built — the account of what
was done, not just the code that does it — and the guide to building a
tracker in a new domain.

## Contents

- [`Building a C-CT Tracker in Your Domain.pdf`](<Building a C-CT Tracker in Your Domain.pdf>) —
  the step-by-step guide to building a collapse-causal tracker in a new
  domain, from choosing the domain to a final checklist, written from what
  the higher-education tracker taught. It replaces the earlier adapter
  manual, and its first rules are the two the tracker learned hardest:
  choose the channels on development data before anything is scored, and
  list every way the training sample differs from the population it will
  be used on, starting with the base rate.
- [`Collapse-Causal Tracker (C-CT) Description Document.pdf`](<Collapse-Causal Tracker (C-CT) Description Document.pdf>) —
  a description document, distinct from the reports below: what a
  collapse-causal tracker is as a category of thing, the RICD math it draws
  on (Feedback Divergence Field Mechanics, resource dynamics, permeability
  and regime classification, collapse onset), and how the one built so far
  (the higher-ed tracker) generalizes to the domains planned next. Also
  distinguishes C-CT from the collapse-causal *agent* tracker (C-CAT) —
  C-CT measures the aggregate effect a cause leaves behind without needing
  to know what produced it; C-CAT, seeded in
  [`future-projects/`](<../future-projects/Collapse-Causal Agent Tracker (C-CAT) Seed Note.pdf>),
  is the planned tracker that goes looking for the specific agent that did.
- [`Model evolution.md`](<Model evolution.md>) — the record of tracker v1
  and v2, the first two pre-registered tests, and the exploratory search
  for the meta channel's first readings: how the tracker was built into
  v3, the version that passed.
- [`RICD Tracker Findings Final.pdf`](<RICD Tracker Findings Final.pdf>) —
  the development-panel findings, from before the out-of-sample tests:
  the eight features, the two honest negative results, the governance
  override, and the in-sample result on the designed 54-institution panel
  (100.00% leave-one-out accuracy). The out-of-sample evidence is in the
  root README.
- [`RICD Tracker Narrative Final.pdf`](<RICD Tracker Narrative Final.pdf>) —
  the narrative account of how each result was actually reached, including
  the dead ends and corrections along the way, not just the final state.
- [`RICD Tracker Process Log Final.pdf`](<RICD Tracker Process Log Final.pdf>) —
  the consolidated process record: methodological lessons, the panel
  four-category labeling discipline, and the data- and feature-verification
  steps that produced the panel result.
- [`Higher Ed Sector Findings.pdf`](<Higher Ed Sector Findings.pdf>) — a
  separate analysis of what the tracker's results imply about the U.S.
  higher-education sector as a whole, distinct from the validation result
  itself.

The full write-up of tracker v3, with every number, is being prepared for
this folder.

The seed note for a genuinely different kind of tracker — an agent tracker
(C-CAT), investigating the specific real decisions and agents behind a
collapse (board minutes, depositions, investigative findings) rather than
the aggregate financial and enrollment effects this folder's reports
measure — lives in [`future-projects/`](../future-projects/), alongside
other not-yet-built work, not in this folder.
