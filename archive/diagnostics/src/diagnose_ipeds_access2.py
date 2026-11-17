"""
Second-round diagnostic. Round 1 confirmed the real, current mechanism
for the NEWEST year or two of IPEDS finance data (a plain static ZIP at
/ipeds/complete-data-files/<table_name>.zip -- no session needed). That
fix downloaded 2 of 11 years successfully; the other 9 (older years,
FY2013-FY2021) all 404 at that same address. This means older years
are not retired -- IPEDS keeps its full historical archive available --
but they're evidently served from a different real location than the
newest year or two. This script finds that real location directly,
rather than guessing it, using two approaches in parallel:

1. Re-request the Data Center page for an old year (2018) using the
   SAME session that first visited the login/entry page, in case the
   entry page's session cookie is what's needed to see the real link
   for older years (unlike the newest year, which may be served from a
   public, cacheable, session-free path).
2. Directly test a handful of plausible archive URL variations for the
   same known old table name, to see whether the file simply lives at
   a slightly different real address for older years.
"""

import re
import requests

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (RICD-tracker-diagnostic)"})

print("STEP 1: establish session via the real entry page")
r1 = session.get("https://nces.ed.gov/ipeds/datacenter/login.aspx?gotoReportId=7", timeout=30)
print(f"  entry page status: {r1.status_code}, final url: {r1.url}")

print("\nSTEP 2: request the Data Center page for an OLD year (2018), same session")
r2 = session.get("https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year=2018", timeout=30)
print(f"  status: {r2.status_code}, final url: {r2.url}, length: {len(r2.text)}")
hrefs = re.findall(r'href=["\']([^"\']+)["\']', r2.text, re.IGNORECASE)
old_year_links = [h for h in hrefs if "f1a" in h.lower() or "f1819" in h.lower() or "finance" in h.lower()]
print(f"  finance-looking links found for 2018: {len(old_year_links)}")
for h in old_year_links[:20]:
    print(f"    {h}")
# also print any complete-data-files links regardless of name, to see the real pattern
cdf_links = [h for h in hrefs if "complete-data-files" in h.lower()]
print(f"\n  ALL complete-data-files links found on the 2018 page: {len(cdf_links)}")
for h in cdf_links[:20]:
    print(f"    {h}")
archive_links = [h for h in hrefs if "archive" in h.lower() or "prior" in h.lower()]
print(f"\n  Any 'archive'/'prior' looking links: {len(archive_links)}")
for h in archive_links[:20]:
    print(f"    {h}")

print("\nSTEP 3: direct probes of plausible real URLs for the known old table F1819_F1A")
candidates = [
    "https://nces.ed.gov/ipeds/complete-data-files/F1819_F1A.zip",
    "https://nces.ed.gov/ipeds/complete-data-files/archive/F1819_F1A.zip",
    "https://nces.ed.gov/ipeds/complete-data-files/2018/F1819_F1A.zip",
    "https://nces.ed.gov/ipeds/datacenter/data/F1819_F1A.zip",
    "https://nces.ed.gov/ipeds/tablefiles/zipfiles/IPEDS_2018-19_Final.zip",
]
for url in candidates:
    try:
        resp = session.head(url, timeout=20, allow_redirects=True)
        print(f"  HEAD {url} -> {resp.status_code} (final: {resp.url})")
    except Exception as e:
        print(f"  HEAD {url} -> FAILED: {e}")

print("\nDONE. Copy this entire output and send it back.")
