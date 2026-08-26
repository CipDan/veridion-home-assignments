"""Reusable helpers for querying the public PEPPOL Directory REST API
(https://directory.peppol.eu/search/1.0/json) — no authentication required.

Each match is one participant registration, not a multi-scheme identifier
record: `participantID.value` is "<ICD scheme code>:<local id>", e.g.
"9932:gb250147634" for a UK-VAT-scheme registration. A company appears once
per participant ID it has registered under, so a single match cannot carry
both a Companies House number and a VAT number the way an OCDS party can.
"""

from __future__ import annotations

from collections.abc import Iterator

import requests

SEARCH_URL = "https://directory.peppol.eu/search/1.0/json"
PAGE_SIZE = 100


def search(query: str = "", **params: str | int) -> dict:
    """Run one page of a PEPPOL Directory search and return the raw JSON.

    `query` is the free-text `q` parameter; additional query params (e.g.
    country="GB", resultPageIndex=2) are passed through as-is. See
    iter_all_results() to page through every match automatically.
    """
    request_params: dict[str, str | int] = {"resultPageCount": PAGE_SIZE, **params}
    if query:
        request_params["q"] = query
    response = requests.get(SEARCH_URL, params=request_params, timeout=30)
    response.raise_for_status()
    return response.json()


def iter_all_results(query: str = "", max_pages: int | None = None, **params: str | int) -> Iterator[dict]:
    """Yield every match across all result pages for a given search."""
    page_index = 0
    while max_pages is None or page_index < max_pages:
        data = search(query, resultPageIndex=page_index, **params)
        matches = data.get("matches", [])
        if not matches:
            return
        yield from matches
        page_index += 1


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
