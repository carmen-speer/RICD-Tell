"""
Transfer test, step 1: list what the Texas Higher Education Coordinating
Board's sites serve for the transfer test (see "transfer test protocol.md"),
so the download and parsing code can be written for the real formats.

It reads index pages only. It records each page's address, status, type and
size, and every link on it (address and text), following links one level
down within the same section of a site. It never opens a report file (PDF,
spreadsheet): those are listed by address, with their size from a HEAD
request where the server gives one. No outcome is read.

Output: data/transfer test/sources.json

Usage (GitHub Actions; the chat sandbox cannot reach these sites):
    cd src
    python "transfer sources.py"
"""

from __future__ import annotations

import datetime
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "transfer test" / "sources.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

# Starting pages, and the path prefix within which links are followed one level down.
STARTS = [
    # Per-pair reports: "Academic Performance of 2-Year College Transfer Students at Texas Public Universities"
    ("http://www.txhighereddata.org/reports/performance/ctctransfer/", "/reports/performance/ctctransfer"),
    ("https://www.txhighereddata.org/reports/performance/ctctransfer/", "/reports/performance/ctctransfer"),
    ("http://www.txhighereddata.org/reports/performance/", "/reports/performance"),
    # Accountability system: two-year colleges' graduation rates ("Bachelor's or Above"); universities' C15U
    ("http://www.txhigheredaccountability.org/AcctPublic/", "/AcctPublic"),
    ("http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=1", "/AcctPublic"),
    ("http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=2", "/AcctPublic"),
    ("http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=3", "/AcctPublic"),
    ("http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=4", "/AcctPublic"),
    ("http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=5", "/AcctPublic"),
    # Annual Transfer Reports (universities' junior-cohort completion rates)
    ("https://reportcenter.highered.texas.gov/tag/transfer-report/", "/reports"),
    ("https://reportcenter.highered.texas.gov/?s=transfer+report", "/reports"),
    ("https://reportcenter.highered.texas.gov/?s=academic+performance+transfer", "/reports"),
]
FILE_RE = re.compile(r"\.(pdf|xlsx?|csv|zip|docx?)(\?|$)", re.I)
MAX_FOLLOW = 150          # pages followed one level down, per start
PAUSE = 0.5               # seconds between requests


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self._href, self._text = [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self._href, self._text = a["href"], []
        elif tag in ("form",) and a.get("action"):
            self.links.append({"href": a["action"], "text": "[form action]"})
        elif tag == "option" and a.get("value"):
            self.links.append({"href": a["value"], "text": "[option]"})

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append({"href": self._href, "text": " ".join("".join(self._text).split())})
            self._href = None


def get(url: str) -> dict:
    rec = {"url": url}
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
        rec.update({"status": r.status_code, "final url": r.url,
                    "content type": r.headers.get("Content-Type", ""), "bytes": len(r.content)})
        if "html" in rec["content type"].lower():
            p = Links()
            p.feed(r.text)
            rec["title"] = (re.search(r"<title>(.*?)</title>", r.text, re.I | re.S) or [None, ""])[1].strip()[:200]
            rec["links"] = [{"href": urljoin(r.url, x["href"]), "text": x["text"][:200]} for x in p.links]
            rec["forms and selects (raw)"] = re.findall(r"<(?:form|select)[^>]*>", r.text, re.I)[:40]
    except requests.RequestException as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    time.sleep(PAUSE)
    return rec


def head(url: str) -> dict:
    try:
        r = requests.head(url, headers=HEADERS, timeout=60, allow_redirects=True)
        return {"url": url, "status": r.status_code, "final url": r.url,
                "content type": r.headers.get("Content-Type", ""),
                "bytes": r.headers.get("Content-Length")}
    except requests.RequestException as e:
        return {"url": url, "error": f"{type(e).__name__}: {e}"}
    finally:
        time.sleep(PAUSE)


def main() -> None:
    out = {"protocol": "transfer test protocol.md, step 1 (listing only; no report file is opened)",
           "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "starts": []}
    for start, prefix in STARTS:
        print(f"Listing {start}", flush=True)
        page = get(start)
        entry = {"start": start, "page": page, "followed": [], "files": []}
        host = urlparse(page.get("final url", start)).netloc
        seen, n = {start, page.get("final url")}, 0
        for link in page.get("links", []):
            u = link["href"].split("#")[0]
            pu = urlparse(u)
            if not u or u in seen or pu.scheme not in ("http", "https"):
                continue
            seen.add(u)
            if FILE_RE.search(pu.path):
                entry["files"].append({**head(u), "text": link["text"]})
            elif pu.netloc == host and pu.path.lower().startswith(prefix.lower()) and n < MAX_FOLLOW:
                sub = get(u)
                n += 1
                files = [x for x in sub.get("links", []) if FILE_RE.search(urlparse(x["href"]).path)]
                entry["followed"].append({k: v for k, v in sub.items() if k != "links"}
                                         | {"link text": link["text"],
                                            "file links (not opened)": files,
                                            "other links": [x for x in sub.get("links", []) if x not in files][:300]})
        out["starts"].append(entry)
        print(f"  status {page.get('status', page.get('error'))}; {len(entry['followed'])} pages followed; "
              f"{len(entry['files'])} file links", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
