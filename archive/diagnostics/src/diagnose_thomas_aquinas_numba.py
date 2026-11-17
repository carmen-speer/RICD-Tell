"""
Diagnostic: does compiling the MCMC sampler through PyTensor's Numba
backend (compile_mode="NUMBA"), instead of its default C-compiled path,
avoid the reproducibility instability confirmed in
diagnose_thomas_aquinas_pinned_env.py?

The pinned-environment diagnostic ruled out environment drift as the
cause: three separate job dispatches of a byte-identical Docker image
(same pinned dependency versions, same fixed random_seed=7) still split
two ways -- two runs agreeing at rhat=1.3016/frac_high_entropy=0.0000,
one landing at rhat=3.2258/153 divergences/frac_high_entropy=1.0000.
With software pinned identical, the remaining explanation is
hardware/numerics-level: PyTensor's default path here is its own
"severely degraded" non-BLAS-linked fallback (see the warning printed
on every single run in this entire investigation), which is exactly
the kind of unoptimized, less-tested math most likely to behave
differently across different underlying CPU hardware.

PyTensor's own warning names Numba and JAX as alternative backends that
"perform their own BLAS optimizations" instead of routing through that
fragile fallback. This diagnostic tests Numba specifically: a
different compiled code path, not just a different BLAS library, so if
it stays stable across separate dispatches where the default C path
did not, that's real evidence the instability lives specifically in
PyTensor's default fallback path rather than being an unavoidable
property of this model or this institution's data.

DIRECT MODE CONFIRMATION (2026-09-22 addition): the first three real
Numba dispatches all agreed (rhat=1.2398 exactly, three separate times)
and ran 4-5x faster than the default-path runs -- but the "PyTensor
could not link to a BLAS installation" warning kept printing anyway,
which is ambiguous on its own (that warning fires from PyTensor's own
BLAS-detection check, not necessarily tied to which mode a specific
compile call ends up using). Rather than keep inferring engagement
indirectly from timing and warning text, _confirm_compile_mode()
below independently compiles a trivial PyTensor function with the
same mode string, using PyTensor's own base-level pytensor.function()
API rather than going through pm.sample(), and prints the actual
linker class it gets back -- direct, positive confirmation instead of
inference from side effects.

ONE evaluation per dispatch, not several replicates -- replicates
within a single job are guaranteed to agree with each other regardless
of anything, since random_seed=7 is fixed (confirmed by the extreme-
precision diagnostic's three identical replicates). The real test is
running THIS workflow several separate times and comparing results
across those separate dispatches, exactly how the pinned-environment
diagnostic was actually evaluated.
"""

import pytensor
import pytensor.tensor as pt

from score_institution import compute_features_for_institution

UNITID = "124292"
NAME = "Thomas Aquinas College"
COMPILE_MODE = "NUMBA"


def _confirm_compile_mode(mode):
    """
    Compiles a trivial function (f(x) = x * 2) with the given mode and
    prints the actual linker class PyTensor produced. This is
    independent of pm.sample() and of this project's model code
    entirely -- it only tests whether PyTensor itself honors this mode
    string in this environment. A linker class name containing "Numba"
    confirms real engagement; anything else (e.g. falling back to the
    default CLinker/VMLinker) means the mode request was silently
    ignored, which the rest of this script's output alone couldn't
    have told us.
    """
    x = pt.dscalar("x")
    f = pytensor.function([x], x * 2, mode=mode)
    linker = f.maker.linker
    linker_name = f"{type(linker).__module__}.{type(linker).__name__}"
    print(f"COMPILE MODE CHECK: requested mode={mode!r} -> actual linker class={linker_name}")
    if "numba" in linker_name.lower():
        print("COMPILE MODE CHECK: CONFIRMED -- Numba linker really is engaged.")
    else:
        print("COMPILE MODE CHECK: NOT CONFIRMED -- this did not produce a Numba "
              "linker. The mode request may be silently falling back to the "
              "default path; the CONVERGENCE result below should not be trusted "
              "as a real Numba-backend result until this is resolved.")


def main():
    _confirm_compile_mode(COMPILE_MODE)

    features = compute_features_for_institution(UNITID, NAME, cores=1, compile_mode=COMPILE_MODE)
    if features is None:
        print("Diagnostic inconclusive: returned None (insufficient live data).")
        return
    print(f"\nfrac_high_entropy: {features.frac_high_entropy:.4f}")
    print("Compare this run's CONVERGENCE line above and this "
          "frac_high_entropy value against OTHER SEPARATE dispatches "
          "of this same workflow.")


if __name__ == "__main__":
    main()
