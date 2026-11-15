"""
Shared settings for "sampling protocol v3.md".

The v3 scoring pipeline is the v2 pipeline with the drift-type and
shock-type collapse terms of RICD §10.3a switched on (drift_terms=True in
score_institution.compute_features_for_institution, used through
v3_score_one.py). With the terms switched off, the model is exactly the v2
model, which the v3 reproducibility check confirms against committed v2
scores. Every v3 batch records the git blob hash of each file below, and
v3 scoring refuses to run if any differs from the hashes frozen with
classifier v3.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import v2_common as v2

V3_DIR = v2.ROOT / "data" / "v3"
PIPELINE_FILES = ("score_institution.py", "model.py", "fetch_live_data.py", "real_adapter.py",
                  "dynamics.py", "jump_diffusion.py", "v2_common.py", "v3_score_one.py")
DRIFT_FEATURES = ("enroll_drift", "slide_rate", "collapse_urgency", "coverage_final", "enroll_jump_recent")


def pipeline_hashes() -> dict:
    src = Path(__file__).resolve().parent
    out = {f: subprocess.run(["git", "hash-object", str(src / f)], capture_output=True, text=True,
                             check=True).stdout.strip() for f in PIPELINE_FILES}
    out["requirements v2 lock.txt"] = subprocess.run(
        ["git", "hash-object", str(v2.ROOT / "requirements v2 lock.txt")],
        capture_output=True, text=True, check=True).stdout.strip()
    return out
