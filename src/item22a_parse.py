"""
Item 22a, step two: read the nursing pass-rate files in data/item 22a/raw/
into one table of program-years (protocols/nursing and pharmacy protocol.md,
sections 2 and 3, and Amendment 1). Nothing here touches IPEDS or any outcome.

What is read, by state (exam years 2014 to 2020, the years the test needs):

  Indiana   the board's BSN and ASN tables (several editions); passed and
            tested counts by school and year.
  Texas     the board's five-year tables (2020 and 2021 editions, and the
            2013 to 2017 copy); passed and total by program, in sections by
            program type.
  Oklahoma  the board's ten-year tables (three editions); first-time pass
            rates by campus and calendar year, without counts.
  Florida   the NCSBN fourth-quarter program reports (Report 4), one per exam
            year; annual counts are the sums of the quarterly Total rows
            (Amendment 1, decision 3). The 2016 report gives a year-to-date
            column (January to December) in place of the quarters; that column
            is used, since it is the same sum.

Checks. Where a board prints a rate beside the counts, passed / tested is
compared with it. Within 0.6 points (Indiana) or 0.06 points (Texas, which
prints two decimals), the counts are used. Off by up to 10 points, with
passed no larger than tested, the board's figures disagree with each other:
the printed rate is used as the pass rate, the tested count is kept for the
20-taker threshold, and the row is marked. Off by more than 10 points, or
with passed above tested, the count is a broken cell (a number split across
lines or mistyped): it is not used, and the row keeps the printed rate alone
if no other edition gives a clean count. Every such cell is listed. Where several editions give the same program and
year, the value given by the most editions is used and any disagreement is
listed (Indiana's 2014 to 2024 ASN edition, for one, prints some rows a year
off). Names are taken from the files; a few rows whose names the layout
splits are named by hand in NAME_FIXES below, each with the file and position.
Values are never typed in by hand.

Outputs:
  data/item 22a/pass_rates.csv     one row per state, program, level and exam year
  data/item 22a/parse_report.json  rejected cells, disagreements between
                                   editions, unnamed rows, excluded sections

Run from the repository root:  python src/item22a_parse.py
Needs pdfplumber and pdftotext (poppler-utils).
"""
import collections
import csv
import json
import os
import re
import subprocess

import pdfplumber

RAW = os.path.join("data", "item 22a", "raw")
OUT_CSV = os.path.join("data", "item 22a", "pass_rates.csv")
OUT_REPORT = os.path.join("data", "item 22a", "parse_report.json")
YEARS = range(2014, 2021)

report = collections.defaultdict(list)


def pdftext(name):
    return subprocess.run(["pdftotext", "-layout", os.path.join(RAW, name), "-"],
                          capture_output=True, text=True, check=True).stdout


def tidy(name):
    """Board name with layout debris removed: counts, rates, program codes,
    trailing hyphens. Dashes and apostrophes are made uniform."""
    n = re.sub(r"\(?\d+/\d+\)?|\b\d+(\.\d+)?%|(?<!US)\b\d{6,10}\b|20202020", " ", name)
    n = n.replace("–", "-").replace("’", "'")
    n = re.sub(r"\s*-\s*", " - ", n)
    return re.sub(r"\s+", " ", n).strip(" -")


# ---------------------------------------------------------------- Indiana
# The Indiana tables put a line of rates above a line of counts, with the
# school's name wrapped beside them. Words are read with their positions:
# each count is given to the year column nearest it, counts are grouped into
# rows, and name lines are given to the nearest row.

IND_FILES = ["indiana bsn 2015-2025.pdf", "indiana asn 2015-2025.pdf",
             "indiana bsn 2014-2024.pdf", "indiana asn 2014-2024.pdf",
             "indiana bsn 2013-2023.pdf", "indiana asn 2013-2023.pdf",
             "indiana asn 2010-2020.pdf"]
IND_COUNT = re.compile(r"\((\d+)\s*/\s*(\d+)\)?|^(\d+)/(\d+)\)?[_%(]*$")
IND_SKIP = ("CLOSED PROGRAMS", "* Percent", "*N/A", "Name of School", "NCLEX Mean",
            "Std. Deviation", "One std. deviation below", "Annual Pass Rates")

