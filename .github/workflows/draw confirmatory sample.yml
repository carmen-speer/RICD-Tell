name: Draw confirmatory sample

# Runs "src/draw confirmatory sample.py" once, by hand, to draw the
# 300-institution confirmatory sample under "sampling protocol.md",
# then commits the draw log and slot list to data/confirmatory/ so the
# draw is fixed and timestamped before anything is scored.
#
# Manual only (no schedule): the draw happens exactly once. The script
# itself refuses to run again once its files exist.
on:
  workflow_dispatch: {}

# Lets the final step push its commit back to the repository.
permissions:
  contents: write

jobs:
  draw:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install requests

      - name: Draw the sample
        run: python "src/draw confirmatory sample.py"

      - name: Commit the draw
        run: |
          git config user.name "ricd-tracker-bot"
          git config user.email "actions@github.com"
          git add data/confirmatory
          if git diff --staged --quiet; then
            echo "Nothing to commit -- the draw produced no files."
            exit 1
          fi
          git commit -m "Confirmatory sample draw (sampling protocol.md)"
          git fetch origin main
          git rebase origin/main
          git push
