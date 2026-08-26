"""Reusable helpers for querying the public PEPPOL Directory REST API
(https://directory.peppol.eu/search/1.0/json) — no authentication required.

Each match is one participant registration, not a multi-scheme identifier
record: `participantID.value` is "<ICD scheme code>:<local id>", e.g.
"9932:gb250147634" for a UK-VAT-scheme registration. A company appears once
per participant ID it has registered under, so a single match cannot carry
both a Companies House number and a VAT number the way an OCDS party can.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import requests

SEARCH_URL = "https://directory.peppol.eu/search/1.0/json"
PAGE_SIZE = 100

# The Directory's REST API allows at most 2 queries/second and returns
# HTTP 429 above that rate (docs.peppol.eu REST API docs).
MIN_REQUEST_INTERVAL_SECONDS = 0.5
MAX_429_RETRIES = 4
RETRY_BACKOFF_SECONDS = 1.0

# Any single query is capped at 1,000 results by the Directory itself;
# requesting a page beyond that returns an error rather than more matches.
MAX_RESULT_COUNT = 1000
MAX_RESULT_PAGES = MAX_RESULT_COUNT // PAGE_SIZE

_last_request_time: float | None = None


def search(query: str = "", **params: str | int) -> dict:
    """Run one page of a PEPPOL Directory search and return the raw JSON.

    `query` is the free-text `q` parameter; additional query params (e.g.
    country="GB", resultPageIndex=2) are passed through as-is. See
    iter_all_results() to page through every match automatically.

    Waits out the Directory's minimum request interval before sending, and
    retries a bounded number of times (with backoff) if the Directory
    responds with HTTP 429 (rate limited).
    """
    global _last_request_time

    request_params: dict[str, str | int] = {"resultPageCount": PAGE_SIZE, **params}
    if query:
        request_params["q"] = query

    for attempt in range(MAX_429_RETRIES + 1):
        if _last_request_time is not None:
            elapsed = time.monotonic() - _last_request_time
            if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
                time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        response = requests.get(SEARCH_URL, params=request_params, timeout=30)
        _last_request_time = time.monotonic()
        if response.status_code == 429 and attempt < MAX_429_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
            continue
        response.raise_for_status()
        return response.json()

    raise AssertionError("unreachable")  # loop always returns or raises


def iter_all_results(query: str = "", max_pages: int | None = None, **params: str | int) -> Iterator[dict]:
    """Yield every match across all result pages for a given search.

    Stops at the Directory's 1,000-result cap (10 pages of PAGE_SIZE=100)
    even if `max_pages` would allow more, since requesting page index 10+
    fails rather than returning further matches. If the query's
    total-result-count exceeds the cap, prints a warning that results were
    truncated -- split the query (e.g. by name prefix) or use the
    Directory's bulk export feature to get the rest.
    """
    page_index = 0
    total_result_count: int | None = None
    while (max_pages is None or page_index < max_pages) and page_index < MAX_RESULT_PAGES:
        data = search(query, resultPageIndex=page_index, **params)
        if total_result_count is None:
            total_result_count = data.get("total-result-count")
        matches = data.get("matches", [])
        if not matches:
            return
        yield from matches
        page_index += 1

    if total_result_count is not None and total_result_count > MAX_RESULT_COUNT:
        print(
            f"iter_all_results: truncated at the Directory's {MAX_RESULT_COUNT}-result "
            f"cap ({total_result_count} total matches available) -- split the query or "
            "use bulk export to see the rest."
        )


def get_scheme_and_local_id(match: dict) -> tuple[str, str]:
    """Split a match's participantID.value into (ICD scheme code, local id).

    E.g. "9932:gb250147634" -> ("9932", "gb250147634"). Returns ("", "") if
    the value is missing or unexpectedly shaped, so callers always get a str
    pair back rather than having to handle a None case.
    """
    raw = match.get("participantID", {}).get("value", "")
    if ":" not in raw:
        return "", ""
    scheme, local_id = raw.split(":", 1)
    return scheme, local_id


def get_names(match: dict) -> list[str]:
    """Return all registered entity names on a match."""
    names = []
    for entity in match.get("entities", []):
        for name_entry in entity.get("name", []):
            if name_entry.get("name"):
                names.append(name_entry["name"])
    return names


def get_country(match: dict) -> str | None:
    """Return the first entity's country code, if any."""
    entities = match.get("entities", [])
    return entities[0].get("countryCode") if entities else None