# Rows whose names the layout splits or shifts, named by hand from the file
# (file, page counted from 0, top of the row's first count line, rounded).
# An empty name leaves the row out (a stray line of counts already given in
# its own row); it is listed in the report.
NAME_FIXES = {
    ("indiana asn 2010-2020.pdf", 1, 421): "University of Saint Francis - Fort Wayne",
    ("indiana asn 2010-2020.pdf", 1, 444): "",
    ("indiana asn 2010-2020.pdf", 2, 301): "Harrison College - Indianapolis",
    ("indiana asn 2010-2020.pdf", 2, 329): "Indiana University Purdue University - Fort Wayne",
    ("indiana asn 2010-2020.pdf", 2, 382): "ITT Technical Institute - Fort Wayne",
    ("indiana asn 2010-2020.pdf", 2, 410): "ITT Technical Institute - Indianapolis",
    ("indiana asn 2010-2020.pdf", 2, 438): "ITT Technical Institute - Merrillville",
    ("indiana asn 2010-2020.pdf", 2, 465): "ITT Technical Institute - Newburgh",
    ("indiana asn 2010-2020.pdf", 3, 116): "Marian University",
    ("indiana asn 2010-2020.pdf", 3, 157): "Medtech College - Fort Wayne",
    ("indiana asn 2010-2020.pdf", 3, 212): "Medtech College - Greenwood",
    ("indiana asn 2010-2020.pdf", 3, 267): "Medtech College - Indianapolis",
    ("indiana asn 2013-2023.pdf", 2, 118): "Ivy Tech Community College Terre Haute",
    ("indiana asn 2013-2023.pdf", 2, 288): "Vincennes University - Jasper",
    ("indiana asn 2014-2024.pdf", 0, 516): "Ivy Tech Community College Fort Wayne",
    ("indiana asn 2015-2025.pdf", 3, 154): "University of Saint Francis - Fort Wayne",
    ("indiana asn 2015-2025.pdf", 3, 191): "University of Saint Francis - Crown Point",
    ("indiana asn 2015-2025.pdf", 3, 229): "Vincennes University",
    ("indiana asn 2015-2025.pdf", 3, 283): "Vincennes University - Jasper",
}
# Names printed with no figures beside them (programs without first-time
# takers in the years shown); they are not joined to a neighbouring row.
IND_ALONE = {"BUTLER UNIVERSITY", "GRACE COLLEGE", "TAYLOR UNIVERSITY", "CARIS COLLEGE",
             "EVEREST COLLEGE", "TRINE UNIVERSITY"}
# One spelling for each program across editions (the board's own spellings).
ALIASES = {
    ("IN", "ANCILLA DOMINI COLLEGE"): "Ancilla College",
    ("IN", "BETHEL COLLEGE"): "Bethel University",
    ("IN", "IVY TECH INDIANAPOLIS"): "Ivy Tech Community College Indianapolis",
    ("IN", "COMMUNITY COLLEGE LAWRENCEBURG"): "Ivy Tech Community College Lawrenceburg",
    ("IN", "KOKOMO"): "Indiana University Kokomo",
    ("IN", "SOUTH BEND"): "Indiana University South Bend",
    ("IN", "INDIANA UNIVERSITY COLUMBUS"): "Indiana University Purdue University Columbus",
}


CLOSED_MARK = re.compile(r"\s*(\(closed\)|\(notice of closure\)|-?\s*\bclosed\b(\s+\d{1,2}/\d{4})?)\s*$", re.I)


def canonical(state, name):
    n = CLOSED_MARK.sub("", name).strip(" -")
    n = ALIASES.get((state, n.upper()), n)
    if state == "IN":
        n = re.sub(r"^Ivy Tech Community College - ", "Ivy Tech Community College ", n)
    if state == "OK":   # the older editions abbreviate the state's name
        n = re.sub(r"^University Okla\.", "University of Oklahoma", n)
        n = re.sub(r"\bOkla\.|\bOK\b", "Oklahoma", n)
    return n


