"""
Transfer test, step 1b (see "transfer test protocol.md"): records the
formats of the Texas Higher Education Coordinating Board's transfer reports,
so the download and parsing code can be written for them.

The per-pair reports ("Transfer Students Success" on apps.highered.texas.gov)
are produced by four forms, each taking a college (FICE code) and a report
year. This script saves the page itself (every college and year offered, by
form), submits each form once, for one college and one year, and saves what
comes back (type, size and the response itself), and saves the accountability
system's report and measure menus. That one sample per form is the only
report content read; it is needed to write the parser, and the analysis was
fixed in the protocol before it was read.

Output: data/transfer test/formats/ (one file per page or sample) and
data/transfer test/formats.json (the index).

Usage (GitHub Actions):
    cd src
    python "transfer formats.py"
"""

from __future__ import annotations

import datetime
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "transfer test" / "formats"
INDEX = ROOT / "data" / "transfer test" / "formats.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
PAGE = "https://apps.highered.texas.gov/index.cfm?page=F5C67269E9A51FF66C697725A30167EAAD92F671EEA28FA27DEB32DFB4609513"
ACCT = ["http://www.txhigheredaccountability.org/AcctPublic/InteractiveReport/ManageReports",
        "http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=1",
        "http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=2",
        "http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=3",
        "http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=4",
        "http://www.txhigheredaccountability.org/AcctPublic/Measures/ManageMeasures?instTypeID=5"]


class Forms(HTMLParser):
    """Each form's action, method, hidden inputs and select options (value and text)."""
    def __init__(self):
        super().__init__()
        self.forms, self._form, self._select, self._opt = [], None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._form = {"name": a.get("name") or a.get("id"), "action": a.get("action"),
                          "method": (a.get("method") or "get").lower(), "inputs": {}, "selects": {}}
            self.forms.append(self._form)
        elif self._form is not None and tag == "input" and a.get("name"):
            self._form["inputs"][a["name"]] = {"type": a.get("type"), "value": a.get("value")}
        elif self._form is not None and tag == "select":
            self._select = a.get("name")
            self._form["selects"][self._select] = []
        elif self._form is not None and tag == "option" and self._select:
            self._opt = {"value": a.get("value"), "text": ""}
            self._form["selects"][self._select].append(self._opt)

    def handle_data(self, data):
        if self._opt is not None:
            self._opt["text"] += data

    def handle_endtag(self, tag):
        if tag == "option" and self._opt is not None:
            self._opt["text"] = " ".join(self._opt["text"].split())
            self._opt = None
        elif tag == "select":
            self._select = None
        elif tag == "form":
            self._form = None


def save(name: str, r: requests.Response) -> dict:
    ct = r.headers.get("Content-Type", "")
    ext = ".pdf" if "pdf" in ct else ".xlsx" if "sheet" in ct else ".xls" if "excel" in ct else \
        ".csv" if "csv" in ct else ".html"
    path = OUT / (name + ext)
    path.write_bytes(r.content)
    return {"file": str(path.relative_to(ROOT)), "status": r.status_code, "final url": r.url,
            "content type": ct, "bytes": len(r.content),
            "content disposition": r.headers.get("Content-Disposition")}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(HEADERS)
    index = {"protocol": "transfer test protocol.md, step 1b (formats; one sample report per form)",
             "written at (UTC)": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    r = s.get(PAGE, timeout=60)
    index["transfer page"] = save("transfer page", r)
    p = Forms()
    p.feed(r.text)
    forms = [f for f in p.forms if f["selects"]]
    index["forms"] = forms
    samples = []
    for f in forms:
        data = {k: v.get("value") or "" for k, v in f["inputs"].items()}
        choice = {}
        for name, opts in f["selects"].items():
            real = [o for o in opts if o["value"] and not re.match(r"^\s*(select|choose|--)", o["text"], re.I)]
            if not real:
                continue
            # the institution: the first real option; the year: the second most recent offered
            pick = real[1] if "yr" in name.lower() and len(real) > 1 else real[0]
            data[name] = pick["value"]
            choice[name] = pick
        url = requests.compat.urljoin(PAGE, f["action"] or PAGE)
        try:
            resp = s.post(url, data=data, timeout=120) if f["method"] == "post" else s.get(url, params=data, timeout=120)
            samples.append({"form": f["name"], "submitted": data, "choices": choice,
                            **save(f"sample {f['name']}", resp)})
        except requests.RequestException as e:
            samples.append({"form": f["name"], "submitted": data, "error": f"{type(e).__name__}: {e}"})
        time.sleep(1)
    index["samples"] = samples
    acct = []
    for i, u in enumerate(ACCT):
        try:
            acct.append(save(f"accountability {i}", s.get(u, timeout=60)))
        except requests.RequestException as e:
            acct.append({"url": u, "error": f"{type(e).__name__}: {e}"})
        time.sleep(0.5)
    index["accountability pages"] = acct
    INDEX.write_text(json.dumps(index, indent=1))
    print(json.dumps({k: v for k, v in index.items() if k != "forms"}, indent=1)[:4000])


if __name__ == "__main__":
    main()
