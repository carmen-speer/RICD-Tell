# Archive

One-off diagnostics and finished records, kept as a record. Nothing in the
current pipeline runs or imports any file here.

## What is here

- `diagnostics/workflows/`: 37 workflows that investigated specific
  problems while the tracker was being built and tested: the Thomas
  Aquinas College reproducibility investigation, the Clemson and West
  Virginia, Phoenix and Wittenberg checks, the finance-form, window,
  Scorecard-gap, outcome-coding and IPEDS-access diagnostics, the
  sigma and instruction-weight model variants, the v3 anchor-code check,
  and the builder for the pinned Thomas Aquinas image.
- `diagnostics/src/`: the 41 scripts those workflows ran, including two
  model variants (`model_variant_noncentered_w_instr.py`,
  `model_variant_split_sigma_fin.py`) and two scripts no workflow ran
  (`common_cause.py`, `legacy_peer_density_reference.py`).
- `diagnostics/docker/Dockerfile.thomas_aquinas_pinned`: the pinned
  environment used by the Thomas Aquinas investigation.
- [`Texas transfer test.md`](<Texas transfer test.md>): the write-up of
  the transfer test (adjunct reliance and transfer students' outcomes,
  under `transfer test protocol.md`), which was not supported; moved here
  from the root README.
- [`Anchor-Quantification Sensor - Seed Note.md`](<Anchor-Quantification Sensor - Seed Note.md>):
  the seed note that proposed the anchor sensor, kept as a record now that
  the sensor is built (tested in tracker v3, then quantified in the ending
  types, anchor efficiency and anchor-and-voice studies; see the root
  README).

What each diagnostic found is recorded in
[Known gaps and record of fixes](<../history of fixes/Known gaps and record of fixes.md>).
Some current scripts, and the sampling protocols, still mention these
files by name; they now live here. The frozen v3 scripts are not edited to
update those mentions, because v3 scoring checks each frozen file by its
hash.

## What is not here

Everything that reproduces a reported result stays in place and runnable
from the Actions tab: the confirmatory, v2 and v3 pipelines, the
equivalence, reproducibility and convergence checks, the reanalysis, the
meta-channel tests, the anchor cross-reference, the transfer test, the
ending types, anchor efficiency and anchor-and-voice studies, and the live
tracker. `src/diagnose_v2_finance_codes.py` and its workflow also stay,
because the current pipeline imports that script.

## Running an archived workflow

GitHub runs only workflow files placed directly in `.github/workflows/`,
so these no longer appear in the Actions tab (their past runs and logs
remain in the repository's Actions history). To run one again, copy it
back to `.github/workflows/` and its script back to `src/`, since the
workflows call their scripts by those paths.
