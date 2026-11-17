"""
Diagnostic: does installing PyMC/PyTensor through conda-forge (which
links against a real, optimized BLAS implementation) resolve the
Thomas Aquinas College reproducibility instability -- as opposed to
the pip install used everywhere else in this investigation, which
produces the "PyTensor could not link to a BLAS installation...
severely degraded" warning on every single run?

Runs N independent replicates of Thomas Aquinas College (UNITID
124292) at real production settings (cores=1, the same setting
score_institution.py's own CLI and score_batch.py now use), and
reports frac_high_entropy plus the CONVERGENCE line (divergence
count, max rhat) for each replicate.

N=10, not 5 -- per the standing "always double-check" rule from this
same investigation: a 5/5 clean replication at cores=2 was earlier
treated as settled, then directly contradicted by an equally clean
5/5 at cores=1 showing the opposite value. A larger sample here is
deliberate, not arbitrary.
"""

from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
N_REPLICATES = 10


def main():
    results = []
    for i in range(1, N_REPLICATES + 1):
        print(f"\n=== Replicate {i}/{N_REPLICATES} ===")
        features = compute_features_for_institution(UNITID, NAME, cores=1)
        if features is None:
            print(f"Replicate {i}: returned None (insufficient live data) -- "
                  f"not counted in the camp tally below.")
            continue
        results.append(features.frac_high_entropy)
        print(f"Replicate {i} frac_high_entropy: {features.frac_high_entropy:.4f}")

    print("\n=== SUMMARY ===")
    print(f"Valid replicates: {len(results)}/{N_REPLICATES}")
    print(f"All frac_high_entropy values: {results}")
    high_count = sum(1 for r in results if r > 0.5)
    low_count = len(results) - high_count
    print(f"HIGH camp (frac_high_entropy > 0.5): {high_count}/{len(results)}")
    print(f"LOW camp (frac_high_entropy <= 0.5): {low_count}/{len(results)}")
    if high_count == 0 and low_count > 0:
        print("RESULT: fully consistent LOW under the conda/BLAS environment -- "
              "consistent with the BLAS fix resolving the instability. Still only "
              "one environment's worth of evidence -- see the standing double-check rule.")
    elif low_count == 0 and high_count > 0:
        print("RESULT: fully consistent HIGH under the conda/BLAS environment.")
    elif high_count > 0 and low_count > 0:
        print("RESULT: STILL SPLIT between camps under the conda/BLAS environment -- "
              "the BLAS fix alone does NOT resolve the instability.")
    else:
        print("RESULT: no valid replicates -- cannot conclude anything.")


if __name__ == "__main__":
    main()
