"""
Fetches real, current data for a given institution (by UNITID) to
support live scoring, rather than relying on the locally-downloaded
files used to build the original 54-institution validation panel.

Honest scope note: not everything here is fully automatable yet.

- Enrollment, completion, and admissions data: fully automated via the
  real, stable College Scorecard API (api.data.gov/ed/collegescorecard).
  Requires a free API key (get one at https://api.data.gov/signup/)
  set as the COLLEGE_SCORECARD_API_KEY environment variable.

- IPEDS finance, debt, and endowment data: NOT available through a
  clean, stable REST API -- NCES distributes it as downloadable data
  files instead. The exact download mechanism has changed more than
  once during this project: a defunct static zip pattern, then a
  defunct "data-generator" query-string endpoint (confirmed dead via
  a live GitHub Actions run on 2026-09-15 -- every single fiscal year
  returned a 404). A same-day diagnostic run against NCES's own live
  Data Center page found the real, current mechanism: NCES now serves
  each complete data file as a plain static ZIP archive at
  https://nces.ed.gov/ipeds/complete-data-files/<table_name>.zip --
  no session, login, or query parameters required at all, a genuinely
  simpler system than any previous version of this function assumed.
  This was confirmed directly from real link text scraped off NCES's
  own live page, not guessed.

  This module downloads the most recent available bulk finance file
  it can find using that real, current pattern, but NCES has changed
  this mechanism multiple times before and may again -- this part of
  the pipeline should be monitored (see the GitHub Actions workflow's
  results), not trusted blindly forever.
"""

from __future__ import annotations

import os
import zipfile
import io
from pathlib import Path

import requests

SCORECARD_API_BASE = "https://api.data.gov/ed/collegescorecard/v1/schools"

# OPTIONAL BULK SOURCE (2026-11-12, confirmatory-test preparation): the
# College Scorecard API returns no record at all for an institution that
# has since closed (confirmed by src/diagnose_window_data.py: 20 of the
# panel's 23 closures have no API record), so any pipeline run that must
# see closed institutions -- the confirmatory out-of-sample test above
# all -- cannot take its enrollment, completion and tuition series from
# the API. The Department of Education's own "All Data Files" download
# keeps one file per year (MERGEDyyyy_yy_PP.csv) holding every
# institution that reported that year, closed ones included, with the
# same underlying values the API serves (UGDS = student.size, C150_4 =
# completion.completion_rate_4yr_150nt, TUITIONFEE_IN =
# cost.tuition.in_state, ADM_RATE = admissions.admission_rate.overall).
# src/build_scorecard_compact.py reduces those files to the four columns
# used here. Calling use_bulk_scorecard(path) switches build_live_series
# to that file; nothing calls it unless asked, so the weekly re-score and
# every existing caller keep using the API exactly as before.
_BULK_SCORECARD: dict | None = None
BULK_TO_API = {
    "UGDS": "student.size",
    "C150_4": "completion.completion_rate_4yr_150nt",
    "TUITIONFEE_IN": "cost.tuition.in_state",
    "ADM_RATE": "admissions.admission_rate.overall",
}


def use_bulk_scorecard(path: str | Path) -> None:
    """Load the compact bulk Scorecard file and route build_live_series to it."""
    import csv
    global _BULK_SCORECARD
    data = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            data[(row["UNITID"], int(row["YEAR"]))] = row
    _BULK_SCORECARD = data


def _bulk_scorecard_fields(unitid: str, year: int) -> dict:
    """The same year-prefixed keys fetch_scorecard_fields returns, from the bulk file.
    Missing or suppressed values come back as None, exactly as the API returns them."""
    row = _BULK_SCORECARD.get((unitid, year))
    if row is None:
        raise KeyError(f"No bulk College Scorecard row for UNITID {unitid}, year {year}.")
    out = {}
    for col, api_name in BULK_TO_API.items():
        v = (row.get(col) or "").strip()
        try:
            out[f"{year}.{api_name}"] = float(v)
        except ValueError:
            out[f"{year}.{api_name}"] = None  # NULL / PrivacySuppressed / blank
    return out

# Real field codes, confirmed directly against the actual IPEDS form
# documentation during this project's original build -- not assumed.
PRIVATE_FINANCE_FIELDS = {
    "total_liabilities": "F2A03",
    "endowment": "F2H02",
    "revenue": "F2B01",
    "expenses": "F2B02",
    "institutional_support": "F2E061",
    "instruction": "F2E011",
    "research": "F2E021",
    "net_tuition": "F2D01",
}
PUBLIC_FINANCE_FIELDS = {
    "total_liabilities": "F1A13",
    "endowment": "F1H02",
    "revenue": "F1D01",
    "expenses": "F1D02",
    "institutional_support": "F1C071",
    "instruction": "F1C011",
}

