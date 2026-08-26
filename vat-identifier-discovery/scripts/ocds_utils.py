"""Reusable helpers for inspecting bulk OCDS (Open Contracting Data Standard)
data — e.g. Find a Tender's bulk-download .jsonl.gz files, where each line is
one compiled release / record for a contracting process.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator


def iter_records(path: str) -> Iterator[dict]:
    """Yield each parsed JSON object from a (gzip-compressed) OCDS .jsonl file.

    Skips blank lines. Works on plain .jsonl too (gzip.open transparently
    handles non-gzip files raising, so callers with plain .jsonl should open
    it directly instead).
    """
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def get_parties(record: dict) -> list[dict]:
    """Return a compiled release/record's top-level 'parties' array (or [])."""
    return record.get("parties") or []


def iter_identifiers(party: dict) -> Iterator[tuple[str, str]]:
    """Yield (scheme, id) for a party's primary identifier plus any
    additionalIdentifiers. Entries missing a scheme or id are skipped.
    """
    candidates = []
    if party.get("identifier"):
        candidates.append(party["identifier"])
    candidates.extend(party.get("additionalIdentifiers") or [])

    for ident in candidates:
        scheme = ident.get("scheme")
        ident_id = ident.get("id")
        if scheme and ident_id:
            yield scheme, str(ident_id)


def find_scheme_id(party: dict, scheme: str) -> str | None:
    """Return the id for the first identifier on `party` matching `scheme`
    (case-sensitive, e.g. "GB-COH" or "GB-VAT"), or None if absent.
    """
    for found_scheme, ident_id in iter_identifiers(party):
        if found_scheme == scheme:
            return ident_id
    return None


def extract_gb_coh_vat_pairs(record: dict) -> list[dict]:
    """Scan a record's parties for ones carrying a GB-COH (Companies House
    number) identifier, and report whether a GB-VAT identifier is also
    present alongside it.

    Returns a list of dicts: {party_name, company_number, vat_number}
    (vat_number is None when the party has a GB-COH id but no GB-VAT one).
    """
    results = []
    for party in get_parties(record):
        company_number = find_scheme_id(party, "GB-COH")
        if company_number is None:
            continue
        results.append(
            {
                "party_name": party.get("name"),
                "company_number": company_number,
                "vat_number": find_scheme_id(party, "GB-VAT"),
            }
        )
    return results
