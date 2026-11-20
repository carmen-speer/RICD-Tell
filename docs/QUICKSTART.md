# Quickstart

This page is for a reader who wants to check Tell's result or rerun it. The
README explains what Tell is; the protocols explain what was fixed in advance.

## 1. Read the result (no running needed)

- **The pre-registered test and its rules:** [`sampling protocol v3.md`](<../sampling protocol v3.md>),
  committed before any test outcome was read.
- **The verdicts and numbers:** [`data/v3/test results.json`](<../data/v3/test results.json>)
  (tracker v3 on 987 held-out institutions, closures 2019 to 2025).
- **Every institution's score:** [`data/v3/test scores/`](<../data/v3/test scores/>), in numbered batches.
- **The frozen classifier:** [`data/v3/classifier v3.json`](<../data/v3/classifier v3.json>).
- **The comparator (critical slowing down):** [`data/v3/comparator flags.json`](<../data/v3/comparator flags.json>).
- **Exploratory follow-ups** (reanalysis, anchor cross-reference, meta-channel
  candidates, the Texas transfer test, openings against closures):
  [`data/`](<../data/>), one folder each, with the protocol for each at the top level.
- **Errors and their fixes:** [`history of fixes/`](<../history of fixes/>) and the errata
  recorded in each protocol.

## 2. Rerun the v3 test on GitHub (no installation)

Every step runs as a GitHub Actions workflow. In your own fork, open the
**Actions** tab, choose the workflow by the name shown in the sidebar, and
click **Run workflow**. Each one commits its output back to the repository.
Run them in this order:

| Order | Name in the Actions sidebar | File |
|---|---|---|
| 1 | v3 phase 1 - fit and freeze classifier v3 | `fit_classifier_v3.yml` |
| 2 | v3 phase 2 - list the v3 test institutions | `draw_v3_test.yml` |
| 3 | v3 phase 3 - score the v3 test institutions | `score_v3_test.yml` |
| 4 | v3 phase 4 - comparator | `v3_comparator.yml` |
| 5 | v3 phase 5 - test outcomes and results | `v3_test_results.yml` |

Phase 3 scores in parallel shards and commits one numbered batch per run;
run it again until every listed institution has a score. Outcomes are read
only in phase 5, after every score is committed, which is the order the
protocol requires.

To check reproducibility without rerunning the whole test, run
`check_v3_reproducibility.yml`. It confirms that the v3 model with its
drift terms switched off is exactly the v2 model, and reports how much a
score varies between processor models with the terms on (up to about 0.02;
every result records the processor that produced it).

## 3. Run locally

Requirements: Python 3.11.18 (the version every recorded run used) and an
internet connection to NCES (IPEDS) and the College Scorecard.

```
pip install -r "requirements v2 lock.txt"
cd src
python v3_test_results.py
```

`v3_test_results.py` reads the committed classifier, test list and scores
from `data/v3/` and downloads the IPEDS header files to read outcomes, so it
reproduces the verdicts without rescoring. Rescoring locally is possible
(see the commands inside each workflow file in `.github/workflows/`) but
takes many hours; the workflows split it across machines.

## 4. The theory

The model implements Recursive Information-Container Dynamics (RICD). The
current manuscript is in [`docs/`](<../docs/>): the Spine (the core engine) and
the Catalog (further mechanisms, edge cases and audit protocols), each as
`.docx` and `.tex`.
