name: Replicate Thomas Aquinas College (reproducibility check)

# Manual-only diagnostic. Calls compute_features_for_institution() for
# Thomas Aquinas College (124292) multiple times in a row at identical
# nominal production settings (300/300/2/0.9, same hardcoded
# random_seed=7 score_institution.py already uses) to test whether
# "the same settings" actually reproduces "the same result." Built
# because diagnose_thomas_aquinas.py's Step 1 (comparing production
# vs. high-precision settings within one run) found frac_high_entropy
# identical at 0.0000 -- but a real, separate 2026-09-22 batch run at
# the same nominal production settings got 1.0000. See
# src/diagnose_thomas_aquinas_replication.py's own module docstring
# for the full reasoning, including why this could affect every other
# "identical across settings" resolution already documented in this
# project, not just this institution.
#
# Does not touch panel.json, dynamics.py, classifier.py,
# score_institution.py, docs/data/live_scores.json, or the public
# dashboard. Diagnostic only.
on:
  workflow_dispatch:

jobs:
  diagnose:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run replication check for Thomas Aquinas College
        env:
          COLLEGE_SCORECARD_API_KEY: ${{ secrets.COLLEGE_SCORECARD_API_KEY }}
        run: |
          cd src
          python diagnose_thomas_aquinas_replication.py
