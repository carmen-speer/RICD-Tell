"""
The two-step diagnostic plan for Clemson University and West Virginia
University, exactly as scoped in README Known Gaps ("Plan to resolve
Clemson and West Virginia (not yet executed)") -- not a new plan
invented here.

BACKGROUND: after the 2026-09-20 directional-entropy fix, both
institutions flipped from high_risk to stable in live scoring (Clemson
39.0%, West Virginia 44.2%, at production settings: n_draws=300,
n_tune=300, n_chains=2, target_accept=0.9) despite each carrying real,
independently documented financial distress -- Clemson's long-term
liabilities up $231.9M year-over-year to $2.65B with expenses
outpacing revenue; West Virginia's real 2023 financial crisis and
program/faculty cuts. Whether the new downside-only entropy measure
suppressed a real signal it used to (over)detect, or whether the
`stable` calls are themselves correct and consistent with the other
seven features, was left as an open question.

STEP 1 -- rule out ordinary MCMC non-convergence as a confound. Every
production-settings run on this project has shown real rhat > 1.01 and
low effective-sample-size warnings (see diagnose_window_mismatch.py's
own module docstring, which found and fixed the identical issue for
five other institutions). Re-runs both institutions at much higher
sampling settings (1000 draws, 1000 tune, 4 chains, target_accept=0.95
-- the same settings diagnose_window_mismatch.py already uses for
exactly this purpose) and reports whether frac_high_entropy holds near
its production-settings value or moves substantially. A substantial
move means the `stable` calls were, at least partly, a convergence
artifact, not a confirmed fix outcome.

STEP 2 -- compares each institution's full 8-feature vector against
the entire real, validated 54-institution panel using
RICDClassifier.peer_density() (an existing, already-built diagnostic
method in classifier.py, not new machinery) -- finds each
institution's 5 nearest real panel neighbors in standardized feature
space, with their real outcome (closure or stable) and distance. This
is a more direct implementation of the README's own instruction to
"compare their full 8-feature vectors against the validated panel's
real closures with a similar profile" than a fixed reference list
would be, since peer_density() searches the whole panel -- closures
included -- rather than only a hand-picked set of stable comparisons.
If Clemson's or West Virginia's real documented distress is legible to
any of the other seven features, their nearest neighbors in feature
space should include real closures. If their nearest neighbors are
overwhelmingly stable institutions even with frac_high_entropy set
aside, that is itself the real, honest answer: their distress isn't
legible to any of these eight features as currently constructed -- the
same kind of conclusion already documented for Buffalo, for an
entirely different underlying reason (see README Known Gaps).

Does NOT touch panel.json, dynamics.py, classifier.py,
score_institution.py, docs/data/live_scores.json, or the public
dashboard. Diagnostic only.

Requires COLLEGE_SCORECARD_API_KEY in the environment. Run via GitHub
Actions -- this project's sandboxed development environments cannot
reach NCES/College Scorecard.

Usage:
    python diagnose_clemson_wvu.py
"""

from __future__ import annotations

import traceback

from classifier import RICDClassifier, load_panel
from score_institution import compute_features_for_institution

TARGETS = [
    ("217882", "Clemson University", "public", 2013),
    ("238032", "West Virginia University", "public", 2013),
]

PRODUCTION_SETTINGS = dict(n_draws=300, n_tune=300, n_chains=2, target_accept=0.9)
HIGH_PRECISION_SETTINGS = dict(n_draws=1000, n_tune=1000, n_chains=4, target_accept=0.95)

# A move in frac_high_entropy larger than this between production and
# high-precision settings is read as a real, substantial shift, not
# ordinary run-to-run sampling noise.
SUBSTANTIAL_MOVE_THRESHOLD = 0.15

PANEL_PATH = "../data/panel/panel.json"