def _lines(words, tol=3.5):
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(out[-1][0]["top"] - w["top"]) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    return out


def indiana_file(fname):
    level = "associate" if " asn " in fname else "bachelor"
    rows = []
    cols = left = None
    with pdfplumber.open(os.path.join(RAW, fname)) as pdf:
        for pi, page in enumerate(pdf.pages):
            ws = page.extract_words()
            yrs = [w for w in ws if re.fullmatch(r"20[0-2]\d", w["text"])
                   and w["top"] < 125 and w["x0"] > 150]
            if yrs:
                cols = [(int(w["text"]), (w["x0"] + w["x1"]) / 2) for w in yrs]
                left = min(w["x0"] for w in yrs) - 14
                top0 = max(w["top"] for w in yrs) + 5
            elif cols:   # a page without its own year header keeps the last one
                tt = [w["top"] for w in ws if w["text"] == "Rates" and w["top"] < 100]
                top0 = (tt[0] if tt else 40) + 8
            else:
                continue
            body = [w for w in ws if top0 < w["top"] < page.height - 40]
            vals = [w for w in body if w["x0"] >= left]
            names = [w for w in body if w["x1"] < left + 4 and w["x0"] < left]

            def col(w):
                c = (w["x0"] + w["x1"]) / 2
                return min(cols, key=lambda yc: abs(yc[1] - c))[0]

            counts = []
            for w in vals:
                t = w["text"]
                if "/" not in t:
                    continue
                m = IND_COUNT.search(t)
                if m and re.search(r"\d\)?[_%(]*$", t):
                    a, b = (m[1], m[2]) if m[1] else (m[3], m[4])
                    counts.append(dict(w, yr=col(w), p=int(a), n=int(b)))
                elif t not in ("N/A",):
                    report["indiana unreadable tokens"].append([fname, pi, round(w["top"]), col(w), t])
            rates = [dict(w, yr=col(w), r=float(w["text"].rstrip("%"))) for w in vals
                     if re.fullmatch(r"\d{1,3}(\.\d+)?%|\d{1,3}\.\d+|\d{2,3}", w["text"])]
            # count lines; a line joins the row above when it is close and
            # its years do not overlap (counts printed on two lines)
            groups = []
            for L in _lines(counts):
                ys = {c["yr"] for c in L}
                if groups and L[0]["top"] - groups[-1][-1][0]["top"] < 28 and \
                        not ys & {c["yr"] for g in groups[-1] for c in g}:
                    groups[-1].append(L)
                else:
                    groups.append([L])
            G = []
            for g in groups:
                cs = [c for L in g for c in L]
                G.append(dict(lo=min(c["top"] for c in cs), hi=max(c["top"] for c in cs),
                              cells=cs, names=[]))
            for L in _lines(names):
                text = " ".join(x["text"] for x in sorted(L, key=lambda w: w["x0"]))
                if any(text.startswith(s) for s in IND_SKIP) or not G:
                    continue
                y = L[0]["top"]
                d, i = min((0 if g["lo"] - 14 <= y <= g["hi"] else
                            min(abs(y - (g["lo"] - 14)), abs(y - g["hi"])), i)
                           for i, g in enumerate(G))
                if tidy(text).upper() in IND_ALONE:
                    report["indiana names without figures"].append([fname, pi, round(y), tidy(text)])
                    continue
                G[i]["names"].append(text)
            for g in G:
                key = (fname, pi, round(g["lo"]))
                name = NAME_FIXES[key] if key in NAME_FIXES else tidy(" ".join(g["names"]))
                if not name:
                    report["indiana unnamed rows"].append([fname, pi, round(g["lo"]),
                                                           sorted({c["yr"] for c in g["cells"]})])
                    continue
                for c in g["cells"]:
                    near = [r for r in rates if r["yr"] == c["yr"] and -3 <= c["top"] - r["top"] <= 17]
                    printed = min(near, key=lambda r: abs(c["top"] - r["top"]))["r"] if near else None
                    rows.append(dict(state="IN", name=name, level=level, section=level,
                                     year=c["yr"], passed=c["p"], tested=c["n"],
                                     printed_rate=printed, source=fname, where=f"page {pi + 1}"))
    return rows


