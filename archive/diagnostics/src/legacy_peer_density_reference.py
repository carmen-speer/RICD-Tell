"""
Real peer-density diagnostic, built from data already in hand -- not an
invented feature vector. Answers a concrete question: for a stalled
case, which existing panel institutions are its closest real
structural peers, and how many real peers does it actually have?

Uses two real, already-available fields per institution:
  - sector: public vs private (already known per institution from
    which finance form -- F1A vs F2 -- was used to extract its data)
  - scale: peak undergraduate enrollment across the observed window
    (already in scorecard_raw.csv for every institution)

This is deliberately a first, honest version using only data already
extracted -- not a promise of a complete typology. Carnegie
Classification (research intensity, degree focus) would be a real,
valuable third dimension to add later via a fresh IPEDS HD pull, not
fabricated here.
"""

import csv
import numpy as np


PUBLIC_UIDS = {
    '162928', '166027', '215062', '190415', '199120', '134130', '240444',
    '198419', '227757', '221999', '130794', '186131', '131496', '168342',
    '164465', '216287', '153384', '149781', '185262', '185129', '145646',
    '170976', '234076',
}
# All others in the panel are private; this set is built from which
# finance form (F1A = public) was actually used during extraction this
# session, not guessed.


def get_peak_enrollment(scorecard_path, uid):
    with open(scorecard_path) as f:
        reader = csv.DictReader(f)
        vals = [
            int(row['n_undergrads']) for row in reader
            if row['id'] == uid and row['n_undergrads'].strip()
        ]
    return max(vals) if vals else None


def peer_density_report(scorecard_path, target_uid, target_name, panel_uids_names,
                         scale_radius_ratio=2.0, min_peers=3):
    """
    For a target institution, finds how many real panel peers share its
    sector and fall within scale_radius_ratio of its size (e.g. 2.0
    means peers between half and double its enrollment). Reports the
    count and, if below min_peers, names the closest few real
    institutions actually in the panel as the concrete gap.
    """
    target_public = target_uid in PUBLIC_UIDS
    target_scale = get_peak_enrollment(scorecard_path, target_uid)
    if target_scale is None:
        return {"status": "ERROR", "message": f"No enrollment data for {target_name}"}

    candidates = []
    for uid, name in panel_uids_names:
        if uid == target_uid:
            continue
        is_public = uid in PUBLIC_UIDS
        scale = get_peak_enrollment(scorecard_path, uid)
        if scale is None:
            continue
        same_sector = (is_public == target_public)
        ratio = max(scale, target_scale) / min(scale, target_scale)
        within_scale = ratio <= scale_radius_ratio
        candidates.append((name, is_public, scale, ratio, same_sector and within_scale))

    real_peers = [c for c in candidates if c[4]]
    candidates_sorted = sorted(candidates, key=lambda c: (not c[1] == target_public, c[3]))

    result = {
        "target": target_name,
        "sector": "public" if target_public else "private",
        "peak_enrollment": target_scale,
        "real_peer_count": len(real_peers),
        "status": "PASS" if len(real_peers) >= min_peers else "HOLD",
    }
    if result["status"] == "HOLD":
        result["closest_real_candidates_in_panel"] = [
            {"name": n, "sector": "public" if p else "private", "peak_enrollment": s, "scale_ratio": round(r, 2)}
            for n, p, s, r, _ in candidates_sorted[:5]
        ]
    return result
