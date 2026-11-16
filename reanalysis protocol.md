# Reanalysis Protocol: Tracker v3 with the Two-Channel Scoring Model

This protocol is committed before any part of the reanalysis is run. It is
exploratory: the outcomes of every institution it uses are already known
from the v3 test (`data/v3/test results.json`), so nothing here is a test,
and nothing here changes a verdict of `sampling protocol v3.md`. Every
result is reported in full, whichever way it comes out.

## The error it corrects

The scoring model takes divergence as the largest of three gaps between the
official, operational and meta channels, D_total = max(D_op, D_om, D_pm).
No institution's meta channel P_m has been measured, and where it is not
measured `src/model.py` sets it to a constant that evaluates to 1.5, outside
the range [0, 1] of the other channels. The two gaps involving P_m are then
each at least 0.5 and always the largest, so in every test so far the
tracker's divergence, and the stress and resource-debt terms it drives,
measured how low an institution's tuition and completion figures were
rather than how far its official and operational layers had split. The RICD
divergence mechanism has therefore not yet been tested.

## The two-channel model

`src/model_two_channel.py` is `src/model.py` with one change: where P_m is
not measured, the two gaps involving it are left out and D_total = D_op,
the official–operational gap alone. This is the reading of the RICD Spine,
which treats the three-channel calculation as undetermined without P_m; a
formal definition of this reduced mode is added to the Spine in the next
manuscript version. Where P_m is measured, the two models are identical.

`src/model.py` and every other file frozen with classifier v3 are left
unchanged, so the v3 test stays reproducible. `src/reanalysis.py` runs the
v3 scripts unchanged, with three redirections: the scoring model is the
two-channel model; every output goes to `data/v3 reanalysis/`; and the
pipeline-file fingerprint the v3 freeze checks use also covers
`model_two_channel.py` and `reanalysis.py`.

## What is rerun

1. **Rescoring** (`reanalysis_rescore.yml`, "reanalysis 1 - rescore with
   the two-channel model"): the 670 development institutions of protocol v3
   and every v3 test institution that was not structurally unscorable, once
   each at seed 7, with the two-channel model, in their own processes with
   empty compile caches, on the same finance forms and windows as before.
   Results go to `data/v3 reanalysis/rescored/`.
2. **Refit, test scoring and results** (`reanalysis_finish.yml`,
   "reanalysis 2 - refit, rescore the test list and results"):
   - classifier v3, the size-and-sector baseline and the anchor sensor are
     refitted on the two-channel development results by exactly the frozen
     procedure of protocol v3, including its cross-validated cuts and
     random seeds (`data/v3 reanalysis/classifier.json`);
   - they are applied to the two-channel results of the v3 test
     institutions exactly as phase 3 applied the frozen models
     (`data/v3 reanalysis/test scores/`);
   - the phase 5 measures, triggers R1 to R6, the second verdict and the
     two anchor tests are recomputed with the same code and seeds
     (`data/v3 reanalysis/test outcomes.json`,
     `data/v3 reanalysis/test results.json`).

## What is compared

Each of the following is reported beside its value in the v3 test:

- the overall result: sensitivity, false-alarm rate, J and its interval,
  and the six triggers;
- the result among public and private nonprofit institutions alone;
- the second verdict: whether, among public and private nonprofit
  institutions, the refitted classifier ranks institutions better than the
  size-and-sector baseline (area under the ROC curve, paired bootstrap);
- the two anchor tests.

The question the reanalysis asks is whether the tracker's own features gain
ground on size and sector once divergence measures official–operational
divergence. A gain, a loss or no change are all reported. Because the
outcomes are known, a gain here would justify carrying the two-channel
model into the next blind test; it would not establish the gain.

## What comes after

The next blind test is prospective. Every institution is scored on the
newest available data, with the meta channel measured from the full-time
share of instructional staff (IPEDS human-resources data, the input the
model was built to take), checked before use, and the scores, flags and a
protocol are committed before the National Center for Education Statistics
releases the 2026–27 institutional header file (HD2026), expected around
late July 2027. Closures first appearing in that file judge the committed
flags blind, and they are judged again as each later header file is
released.