def check_counts(row, tol):
    """'clean', 'disagree' (counts and printed rate differ by up to 10 points)
    or 'broken'; a disagreeing or broken row is changed as the docstring says."""
    p, n, r = row["passed"], row["tested"], row["printed_rate"]
    if r is not None and r > 100:
        row["printed_rate"] = r = None
    if n == 0 or p > n:
        status = "broken"
    elif r is None or abs(100 * p / n - r) <= tol:
        return "clean"
    else:
        status = "disagree" if abs(100 * p / n - r) <= 10 else "broken"
    report["counts not matching the printed rate"].append(dict(row, status=status))
    if status == "broken":
        row["passed"] = row["tested"] = None
        row["where"] = (row["where"] + ", " if row["where"] else "") + "broken count, printed rate used"
    else:
        row["passed"] = None
        row["where"] = (row["where"] + ", " if row["where"] else "") + "count and printed rate disagree, printed rate used"
    return status


# ---------------------------------------------------------------- Texas
TX_FILES = ["texas rn five-year 2020.pdf", "texas rn five-year 2021.pdf",
            "texas rn 2013-2017 (shsu copy).pdf"]
TX_SECTIONS = {"ADN": "associate", "BSN": "bachelor", "DIPLOMA": None, "MSN": None, "MEN": None}
TX_EMPTY = r"(?i:No Candidates|New Program)|-----"
TX_RATE_FIRST = re.compile(r"(\d{1,3}\.\d{1,2})%\s+([\d,]+)/([\d,]+)(\s+Closed)?|(" + TX_EMPTY + ")")
TX_COUNT_FIRST = re.compile(r"([\d,]+)/([\d,]+)(\s+Closed)?\s+(\d{1,3}\.\d{1,2})%|(" + TX_EMPTY + ")")


def texas_file(fname):
    rows = []
    yrs = sec = None
    pending = ""
    for ln in pdftext(fname).splitlines():
        m = re.fullmatch(r"(?:First-Time Test Takers.*?)?((?:\s+20\d\d){5})\s*", ln)
        if m:
            yrs, pending = [int(y) for y in m[1].split()], ""
            continue
        s = ln.strip()
        if not yrs or not s or s.startswith("Page ") or "BOARD OF NURSING" in s \
                or "Licensure Examination" in s or "First-Time Test Takers" in s or "NCSBN" in s:
            continue
        h = re.match(r"(DIPLOMA|ADN|BSN|MSN|MEN)\s+PROGRAMS?\b", s)
        if h:
            sec, pending = h[1], ""
            continue
        if "AVERAGE FOR RN" in s or s.startswith("CANDIDATES"):
            continue
        a, b = list(TX_RATE_FIRST.finditer(s)), list(TX_COUNT_FIRST.finditer(s))
        cells, rate_first = (a, True) if sum(1 for c in a if c[1]) >= sum(1 for c in b if c[1]) else (b, False)
        if not any(c[1] for c in cells):
            if re.fullmatch(r"\d{1,3}\.\d{2}%", s):
                report["texas lone rate lines"].append([fname, s])
            elif len(cells) == 5:
                pass                      # a program with no candidates in any year
            else:
                pending = (pending + " " + s).strip()
            continue
        name = tidy(pending + " " + s[:cells[0].start()])
        pending = ""
        if len(cells) != 5:
            report["texas rows not read in full"].append([fname, name, s])
            continue
        for y, c in zip(yrs, cells):
            if c[5]:
                continue
            if rate_first:
                r, p, n, closed = float(c[1]), int(c[2].replace(",", "")), int(c[3].replace(",", "")), bool(c[4])
            else:
                p, n, closed, r = int(c[1].replace(",", "")), int(c[2].replace(",", "")), bool(c[3]), float(c[4])
            rows.append(dict(state="TX", name=name, level=TX_SECTIONS.get(sec), section=sec,
                             year=y, passed=p, tested=n, printed_rate=r, source=fname,
                             where="closed" if closed else ""))
    return rows


