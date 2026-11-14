"""
Scores one institution once under "sampling protocol v2.md" and writes the
result to a JSON file.

Run in its own process by the v2 scoring scripts, so that each fit starts
from whatever compile-cache state the calling script gives it (see the
protocol's amendments) and nothing carries over between institutions.
Uses the gap-tolerant pipeline (allow_gaps=True) and the protocol's
sampler settings. No outcome is read.

Usage:
    python v2_score_one.py --unitid U --name N --sector S --window training|test
                           --seed 7 --compact C --finance F --out O
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import traceback
from pathlib import Path

import v2_common as v2

FEATURES = ("d_A_trend", "d_A_final", "delta_R_final", "frac_high_entropy",
            "debt_spike", "delta_R_trend", "reserve_adequacy", "research_ratio")
CONV_RE = re.compile(r"CONVERGENCE: (\d+) divergences, max rhat=([0-9.]+|nan|inf)")
INSUFF_RE = re.compile(r"^(INSUFFICIENT [A-Z ]+?):(.*)$", re.M)


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("--unitid", "--name", "--sector", "--window", "--compact", "--finance", "--out"):
        ap.add_argument(a, required=True)
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()

    import fetch_live_data as fld
    from score_institution import compute_features_for_institution

    fld.use_bulk_scorecard(args.compact)
    v2.use_finance_cache(args.finance)
    win = v2.WINDOWS[args.window]

    buf = io.StringIO()
    out: dict = {"seed": args.seed}
    try:
        with contextlib.redirect_stdout(Tee(sys.stdout, buf)):
            feats = compute_features_for_institution(
                args.unitid, args.name, sector=args.sector, start_year=win["start_year"],
                end_year=win["end_year"], random_seed=args.seed, allow_gaps=True, **v2.SAMPLER)
    except Exception as e:
        out.update(status="error", error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc()[-2000:])
        Path(args.out).write_text(json.dumps(out))
        return
    log = buf.getvalue()
    m = CONV_RE.search(log)
    out["divergences"] = int(m.group(1)) if m else None
    out["rhat max"] = float(m.group(2)) if m else None
    if "real IPEDS download failed" in log:
        out.update(status="download failure")
    elif feats is None:
        reasons = INSUFF_RE.findall(log)
        out.update(status="unscorable",
                   reason=(reasons[0][0].lower() + ":" + reasons[0][1]) if reasons else "pipeline returned no features")
    else:
        out.update(status="scored", features={k: float(getattr(feats, k)) for k in FEATURES},
                   availability=getattr(feats, "availability", None))
    Path(args.out).write_text(json.dumps(out))


if __name__ == "__main__":
    main()
