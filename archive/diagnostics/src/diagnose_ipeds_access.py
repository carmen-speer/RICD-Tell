"""
One-time diagnostic, not part of the real pipeline. Purpose: get real,
current ground truth on how nces.ed.gov's Data Center actually serves
file downloads right now, since the previously-working data-generator
URL pattern started returning 404 for every year (confirmed directly
in this project's own GitHub Actions run on 2026-09-15) and this
project's sandboxed development environments cannot reach nces.ed.gov
at all to investigate directly -- only GitHub Actions' own runners can.

This script does not guess a new URL pattern. It requests the real
Data Center entry page with a persistent session (so cookies carry
across any redirects, unlike a one-off request), and prints back
enough of what it actually got -- final URL, status, and any real
download-looking links found in the page -- to build the next real fix
from actual evidence, rather than a fourth guess.
"""

import re
import requests

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (RICD-tracker-diagnostic)"})

urls_to_try = [
    "https://nces.ed.gov/ipeds/datacenter/login.aspx?gotoReportId=7",
    "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year=2023",
    "https://nces.ed.gov/ipeds/use-the-data/download-access-database",
]

for url in urls_to_try:
    print(f"\n{'='*70}\nREQUEST: {url}\n{'='*70}")
    try:
        resp = session.get(url, timeout=30, allow_redirects=True)
        print(f"Final URL after redirects: {resp.url}")
        print(f"Status code: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('Content-Type')}")
        html = resp.text
        print(f"Response length: {len(html)} characters")

        # Look for anything that looks like a real download link
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        interesting = [h for h in hrefs if any(
            kw in h.lower() for kw in ["data-generator", ".zip", ".csv", "/data/", "download"]
        )]
        print(f"\nTotal links found: {len(hrefs)}")
        print(f"Download-looking links found: {len(interesting)}")
        for h in interesting[:25]:
            print(f"  {h}")

        # Look for select/option elements that might show survey/year pickers
        selects = re.findall(r'<select[^>]*name=["\']([^"\']+)["\']', html, re.IGNORECASE)
        print(f"\nForm <select> field names found: {selects[:15]}")

        # Look for any mention of F1A / F2 / finance survey codes
        finance_mentions = re.findall(r'.{30}(?:F1A|F2A|F3[^0-9]|finance).{30}', html, re.IGNORECASE)
        print(f"\nFinance-related text snippets found: {len(finance_mentions)}")
        for m in finance_mentions[:10]:
            print(f"  ...{m}...")

    except Exception as e:
        print(f"REQUEST FAILED: {type(e).__name__}: {e}")

print("\n\nDONE. Copy this entire output and send it back for the real fix.")