# ---------------------------------------------------------------- Oklahoma
OK_FILES = ["oklahoma rn 2015-2025.pdf", "oklahoma rn 2014-2024 (swosu copy).pdf",
            "oklahoma rn 2012-2022 (swosu copy).pdf"]
OK_VAL = r"(N/A|\d{1,3}(?:\.\d+)?\*?)"


def oklahoma_file(fname):
    rows = []
    yrs = None
    pending = ""
    for ln in pdftext(fname).splitlines():
        s = ln.strip()
        if s.startswith("NURSING PROGRAM"):
            yrs, pending = [int(y) for y in re.findall(r"\b20\d\d\b", s)][:11], ""
            continue
        if s.startswith(("OTHER CATEGORY", "OKLAHOMA AND NATIONAL")):
            yrs = None
            continue
        if not yrs or not s or s.startswith("Page ") or "Board of Nursing" in s or "BOARD OF NURSING" in s \
                or "Pass Rate" in s or "PASS RATE" in s:
            continue
        m = re.match(r"(.*?)\s+((?:" + OK_VAL + r"\s+){11})([\d,.]+|N/A)\s*$", s)
        if not m:
            pending = (pending + " " + s).strip()
            continue
        name = tidy(pending + " " + m[1])
        pending = ""
        if name.upper().startswith(("RE - ENTRY", "RE-ENTRY", "CLOSED PROGRAM")):
            continue
        vals = [v.rstrip("*") for v in m[2].split()]
        lvl = re.search(r"\b(ADN|BSN)\b", name)
        for y, v in zip(yrs, vals):
            if v == "N/A":
                continue
            rows.append(dict(state="OK", name=name,
                             level={"ADN": "associate", "BSN": "bachelor"}[lvl[1]] if lvl else None,
                             section="RN", year=y, passed=None, tested=None, printed_rate=float(v),
                             source=fname, where="closed" if "CLOSED" in name.upper() else ""))
    return rows


# ---------------------------------------------------------------- Florida
FL_FILES = [("florida_rn_2016_4q.pdf", 2016), ("florida_rn_2017_4q.pdf", 2017),
            ("florida_rn_2018_report_4.pdf", 2018), ("florida_rn_2019_4q.pdf", 2019),
            ("florida rn 4q 2020.pdf", 2020)]
FL_HEAD = re.compile(r"^\s*FL - (.+?)\s*\((US\d{8})\)\s*$")
FL_GROUP = re.compile(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d{1,3}\.\d{2})%")
FL_LEVEL = {"ADN": "associate", "ASN": "associate", "AS": "associate",
            "BS": "bachelor", "BSN": "bachelor"}


def florida_file(fname, year):
    text = pdftext(fname)
    ytd = "Year to Date" in text
    totals, cur = {}, None
    for ln in text.splitlines():
        m = FL_HEAD.match(ln)
        if m:
            cur = (m[1], m[2])
            continue
        if cur and re.search(r"(^|\s)Total:?\s+\d", ln):
            g = [tuple(int(float(v)) for v in x[:3]) for x in FL_GROUP.findall(ln)]
            if len(g) < (1 if ytd else 2):
                report["florida unreadable totals"].append([fname, cur[0], ln.strip()])
                continue
            quarters, total = (g[-1:], g[-1]) if ytd else (g[:-1], g[-1])
            d, p = sum(q[0] for q in quarters), sum(q[1] for q in quarters)
            if (d, p) != total[:2]:
                report["florida quarters not matching the total column"].append([fname, cur[0], d, p, total])
            totals[cur] = (d, p)
            cur = None
    rows = []
    for (name, code), (d, p) in totals.items():
        tag = re.search(r" - (ADN|ASN|AS|BSN|BS|DIPLOMA|MSN|PN)\s*$", name)
        # campuses share a name, so the NCSBN program code is part of it
        rows.append(dict(state="FL", name=f"{tidy(name)} ({code})", level=FL_LEVEL.get(tag[1]) if tag else None,
                         section=tag[1] if tag else "", year=year, passed=p, tested=d,
                         printed_rate=None, source=fname, where=code))
    return rows


