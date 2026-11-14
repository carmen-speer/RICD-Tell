"""
Diagnostic for the confirmatory test's outcome coding, run after the
outcomes were committed. It changes no score, flag, outcome or result.

It records, for every institution in "data/confirmatory/outcomes.csv"
(scored and skipped), the raw IPEDS header (HD) values that bear on
closure or merger in HD2019 through HD2025: every column whose name
suggests a closure, deletion, merger, new-ID or activity status, plus
which columns each file has. It answers three questions the committed
analysis raised:

1. The protocol names MERGEID, which no post-2019 HD file contains.
   Which merger variable do the files actually carry (for example
   NEWID), and which sample institutions does it mark?
2. Why is Pennsylvania State University-Main Campus (214777) coded
   DEATHYR=2020 in HD2020 while appearing in every later file?
3. For institutions that vanish from later files without a closure,
   deletion or merger code, what do their last rows say?

Output: "data/confirmatory/outcome coding diagnostic.json".
"""

import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_confirmatory as ac  # noqa: E402

OUT = ac.CONF / "outcome coding diagnostic.json"
KEEP = re.compile(r"(CLOSE|DEATH|MERGE|NEWID|^ACT$|CYACTIVE|PSEFLAG|PSET4FLG|POSTSEC|OPEFLAG|PRCH|IDX_|STATUS)")


def main() -> None:
    rows = list(csv.DictReader(open(ac.OUTCOMES_PATH, encoding="utf-8")))
    ids = {r["unitid"] for r in rows}
    files, data = {}, {}
    for year in range(2019, 2026):
        got = ac.download_hd(year)
        if got is None:
            files[f"HD{year}"] = "not found"
            continue
        reader = csv.DictReader(io.StringIO(got["csv"].decode("latin-1")))
        reader.fieldnames = [f.strip().lstrip("\ufeff").lstrip("ï»¿").upper() for f in reader.fieldnames]
        cols = [c for c in reader.fieldnames if KEEP.search(c)]
        files[f"HD{year}"] = {"file": got["file"], "zip sha256": got["zip sha256"],
                              "all columns": reader.fieldnames, "columns kept": cols}
        for row in reader:
            u = row["UNITID"].strip()
            if u in ids:
                data.setdefault(u, {})[f"HD{year}"] = {c: (row.get(c) or "").strip() for c in cols}
        print(f"HD{year}: columns kept {cols}")

    def positive(v):
        try:
            return float(v) > 0
        except ValueError:
            return False

    newid_marked = []
    for r in rows:
        for y, vals in data.get(r["unitid"], {}).items():
            if y != "HD2019" and positive(vals.get("NEWID", "")):
                newid_marked.append({"unitid": r["unitid"], "name": r["name"], "group": r["group"],
                                     "tracker flag": r["tracker flag"],
                                     "closed or merged as committed": r["closed or merged"],
                                     "file": y, "NEWID": vals["NEWID"]})
                break
    vanished = [{"unitid": r["unitid"], "name": r["name"], "group": r["group"],
                 "tracker flag": r["tracker flag"], "rows": data.get(r["unitid"], {})}
                for r in rows if r["vanished without a closure, deletion or merger record"] == "True"]
    out = {
        "note": "Diagnostic only, run after outcomes were committed; changes no committed result.",
        "header files": files,
        "Penn State main campus (214777)": data.get("214777", {}),
        "sample institutions with a positive NEWID after 2019": newid_marked,
        "vanished institutions and their rows": vanished,
        "all sample rows": data,
    }
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out["Penn State main campus (214777)"], indent=1))
    print(f"\nNEWID-marked sample institutions: {len(newid_marked)}")
    for m in newid_marked:
        print(f"  {m['unitid']} {m['name'][:45]:45s} {m['group']:24s} flag={m['tracker flag'] or '-':9s} "
              f"{m['file']} NEWID={m['NEWID']} committed={m['closed or merged as committed']}")
    print(f"Vanished institutions: {len(vanished)}")


if __name__ == "__main__":
    main()
