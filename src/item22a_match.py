"""
Item 22a, step three: match each nursing program in data/item 22a/pass_rates.csv
to its IPEDS unit ID (protocols/nursing and pharmacy protocol.md, section 2:
by normalized name and state, then by a fixed hand list, as in item 15b).

Only the IPEDS institutional directory (HD files) is read here: names,
aliases, cities and states. No completions file is opened, so no program is
matched by its values.

Matching, in order:
  1. a hand entry in data/item 22a/name crosswalk.csv (how = hand) is kept
     as written;
  2. otherwise the board's name, normalized, is looked up among the IPEDS
     names and aliases of the same state in HD2013 to HD2021 (the exam years
     plus one, so programs that closed are still found); first the whole
     name, then the name without its last " - " part (a campus or level), and
     a match is accepted only if exactly one unit ID answers;
  3. otherwise the program is written as unmatched, with up to eight
     candidate unit IDs of the same state in data/item 22a/match_candidates.csv
     (institutions sharing the name's distinctive words), for the hand list.

A hand entry may name several unit IDs separated by ";" only where the
protocol allows a combination; it may also say "leave out" with a reason in
the note. Nothing in the hand list is decided by pass rates or completions.

Outputs:
  data/item 22a/name crosswalk.csv     one row per state, level, board section and program
  data/item 22a/match_candidates.csv   candidates for the programs still unmatched
  data/item 22a/ipeds_directory.csv    the HD rows read (four states), for the record

Run from src/ (GitHub Actions, item22a_parse_match.yml):  python item22a_match.py
"""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from pathlib import Path

import meta_channel as mc

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "item 22a"
RATES = DATA / "pass_rates.csv"
CROSSWALK = DATA / "name crosswalk.csv"
CANDIDATES = DATA / "match_candidates.csv"
DIRECTORY = DATA / "ipeds_directory.csv"
STATES = ("IN", "TX", "OK", "FL")
HD_YEARS = range(2013, 2022)
FIELDS = ["state", "level", "board_section", "board_program", "unitid", "ipeds_name", "how", "note"]
STOP = {"of", "and", "the", "at", "in", "for", "college", "university", "school", "nursing",
        "community", "state", "inc", "llc", "campus", "health", "institute", "center"}
ABBREV = [(r"\bokla\b", "oklahoma"), (r"\bok\b", "oklahoma"), (r"\btx\b", "texas"),
          (r"\buniv\b", "university"), (r"\bhsc\b", "health science center"),
          (r"\but\b", "university of texas"), (r"\bft\b", "fort"), (r"\bmt\b", "mount")]


def norm(name: str) -> str:
    s = name.lower().replace("&", " and ").replace("’", "'").replace("@", " at ")
    s = re.sub(r"\(us\d{8}\)", " ", s)
    s = re.sub(r"\((formerly|now)[^)]*\)", " ", s)
    s = re.sub(r"\bsaint\b|\bst\.", "st", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    for a, b in ABBREV:
        s = re.sub(a, b, s)
    s = re.sub(r"\bthe\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def variants(board: str) -> list[str]:
    """The whole name, then the name without its last ' - ' part; Florida's
    level tag and program code are dropped first."""
    b = re.sub(r"\s*\(US\d{8}\)\s*$", "", board)
    b = re.sub(r"\s+-\s+(ADN|ASN|AS|BSN|BS|DIPLOMA|MSN|PN)\s*$", "", b)
    out = [norm(b)]
    if " - " in b:
        out.append(norm(b.rsplit(" - ", 1)[0]))
    return [v for i, v in enumerate(out) if v and v not in out[:i]]


def directory() -> dict:
    """{unitid: {"names": set, "city": set, "state": str, "years": [..]}}"""
    units: dict = {}
    rows = []
    for y in HD_YEARS:
        got = mc.fetch(f"HD{y}.zip", True)
        _, text = mc.first_csv(got[0])
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            r = {k.strip().lstrip("﻿").lstrip("ï»¿").upper(): (v or "").strip() for k, v in r.items() if k}
            st = r.get("STABBR", "")
            if st not in STATES:
                continue
            u = r["UNITID"]
            e = units.setdefault(u, {"names": set(), "city": set(), "state": st, "years": [], "instnm": ""})
            e["names"].add(r.get("INSTNM", ""))
            e["instnm"] = r.get("INSTNM", "")      # the latest year's name
            for a in re.split(r"[|;,]", r.get("IALIAS", "")):
                if a.strip():
                    e["names"].add(a.strip())
            e["city"].add(r.get("CITY", ""))
            e["years"].append(y)
            rows.append({"year": y, "unitid": u, "name": r.get("INSTNM", ""), "alias": r.get("IALIAS", ""),
                         "city": r.get("CITY", ""), "state": st, "system": r.get("F1SYSNAM", ""),
                         "closed": r.get("CLOSEDAT", ""), "sector": r.get("SECTOR", "")})
    with open(DIRECTORY, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return units


def main() -> None:
    programs = {}
    with open(RATES, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            programs[(r["state"], r["level"], r["board_section"], r["program"])] = True
    hand = {}
    if CROSSWALK.exists():
        with open(CROSSWALK, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["how"] == "hand":
                    hand[(r["state"], r["level"], r["board_section"], r["board_program"])] = r
    units = directory()
    index = defaultdict(set)
    for u, e in units.items():
        for n in e["names"]:
            index[(e["state"], norm(n))].add(u)

    out, cands = [], []
    for key in sorted(programs):
        st, level, section, board = key
        if key in hand:
            out.append(hand[key])
            continue
        row = dict(zip(FIELDS, [st, level, section, board, "", "", "unmatched", ""]))
        for v in variants(board):
            hits = index.get((st, v), set())
            if len(hits) == 1:
                u = next(iter(hits))
                row.update(unitid=u, ipeds_name=units[u]["instnm"], how="auto",
                           note="whole name" if v == variants(board)[0] else "name without its last part")
                break
            if len(hits) > 1:
                row["note"] = "more than one unit ID: " + ";".join(sorted(hits))
                break
        out.append(row)
        if row["how"] == "unmatched":
            words = [w for w in variants(board)[0].split() if w not in STOP and len(w) > 2]
            scored = []
            for u, e in units.items():
                if e["state"] != st:
                    continue
                toks = set(" ".join(norm(n) for n in e["names"] | e["city"]).split())
                s = sum(w in toks for w in words)
                if s:
                    scored.append((-s, u))
            for s, u in sorted(scored)[:8]:
                e = units[u]
                cands.append({"state": st, "level": level, "board_section": section, "board_program": board,
                              "candidate_unitid": u, "candidate_names": " | ".join(sorted(e["names"])),
                              "candidate_city": " | ".join(sorted(e["city"])),
                              "header_years": f"{min(e['years'])}-{max(e['years'])}", "words_shared": -s})
    with open(CROSSWALK, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    with open(CANDIDATES, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["state", "level", "board_section", "board_program", "candidate_unitid",
                                           "candidate_names", "candidate_city", "header_years", "words_shared"])
        w.writeheader()
        w.writerows(cands)
    n = defaultdict(int)
    for r in out:
        n[r["how"]] += 1
    print(f"{len(out)} programs: " + ", ".join(f"{k} {v}" for k, v in sorted(n.items())))


if __name__ == "__main__":
    main()