# ---------------------------------------------------------------- combine
def combine(rows):
    """One value per state, program, level and year: the value the most
    editions give; disagreements are listed."""
    by = collections.defaultdict(list)
    for r in rows:
        if CLOSED_MARK.search(r["name"]):
            r["where"] = (r["where"] + ", " if r["where"] else "") + "marked closed"
        r["name"] = canonical(r["state"], r["name"])
        by[(r["state"], r["name"].upper(), r["level"], r["section"], r["year"])].append(r)
    out = []
    for key, rs in sorted(by.items(), key=lambda kv: [str(x) for x in kv[0]]):
        clean = [r for r in rs if r["passed"] is not None]
        if clean and len(clean) < len(rs):   # a clean count in one edition settles a broken one in another
            rs = clean
        def vk(r):
            return (r["passed"], r["tested"]) if r["passed"] is not None else (None, r["tested"], r["printed_rate"])
        votes = collections.Counter(vk(r) for r in rs)
        top, k = votes.most_common(1)[0]
        tie = len(votes) > 1 and list(votes.values()).count(k) > 1
        if len(votes) > 1:
            report["editions disagreeing"].append(dict(
                program=rs[0]["name"], state=key[0], level=key[2], year=key[4], tie=tie,
                values={" ".join(map(str, v)): [r["source"] for r in rs if vk(r) == v] for v in votes}))
        if tie:            # a tie between editions: the newest edition listed first is used
            top = vk(min(rs, key=lambda r: ORDER.index(r["source"])))
        best = [r for r in rs if vk(r) == top]
        p, n = best[0]["passed"], best[0]["tested"]
        prs = [r["printed_rate"] for r in best if r["printed_rate"] is not None]
        pr = prs[0] if prs else None
        rate = round(100 * p / n, 2) if (n and p is not None) else pr
        out.append(dict(state=key[0], program=rs[0]["name"], level=key[2] or "",
                        board_section=key[3], exam_year=key[4],
                        passed="" if p is None else p, tested="" if n is None else n,
                        pass_rate=rate, printed_rate="" if pr is None else pr,
                        editions=len(rs), editions_agreeing=len(best),
                        sources="; ".join(sorted({r["source"] for r in best})),
                        note="; ".join(sorted({r["where"] for r in best if r["where"]}))))
    return out


ORDER = IND_FILES + TX_FILES + OK_FILES + [f for f, _ in FL_FILES]


def main():
    rows = []
    for f in IND_FILES:
        for r in indiana_file(f):
            check_counts(r, 0.6)
            if r["passed"] is not None or r["printed_rate"] is not None:
                rows.append(r)
    for f in TX_FILES:
        for r in texas_file(f):
            check_counts(r, 0.06)
            rows.append(r)
    for f in OK_FILES:
        rows += oklahoma_file(f)
    for f, y in FL_FILES:
        rows += florida_file(f, y)
    rows = [r for r in rows if r["year"] in YEARS]
    key = "counts not matching the printed rate"
    report[key] = [r for r in report[key] if r["year"] in YEARS]
    table = combine(rows)
    for t in table:                       # Texas's exam year before the calendar year
        if t["state"] == "TX" and t["exam_year"] <= 2015:
            t["note"] = (t["note"] + "; " if t["note"] else "") + "exam year October to September"
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    summary = collections.Counter((t["state"], t["level"] or "no level", t["exam_year"]) for t in table)
    report["summary"] = {f"{s} {l} {y}": c for (s, l, y), c in sorted(summary.items())}
    with open(OUT_REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False, default=str)
    print(f"{len(table)} program-years written to {OUT_CSV}")
    for k, v in report.items():
        if k != "summary":
            print(f"  {k}: {len(v)}")


if __name__ == "__main__":
    main()