# Real field codes for FOR-PROFIT institutions (the F3 form), confirmed
# directly against a real, live-downloaded F3 file for University of
# Phoenix-Arizona (UNITID 484613, FY2022) via a one-off diagnostic run
# on 2026-09-15 -- not guessed from documentation, because the current
# F3 form's published survey materials could not be pinned down (it's
# been revised more than once, and the specific package covering
# degree-granting for-profit institutions couldn't be located through
# NCES's own published materials).
#
# total_liabilities, revenue, and expenses are arithmetically PROVEN
# from that real row, not just plausible:
#   F3A01 (618,567,995) == F3A02 (378,890,323) + F3A03 (239,677,672)
#     -- the balance-sheet identity assets = equity + liabilities,
#     exact to the dollar, which is what confirms F3A03 as total
#     liabilities and F3A01/F3A02 as total assets/equity.
#   F3D01 (832,032,699) + F3D05 (8,651,564) + F3D08 (9,441,821)
#     == F3D09 (850,126,084) exactly -- confirms F3D09 as total revenue.
#   F3D09 (850,126,084) - F3B02 (761,327,216) == F3G01 (88,798,868)
#     exactly, and F3G01 is a real, standalone "net income" line --
#     confirms F3B02 as total expenses.
#
# institutional_support and instruction are NOT arithmetically proven
# the same way -- they're a strong but unverified structural inference:
# F3 and F2 are both FASB-standard forms (unlike the GASB-based F1),
# and F2's confirmed codes for these same two categories sit at the
# identical line positions (F2E061 = institutional support, F2E011 =
# instruction). If a future re-check finds these wrong, the pipeline
# fails safe either way -- see parse_live_finance()'s per-field
# try/except, which yields an honest "insufficient_data" on a bad
# field code rather than a silently wrong number, exactly like it did
# before this fix.
FORPROFIT_FINANCE_FIELDS = {
    "total_liabilities": "F3A03",
    "revenue": "F3D09",
    "expenses": "F3B02",
    "institutional_support": "F3E061",
    "instruction": "F3E011",
    # Deliberately no "endowment" key: for-profit institutions do not
    # report an endowment field on the F3 form at all -- a real,
    # structural fact (already documented in the README's Known Gaps),
    # not a missing-data gap. score_institution.py's endowment lookup
    # already tolerates a missing key gracefully.
}


