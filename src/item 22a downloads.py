"""
Item 22a, step one: download the licensure pass-rate files named in
"protocols/nursing and pharmacy protocol.md" (section 7) and record each
file's URL, size and sha256. Nothing is parsed and no pass rate is read here;
the parsers are written after the files have been seen.

Every attempt is recorded, including files that fail or are refused, so a
file that must be downloaded by hand is listed with its URL. Hand-downloaded
files go in data/item 22a/raw/ under the same name and are recorded the same
way by rerunning this script (an existing file is hashed, not re-fetched).

Run from the repository root:  python "src/item 22a downloads.py"
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

RAW = os.path.join("data", "item 22a", "raw")
MANIFEST = os.path.join(RAW, "downloads.json")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")

OK = "https://www.oklahoma.gov/content/dam/ok/en/nursing/documents/"
IN = "https://secure.in.gov/pla/files/"
IN_OLD = "https://www.in.gov/pla/files/"
TX5 = "https://www.bon.texas.gov/pdfs/education_pdfs/education_programs/RN%205YR-{:02d}.pdf"

# (source, file name to save, URL). Older editions are fetched too, because
# the newest Oklahoma table gives candidate counts for its latest year only.
SOURCES = [
    ("Oklahoma", "oklahoma rn 2015-2025.pdf", OK + "nclexpass1.pdf"),
    ("Oklahoma", "oklahoma nclexpass (board copy).pdf", OK + "nclexpass.pdf"),
    ("Oklahoma", "oklahoma rn 2014-2024 (swosu copy).pdf", "https://swosu.edu/nursing/files/2024nclexpass1.pdf"),
    ("Oklahoma", "oklahoma rn 2012-2022 (swosu copy).pdf", "https://www.swosu.edu/nursing/files/2023.nclexpass1.pdf"),
    ("Oklahoma", "oklahoma nclexpass (swosu copy).pdf", "https://www.swosu.edu/nursing/files/nclexpass.pdf"),
    ("Indiana", "indiana bsn 2015-2025.pdf", IN + "BSN-2015-2025.pdf"),
    ("Indiana", "indiana asn 2015-2025.pdf", IN + "ASN-2015-2025.pdf"),
    ("Indiana", "indiana bsn 2014-2024.pdf", IN_OLD + "BSN-2014-2024.pdf"),
    ("Indiana", "indiana asn 2014-2024.pdf", IN_OLD + "ASN-2014-2024.pdf"),
    ("Indiana", "indiana bsn 2013-2023.pdf", IN_OLD + "BSN-2013-2023.pdf"),
    ("Indiana", "indiana asn 2013-2023.pdf", IN + "ASN-2013-2023.pdf"),
    ("Indiana", "indiana asn 2010-2020.pdf", IN_OLD + "ASN-pass-rates-2010-2020.pdf"),
    ("Texas", "texas rn 2024 (board report).pdf", "https://www.bon.texas.gov/pdfs/board_meetings_pdfs/2025/Apr/3-2-12.pdf"),
    ("Texas", "texas rn 2015 (board report).pdf", "https://www.bon.texas.gov/pdfs/board_meetings_pdfs/2016/January/3-2-5.pdf"),
    ("Texas", "texas rn 2013-2017 (shsu copy).pdf", "https://sacscoc.shsu.edu/Support%20Docs/8.1/9%20-%20Texas%20Board%20of%20Nursing%20NCLEX%20Pass%20Rates.pdf"),
] + [("Texas", f"texas rn five-year 20{yy:02d}.pdf", TX5.format(yy)) for yy in range(16, 26)] + [
    ("Florida", "florida rn 4q 2020.pdf", "https://floridasnursing.gov/forms/rn-pass-rate-4q-2020.pdf"),
    ("NABP", "naplex 2014-2024 ten-year.pdf", "https://nabp.pharmacy/wp-content/uploads/2025/10/Ten-Year-NAPLEX-and-MPJE-Pass-Rates.pdf"),
    ("NABP", "naplex 2023-2025 (nabp).pdf", "https://nabp.pharmacy/wp-content/uploads/NAPLEX-Pass-Rates.pdf"),
    ("NABP", "naplex 2023-2025 (duquesne copy).pdf", "https://www.duq.edu/documents/academics/colleges-and-schools/pharmacy/naplex-2023-2025-pass-rates.pdf"),
    ("NABP", "naplex 2022-2024 (duquesne copy).pdf", "https://www.duq.edu/documents/academics/colleges-and-schools/pharmacy/naplex-pass-rates-acc.pdf"),
    ("NABP", "naplex 2021-2023 (siue copy).pdf", "https://siue.edu/pharmacy/about/pdf/NAPLEX-Pass-Rates-2023.pdf"),
    ("NABP", "naplex 2020-2022 (siue copy).pdf", "https://www.siue.edu/pharmacy/about/pdf/NAPLEXPassRates2022.pdf"),
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return e.code, "", b""
            last = f"HTTP {e.code}"
        except Exception as e:  # network errors, timeouts
            last = f"{type(e).__name__}: {e}"
        time.sleep(5 * (attempt + 1))
    return None, last, b""


def main():
    os.makedirs(RAW, exist_ok=True)
    records = []
    for source, name, url in SOURCES:
        path = os.path.join(RAW, name)
        rec = {"source": source, "file": name, "url": url}
        if os.path.exists(path):
            data = open(path, "rb").read()
            rec.update(status="already present (hashed, not re-fetched)", bytes=len(data), sha256=sha256(data))
        else:
            status, ctype, data = fetch(url)
            if status == 200 and data[:5] == b"%PDF-":
                open(path, "wb").write(data)
                rec.update(status="downloaded", bytes=len(data), sha256=sha256(data))
            elif status == 200:
                rec.update(status=f"refused: not a PDF (content type {ctype!r}); download by hand")
            elif status in (404, 410):
                rec.update(status=f"not found (HTTP {status})")
            else:
                rec.update(status=f"failed ({ctype}); download by hand")
        print(f"{rec['status'][:40]:40}  {name}")
        records.append(rec)
    out = {
        "note": "Item 22a, step one: pass-rate files downloaded or attempted, under protocols/nursing and pharmacy protocol.md, section 7. Nothing parsed; no pass rate read.",
        "written at (UTC)": datetime.now(timezone.utc).isoformat(),
        "files": records,
    }
    json.dump(out, open(MANIFEST, "w"), indent=1)
    got = sum(1 for r in records if r.get("sha256"))
    print(f"{got} of {len(records)} files present; manifest written to {MANIFEST}")


if __name__ == "__main__":
    main()
