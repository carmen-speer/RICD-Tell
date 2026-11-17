"""
Batch-position isolation test for Thomas Aquinas College (UNITID
124292) -- the direct test of a new hypothesis raised by the real
2026-09-23 production rescore run: every isolated cores=1 test of
Thomas Aquinas alone (in a fresh process, as the only institution
scored) gave the same clean, reproducible answer seven times running
(frac_high_entropy=0.0000, ~66-69% probability high_risk, 0
divergences). But the real production batch run -- which scores all
15 institutions sequentially in ONE process, and reaches Thomas
Aquinas 11th, after 10 other institutions have already gone through
PyMC sampling in that same process -- gave the opposite result (153
divergences, frac_high_entropy=1.0000, 95.5081%), even though it also
used cores=1. Every OTHER institution in that same batch run matched
its previously-established number exactly, so this isn't a general
batch-vs-isolated problem -- it looks specific to Thomas Aquinas.

This tests that directly, within a single script run (so both
conditions share the same GitHub Actions runner, same software
environment, same everything except "how many prior institutions were
scored in this process before reaching Thomas Aquinas"):

1. COLD: score Thomas Aquinas first, as the very first call in this
   process -- exactly like every prior isolated diagnostic did.
2. Then score the 10 institutions that precede it in score_batch.py's
   own INSTITUTIONS list, in the same order, at cores=1 -- not to
   check their results (already confirmed correct in the real batch
   run), just to put this process into the same "10 prior institutions
   already sampled" state the real batch run was in when it reached
   Thomas Aquinas.
3. WARM: score Thomas Aquinas again, now as the 11th call in this same
   process -- matching its real position in score_batch.py.

If COLD and WARM disagree with each other in this single run, that's
direct, clean confirmation that something about prior in-process PyMC
sampling activity -- not cores, not the runner, not random chance --
is what flips this specific institution's result. If they agree, the
real batch run's 95.5081% was something else (most likely real
runner-to-runner variability), and this hypothesis is ruled out.

Requires score_institution.py's compute_features_for_institution to
already have the cores parameter (2026-09-23) -- commit that file
first, or this will fail with a TypeError.
"""

from __future__ import annotations
from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

TA_UNITID = "124292"
TA_NAME = "Thomas Aquinas College"
TA_SECTOR = "private"
TA_START_YEAR = 2013

# The 10 institutions that precede Thomas Aquinas in score_batch.py's
# own INSTITUTIONS list, in the same order -- copied from that file,
# not re-derived, so this process reaches the same state the real
# batch run was in.
PRECEDING_INSTITUTIONS = [
    ("233718", "Sweet Briar College", "private", 2013),
    ("484613", "University of Phoenix-Arizona", "forprofit", 2014),
    ("238032", "West Virginia University", "public", 2013),
    ("225511", "University of Houston", "public", 2013),
    ("110583", "California State University-Long Beach", "public", 2013),
    ("217882", "Clemson University", "public", 2013),
    ("132903", "University of Central Florida", "public", 2013),
    ("134097", "Florida State University", "public", 2013),
    ("211291", "Bucknell University", "private", 2013),
    ("212911", "Haverford College", "private", 2013),
]


def score_thomas_aquinas(clf, label):
    print(f"--- Scoring Thomas Aquinas College ({label}) ---")
    features = compute_features_for_institution(
        TA_UNITID, TA_NAME, sector=TA_SECTOR, start_year=TA_START_YEAR, cores=1,
    )
    if features is None:
        print(f"INSUFFICIENT DATA ({label}) -- unexpected; stopping.")
        return None
    result = clf.classify(features)
    print(f"[{label}] frac_high_entropy = {features.frac_high_entropy:.4f}")
    print(f"[{label}] classification = {'high_risk' if result.prediction == 1 else 'stable'} "
          f"({result.probability:.4%} probability high_risk)")
    return features.frac_high_entropy, result.probability


def main():
    panel = load_panel("../data/panel/panel.json")
    clf = RICDClassifier()
    clf.fit(panel)

    print("=" * 70)
    print("BATCH-POSITION ISOLATION TEST (cores=1 throughout)")
    print("=" * 70)

    cold = score_thomas_aquinas(clf, "COLD -- first call in process")

    print("=" * 70)
    print(f"Scoring {len(PRECEDING_INSTITUTIONS)} preceding institutions, to reach "
          f"the same in-process state the real batch run was in at Thomas Aquinas's "
          f"real position (11th)...")
    print("=" * 70)
    for unitid, name, sector, start_year in PRECEDING_INSTITUTIONS:
        print(f"--- Warming up: {name} ({unitid}) ---")
        compute_features_for_institution(
            unitid, name, sector=sector, start_year=start_year, cores=1,
        )

    print("=" * 70)
    warm = score_thomas_aquinas(clf, "WARM -- 11th call in process, after the 10 above")

    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    if cold is not None and warm is not None:
        print(f"COLD: frac_high_entropy={cold[0]:.4f}, probability={cold[1]:.4%}")
        print(f"WARM: frac_high_entropy={warm[0]:.4f}, probability={warm[1]:.4%}")
        if abs(cold[0] - warm[0]) > 0.01:
            print(
                "COLD and WARM disagree within this single run -- direct confirmation "
                "that prior in-process sampling activity (not cores, not the runner) "
                "flips this institution's result."
            )
        else:
            print(
                "COLD and WARM agree within this single run -- the real batch run's "
                "95.5081% was NOT caused by batch position; something else (most "
                "likely real runner-to-runner variability) is the actual cause."
            )


if __name__ == "__main__":
    main()