def run_and_classify(clf, unitid, name, sector, start_year, settings, label):
    print(f"\n--- {name} ({unitid}), {label} (n_draws={settings['n_draws']}, "
          f"n_tune={settings['n_tune']}, n_chains={settings['n_chains']}, "
          f"target_accept={settings['target_accept']}) ---")
    features = compute_features_for_institution(unitid, name, sector=sector, start_year=start_year, **settings)
    if features is None:
        print(f"  RESULT: insufficient_data at {label}.")
        return None
    result = clf.classify(features)
    pred = "high_risk" if result.prediction == 1 else "stable"
    prob_pct = result.probability * 100 if result.probability is not None else None
    print(f"  frac_high_entropy = {features.frac_high_entropy:.4f}")
    if prob_pct is not None:
        print(f"  classification = {pred} ({prob_pct:.1f}% probability high_risk)")
    else:
        print(f"  classification = {pred}")
    return features, result


def main():
    panel = load_panel(PANEL_PATH)
    clf = RICDClassifier()
    clf.fit(panel)

    print(f"{'=' * 100}\nSTEP 1: MCMC non-convergence check -- production settings vs. "
          f"high-precision settings\n{'=' * 100}")

    step1_features: dict[str, object] = {}
    for unitid, name, sector, start_year in TARGETS:
        print(f"\n{'#' * 100}\n{name} ({unitid})\n{'#' * 100}")
        try:
            prod = run_and_classify(clf, unitid, name, sector, start_year, PRODUCTION_SETTINGS, "PRODUCTION settings")
            hi = run_and_classify(clf, unitid, name, sector, start_year, HIGH_PRECISION_SETTINGS, "HIGH-PRECISION settings")
            if prod and hi:
                prod_feh = prod[0].frac_high_entropy
                hi_feh = hi[0].frac_high_entropy
                delta = hi_feh - prod_feh
                if abs(delta) > SUBSTANTIAL_MOVE_THRESHOLD:
                    verdict = "SUBSTANTIAL MOVE -- convergence artifact is a real, likely factor"
                else:
                    verdict = "HOLDS -- not a convergence artifact, the stable call is real"
                print(f"\n  frac_high_entropy: production={prod_feh:.4f} -> high-precision={hi_feh:.4f} "
                      f"(delta={delta:+.4f}) -- {verdict}")
                step1_features[unitid] = prod[0]  # production-settings feature vector, used in Step 2
            else:
                step1_features[unitid] = None
        except Exception as e:
            print(f"REAL ERROR on {name} ({unitid}): {type(e).__name__}: {e}")
            traceback.print_exc()
            step1_features[unitid] = None

    print(f"\n{'=' * 100}\nSTEP 2: feature-space peer comparison against the real validated "
          f"panel (closures included)\n{'=' * 100}")
    for unitid, name, sector, start_year in TARGETS:
        features = step1_features.get(unitid)
        if features is None:
            print(f"\n{name} ({unitid}): skipped -- no real feature vector from Step 1 to compare.")
            continue
        # peer_density() requires its target to already be present in the
        # panel list it's given -- temporarily append this live
        # institution's real, production-settings feature vector so its
        # neighbors can be found, without altering the real, checked-in
        # panel file on disk.
        temp_panel = panel + [features]
        neighbors = clf.peer_density(temp_panel, unitid, n_neighbors=5)
        print(f"\n{name} ({unitid}) -- 5 nearest real panel neighbors in standardized feature space:")
        closures_nearby = 0
        for peer_name, peer_outcome, dist in neighbors:
            print(f"  {peer_name:35s} outcome={peer_outcome:8s} distance={dist:.4f}")
            if peer_outcome == "closure":
                closures_nearby += 1
        print(f"  -> {closures_nearby} of 5 nearest real neighbors are confirmed closures.")

    print(f"\n{'=' * 100}")
    print("READING THIS RESULT:")
    print("If Step 1 shows a substantial frac_high_entropy move under higher sampling")
    print("precision, treat the `stable` call as unconfirmed pending a real fix to production")
    print("sampling settings -- not resolved either way.")
    print("If Step 1 holds but Step 2 finds real closures among the nearest neighbors, the")
    print("downside-only entropy construction likely needs a further correction elsewhere.")
    print("If Step 1 holds AND Step 2's nearest neighbors are overwhelmingly stable, that is")
    print("the real, honest answer: this institution's documented distress is not legible to")
    print("any of these eight features as currently constructed -- document it as such, the")
    print("same way Buffalo's gap is already documented, rather than forcing a fix that")
    print("doesn't exist yet.")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