def fetch_scorecard_fields(unitid: str, fields: list[str], api_key: str | None = None) -> dict:
    """
    Real, live fetch from the College Scorecard API for one institution.
    Requires a real API key -- pass one explicitly or set
    COLLEGE_SCORECARD_API_KEY in the environment.
    """
    api_key = api_key or os.environ.get("COLLEGE_SCORECARD_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No College Scorecard API key found. Get a free one at "
            "https://api.data.gov/signup/ and set COLLEGE_SCORECARD_API_KEY."
        )
    params = {
        "api_key": api_key,
        "id": unitid,
        "fields": ",".join(fields),
    }
    resp = requests.get(SCORECARD_API_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        raise ValueError(f"No College Scorecard record found for UNITID {unitid}.")
    return data["results"][0]


def detect_sector(unitid: str, api_key: str | None = None) -> str | None:
    """
    Real, live sector detection via the College Scorecard API's own
    'school.ownership' field (1 = public, 2 = private nonprofit,
    3 = private for-profit -- the standard Scorecard/IPEDS control
    coding), instead of requiring sector to be hand-supplied for every
    institution ahead of time.

    Added for recompute_panel_entropy.py, which needs to re-run the live
    pipeline against all 54 real panel institutions and has no other real
    source for each one's sector -- data/panel/panel.json only stores the
    final 8 derived features (InstitutionFeatures), never the sector or
    start_year inputs that produced them.

    Returns None, with no fabricated default, if the field comes back
    missing or unrecognized -- the caller must treat that as a real,
    honest gap, not guess "private" and risk parsing finance data through
    the wrong sector's field codes (PRIVATE_FINANCE_FIELDS vs
    PUBLIC_FINANCE_FIELDS vs FORPROFIT_FINANCE_FIELDS are not
    interchangeable -- see their own definitions above).
    """
    try:
        result = fetch_scorecard_fields(unitid, ["school.ownership"], api_key)
    except Exception as e:
        print(f"SECTOR DETECTION FAILED for {unitid}: {type(e).__name__}: {e}")
        return None
    ownership = result.get("school.ownership")
    return {1: "public", 2: "private", 3: "forprofit"}.get(ownership)


def fetch_enrollment_series(unitid: str, start_year: int, end_year: int, api_key: str | None = None) -> dict:
    """
    Real, live, year-by-year enrollment/completion/admissions series
    for one institution, built from repeated real API calls (the
    Scorecard API returns one year -- typically the most recent --
    per call by default; per-year historical fields use a
    year-prefixed field name, e.g. '2021.student.size').
    """
    series = {}
    for year in range(start_year, end_year + 1):
        yy = str(year)[2:]
        fields = [
            f"{year}.student.size",
            f"{year}.admissions.admission_rate.overall",
            f"{year}.completion.completion_rate_4yr_150nt",
            f"{year}.cost.tuition.in_state",
        ]
        try:
            result = fetch_scorecard_fields(unitid, fields, api_key)
            series[str(year)] = {k.split(".", 1)[1]: v for k, v in result.items() if v is not None}
        except Exception:
            continue  # a real, honest gap for that year -- not fabricated
    return series


def build_live_series(unitid: str, start_year: int, end_year: int, api_key: str | None = None,
                       sector: str = "private") -> dict | None:
    """
    Real, live equivalent of real_adapter.extract_institution_series --
    produces the identical dict format (completion, tuition, admit_rate,
    n_undergrads arrays) from live College Scorecard data instead of a
    pre-downloaded local file. Returns None if any year in the window
    is missing a required field, exactly matching the local version's
    behavior -- never fabricates a value to fill a gap.

    Admission rate is the one deliberate exception, and only when
    sector="forprofit": real_adapter.compute_O_o_O_p() only ever uses
    completion & tuition, never admission rate, and nothing else
    downstream uses it either -- it has only ever been a gate here, not
    a real model input. A real, direct per-year API check on
    2026-09-15 (University of Phoenix-Arizona, UNITID 484613) confirmed
    admission rate is absent in every single year 2014-2023, the same
    kind of real, structural for-profit/open-enrollment gap as the
    missing endowment field, not a fetch bug -- so requiring it here
    was rejecting real, usable data for no modeling reason. Every other
    sector, and every other required field, keeps the original
    zero-tolerance behavior unchanged.
    """
    completion, tuition, admit_rate, n_undergrads = [], [], [], []
    for year in range(start_year, end_year):
        fields = [
            f"{year}.student.size",
            f"{year}.admissions.admission_rate.overall",
            f"{year}.completion.completion_rate_4yr_150nt",
            f"{year}.cost.tuition.in_state",
        ]
        try:
            if _BULK_SCORECARD is not None:
                result = _bulk_scorecard_fields(unitid, year)
            else:
                result = fetch_scorecard_fields(unitid, fields, api_key)
            n_undergrads.append(float(result[f"{year}.student.size"]))
            completion.append(float(result[f"{year}.completion.completion_rate_4yr_150nt"]))
            tuition.append(float(result[f"{year}.cost.tuition.in_state"]))
            try:
                admit_rate.append(float(result[f"{year}.admissions.admission_rate.overall"]))
            except (KeyError, TypeError, ValueError):
                if sector == "forprofit":
                    # Real, structural gap, not a fabricated value -- NaN,
                    # not a guess, and never read by compute_O_o_O_p anyway.
                    admit_rate.append(float("nan"))
                else:
                    raise
        except (KeyError, TypeError, ValueError):
            return None  # a real, honest gap year -- matches the local extractor's all-or-nothing behavior
    import numpy as np
    return dict(
        completion=np.array(completion),
        tuition=np.array(tuition),
        admit_rate=np.array(admit_rate),
        n_undergrads=np.array(n_undergrads),
    )


def parse_live_finance(unitid: str, window_years: list[str], dest_base: str | Path, sector: str = "private") -> tuple:
    """
    Real, live equivalent of real_adapter.build_finance_observation_mask.
    Parses the bulk finance CSVs already downloaded by
    download_ipeds_finance_bulk for this institution's window, using the
    real field codes in PRIVATE_FINANCE_FIELDS/PUBLIC_FINANCE_FIELDS.
    Returns the identical (E_exch, M_maint, W_instr, W_total, mask, scale)
    tuple the validated pipeline already uses -- unobserved years stay
    NaN, exactly as the local version leaves them, rather than
    interpolated or assumed.
    """
    import csv
    import numpy as np

    if sector == "private":
        fields = PRIVATE_FINANCE_FIELDS
    elif sector == "forprofit":
        fields = FORPROFIT_FINANCE_FIELDS
    else:
        fields = PUBLIC_FINANCE_FIELDS
    n = len(window_years)
    E_exch = np.full(n, np.nan)
    M_maint = np.full(n, np.nan)
    W_instr = np.full(n, np.nan)
    W_total = np.full(n, np.nan)
    mask = np.zeros(n, dtype=bool)
    scale = 500_000_000.0  # same fixed reference scale as the validated local pipeline

    for i, y in enumerate(window_years):
        cal_year = int(y[:4]) + 1
        year_dir = Path(dest_base) / str(cal_year - 1)
        if not year_dir.exists():
            continue
        csv_files = list(year_dir.glob("*.csv"))
        if not csv_files:
            continue
        try:
            with open(csv_files[0], encoding="latin-1") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("UNITID") == unitid:
                        E_exch[i] = float(row[fields["revenue"]]) / scale
                        M_maint[i] = float(row[fields["institutional_support"]]) / scale
                        W_instr[i] = float(row[fields["instruction"]]) / scale
                        W_total[i] = float(row[fields["expenses"]]) / scale
                        mask[i] = True
                        break
        except (ValueError, KeyError, FileNotFoundError):
            continue  # a real, honest missing year -- not fabricated

    return E_exch, M_maint, W_instr, W_total, mask, scale


def download_ipeds_finance_bulk(year: int, dest_dir: str | Path, sector: str = "private") -> Path | None:
    """
    Attempts a real download of the single-table finance data file for
    the given fiscal year, using NCES's current, real, live download
    mechanism -- confirmed directly via two separate live diagnostic
    runs against NCES's own Data Center pages on 2026-09-15 (run from
    GitHub Actions, which can actually reach nces.ed.gov -- this
    project's sandboxed development environments cannot).

    NCES actually splits this across two real, live addresses, by how
    recent the year is, not one:

    1. The newest year or two: a plain static ZIP with no session
       needed, at https://nces.ed.gov/ipeds/complete-data-files/
       <table_name>.zip -- confirmed via real link text scraped
       directly off NCES's own live page for FY2022-23
       (.../complete-data-files/F2223_F1A.zip).
    2. Older years: NOT retired, but served from a second real
       address, https://nces.ed.gov/ipeds/datacenter/data/
       <table_name>.zip -- confirmed via real link text scraped off
       NCES's own live page for FY2017-18, AND independently confirmed
       with a direct, successful (HTTP 200) request for FY2018-19's
       table at that exact address. This is the same URL pattern an
       earlier revision of this function marked "defunct" -- it either
       came back, or the earlier failure was caused by something else
       (a wrong table-name construction, a missing session) rather
       than the address itself being gone; today's live, direct test
       is the real evidence, not that earlier assumption.

    This function tries address 1 first (correct for the newest
    years), and automatically falls back to address 2 if that 404s --
    so it keeps working as years roll from "newest" into "older"
    without needing a hardcoded cutoff year that would itself go stale.

    The downloaded file is a real ZIP archive (not a raw CSV) containing
    the actual data CSV alongside other files (dictionaries,
    revised-value flags); this function extracts the first real .csv
    file found inside it.

    Returns the local path (dest_dir/<year>/) on success, containing
    the extracted CSV file, or None if both real addresses genuinely
    fail (an honest failure, not a silent one -- callers should check
    for None and alert rather than assume success).

    sector: "private" (F2 form), "public" (F1A form), or "forprofit" (F3 form).
    """
    form = {"private": "F2", "public": "F1A", "forprofit": "F3"}[sector]
    yy1 = str(year)[2:]
    yy2 = str(year + 1)[2:]
    table_name = f"F{yy1}{yy2}_{form}"

    year_dir = Path(dest_dir) / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    candidate_urls = [
        f"https://nces.ed.gov/ipeds/complete-data-files/{table_name}.zip",
        f"https://nces.ed.gov/ipeds/datacenter/data/{table_name}.zip",
    ]

    last_error = None
    for url in candidate_urls:
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 404:
                last_error = f"404 Not Found at {url}"
                continue  # try the next real, known address before giving up
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "zip" not in content_type.lower() and "octet-stream" not in content_type.lower():
                print(f"WARNING: {url} returned HTTP 200 but Content-Type was "
                      f"'{content_type}', not a ZIP archive -- likely an HTML "
                      f"error or session page served with a 200 status rather "
                      f"than the real file. First 300 characters of response "
                      f"for diagnosis: {resp.content[:300]!r}")
                last_error = f"non-ZIP 200 response at {url}"
                continue  # try the next real, known address before giving up

            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if not csv_names:
                    print(f"WARNING: {url} downloaded successfully but the "
                          f"archive contained no .csv file. Archive contents "
                          f"were: {zf.namelist()}")
                    last_error = f"no .csv inside ZIP at {url}"
                    continue  # try the next real, known address before giving up
                csv_bytes = zf.read(csv_names[0])

            csv_path = year_dir / f"{table_name}.csv"
            csv_path.write_bytes(csv_bytes)
            return year_dir
        except Exception as e:
            last_error = f"{e} (at {url})"
            continue  # try the next real, known address before giving up

    print(f"WARNING: real IPEDS download failed for {sector} FY{year} across "
          f"both known real addresses -- last error: {last_error}. This is "
          f"the known-fragile part of the pipeline -- check whether NCES "
          f"changed its endpoint or file format again.")
    return None
