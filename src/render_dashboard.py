"""
Bakes docs/data/live v3 scores.json (the live tracker's results, "live
tracker protocol.md") into docs/index.html as static HTML, so anything
that reads the page's raw source without running its script -- an AI
summarizer, a search-engine crawler, a screen reader -- sees the actual
scores: the four counts, every row, and the date. The page's own script
still runs in a browser and re-renders the same data with search, filters
and sorting.

Run by score_live.yml after each merge and by the weekly workflow
(rescore.yml), so the static HTML and the JSON it is baked from never
drift apart. If the scores file is missing or empty, the page keeps its
"scores are being computed" state; no row is invented.
"""
from __future__ import annotations

import html as h
import json
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
INDEX = DOCS / "index.html"
SCORES = DOCS / "data" / "live v3 scores.json"
ROWS_START = "<!-- STATIC_LIVE_ROWS_START -->"
ROWS_END = "<!-- STATIC_LIVE_ROWS_END -->"
SECTOR = {"public": "Public", "private": "Private nonprofit", "forprofit": "For-profit"}
READING = {"flag": "Flagged", "clear": "Flag cleared by anchors", "ok": "Not flagged", "none": "Not scorable"}
RANK = {"flag": 0, "clear": 1, "ok": 2, "none": 3}


def reading(d: dict) -> str:
    if d.get("status") != "scored" or d.get("score") is None:
        return "none"
    if d.get("anchored flag"):
        return "flag"
    if d.get("flag"):
        return "clear"
    return "ok"


def pct(x) -> str:
    return f"{x * 100:.1f}%" if isinstance(x, (int, float)) else "—"


def anchors_text(a: dict | None) -> str:
    if not a:
        return "—"
    parts = []
    if (a.get("f_approp") or 0) > 0:
        parts.append(f"appropriations {a['f_approp'] * 100:.0f}%")
    if (a.get("f_gift") or 0) > 0:
        parts.append(f"gifts {a['f_gift'] * 100:.0f}%")
    if a.get("S_par"):
        parts.append("system member")
    return ", ".join(parts) if parts else "none recorded"


def row(d: dict, r: str) -> str:
    reason = f'<br><span class="small">{h.escape(d.get("reason") or "")}</span>' if r == "none" and d.get("reason") else ""
    return (f'<tr><td>{h.escape(d.get("name") or "")}</td><td>{h.escape(d.get("state") or "")}</td>'
            f'<td>{h.escape(SECTOR.get(d.get("sector"), d.get("sector") or ""))}</td>'
            f'<td class="r-{r}">{READING[r]}{reason}</td><td class="num">{pct(d.get("score"))}</td>'
            f'<td class="num">{pct(d.get("anchored score"))}</td><td>{h.escape(anchors_text(d.get("anchor inputs")))}</td></tr>')


def set_text(page: str, element_id: str, text: str) -> str:
    return re.sub(rf'(id="{element_id}"[^>]*>)[^<]*(<)', lambda m: m.group(1) + h.escape(text) + m.group(2), page, count=1)


def main() -> None:
    page = INDEX.read_text(encoding="utf-8")
    data = json.loads(SCORES.read_text(encoding="utf-8")) if SCORES.exists() else {}
    colleges = data.get("colleges") or []
    start = page.index(ROWS_START) + len(ROWS_START)
    end = page.index(ROWS_END)
    if not colleges:
        page = page[:start] + "\n" + page[end:]
        INDEX.write_text(page, encoding="utf-8")
        print("No live v3 scores yet; the page keeps its waiting state.")
        return
    rs = [(d, reading(d)) for d in colleges]
    rs.sort(key=lambda x: (RANK[x[1]], (x[0].get("name") or "").lower()))
    page = page[:start] + "\n" + "\n".join(row(d, r) for d, r in rs) + "\n" + page[end:]
    count = {k: sum(1 for _, r in rs if r == k) for k in READING}
    page = set_text(page, "m-scored", f"{len(rs) - count['none']:,}")
    page = set_text(page, "m-flag", f"{count['flag']:,}")
    page = set_text(page, "m-clear", f"{count['clear']:,}")
    page = set_text(page, "m-ok", f"{count['ok']:,}")
    page = set_text(page, "status", f"Showing {len(rs):,} colleges.")
    total = data.get("colleges in the frame")
    upd = (data.get("updated (UTC)") or "")[:10]
    page = set_text(page, "updated", f"Window: {data.get('window', 'fiscal years 2014-2024')}. "
                    + (f"{len(rs):,} of {total:,} colleges in the frame have a result. " if total else "")
                    + (f"Updated {upd}." if upd else ""))
    page = page.replace('<table id="t" style="display:none;">', '<table id="t" style="display:table;">', 1)
    INDEX.write_text(page, encoding="utf-8")
    print(f"Baked {len(rs)} colleges into {INDEX}.")


if __name__ == "__main__":
    main()
