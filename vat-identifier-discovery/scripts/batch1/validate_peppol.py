"""Batch 1 (Tier 1) validation: PEPPOL e-invoicing directory.

Checks two things from FINDINGS.md:
  - Open Question #1: the correct Peppol EAS scheme code for UK VAT numbers
    (resolved separately against docs.peppol.eu as 9932, i.e. "GB:VAT" --
    9930 is Germany, not the UK).
  - Whether real GB directory entries carry a 9932 (GB:VAT) participant ID,
    and whether any can be joined back to the Companies House sample. Only
    a CompanyName join is possible: the Peppol scheme list has no UK
    Companies House number scheme at all ("0190" is the Dutch OIN scheme,
    not UK, contrary to FINDINGS.md's original claim), and each directory
    match carries only one participant ID scheme, so even if one existed it
    couldn't appear on the same record as a VAT id.

Usage:
    py -3.14 validate_peppol.py inspect       # print one raw GB match
    py -3.14 validate_peppol.py scan [pages]  # scan GB matches for 9932 ids
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csv_utils import load_columns
from hmrc_vat_check import check_vat_number, get_access_token, is_valid_uk_vat_checksum
from peppol_utils import get_country, get_names, get_scheme_and_local_id, iter_all_results

GB_VAT_ICD = "9932"
SAMPLE_CSV = "../../BasicCompanyData-2026-08-01-part1_7.csv"
COMPANY_NAME_COL = "CompanyName"
COMPANY_NUMBER_COL = " CompanyNumber"


def normalize_name(name: str) -> str:
    """Uppercase and strip all whitespace, so mid-word spacing artifacts in
    the Peppol directory's names (e.g. "LIM ITED") don't block a match.
    """
    return "".join(name.upper().split())


def load_sample_name_lookup() -> dict[str, list[tuple[str, str]]]:
    """Build {normalized CompanyName: [(CompanyNumber, original name), ...]}.

    A normalized name can map to more than one CompanyNumber in the sample
    (631 cases as of the 2026-08-01 snapshot -- distinct companies that
    happen to share a name, e.g. FC/OE overseas-company re-registrations).
    Keeping every candidate lets callers tell an unambiguous match from an
    ambiguous one, instead of silently keeping whichever row was read last.
    """
    df = load_columns(SAMPLE_CSV, [COMPANY_NAME_COL, COMPANY_NUMBER_COL])
    lookup: dict[str, list[tuple[str, str]]] = {}
    for name, number in zip(df[COMPANY_NAME_COL], df[COMPANY_NUMBER_COL]):
        lookup.setdefault(normalize_name(name), []).append((number.strip(), name))
    return lookup


def inspect_one() -> None:
    """Print the raw JSON of the first GB match from the Peppol Directory,
    as a quick eyeball check of the response shape before scan()/join().
    """
    for entity in iter_all_results(country="GB", max_pages=1):
        print(json.dumps(entity, indent=2))
        return
    print("No GB matches returned.")


def scan(max_pages: int | None) -> None:
    """Scan up to max_pages of GB Peppol Directory matches, printing the
    participant-ID scheme breakdown and a preview of entities registered
    under the 9932 (GB:VAT) scheme.
    """
    n_entities = 0
    scheme_counts: dict[str, int] = {}
    vat_hits = []

    for match in iter_all_results(country="GB", max_pages=max_pages):
        n_entities += 1
        scheme, local_id = get_scheme_and_local_id(match)
        scheme_counts[scheme] = scheme_counts.get(scheme, 0) + 1
        if scheme == GB_VAT_ICD:
            digits = "".join(ch for ch in local_id if ch.isdigit())
            vat_hits.append({"names": get_names(match), "country": get_country(match), "vat_digits": digits})

    print(f"GB entities scanned: {n_entities}")
    print(f"Participant ID scheme breakdown: {scheme_counts}")
    print(f"Entities registered under {GB_VAT_ICD} (GB:VAT): {len(vat_hits)}")
    for hit in vat_hits[:15]:
        print(hit)


def join(max_pages: int | None) -> None:
    """Scan up to max_pages of GB Peppol Directory matches for 9932
    (GB:VAT) entries, join them to the sample CSV by normalized
    CompanyName, then for each unambiguous match print its VAT digits,
    checksum validity, and an HMRC sandbox lookup.
    """
    print("Loading sample CSV CompanyName lookup...")
    sample_lookup = load_sample_name_lookup()
    print(f"Sample lookup size: {len(sample_lookup)}")

    n_entities = 0
    n_vat_hits = 0
    matches = []
    ambiguous = []

    for match in iter_all_results(country="GB", max_pages=max_pages):
        n_entities += 1
        scheme, local_id = get_scheme_and_local_id(match)
        if scheme != GB_VAT_ICD:
            continue
        n_vat_hits += 1
        digits = "".join(ch for ch in local_id if ch.isdigit())
        for name in get_names(match):
            candidates = sample_lookup.get(normalize_name(name))
            if not candidates:
                continue
            if len(candidates) > 1:
                ambiguous.append({"peppol_name": name, "vat_digits": digits, "candidates": candidates})
            else:
                sample_number, sample_name = candidates[0]
                matches.append({"peppol_name": name, "vat_digits": digits, "sample_number": sample_number, "sample_name": sample_name})
            break

    print(f"GB entities scanned: {n_entities}, with 9932 (GB:VAT) id: {n_vat_hits}")
    print(f"Matched to sample CSV by CompanyName (unambiguous): {len(matches)}")
    print(f"Ambiguous matches (name maps to >1 CompanyNumber, skipped): {len(ambiguous)}")
    for hit in ambiguous[:15]:
        print(f"  {hit['peppol_name']!r} (VAT {hit['vat_digits']}) -> candidates {hit['candidates']}")

    if not matches:
        return

    token = get_access_token()
    for m in matches:
        valid, style = is_valid_uk_vat_checksum(m["vat_digits"])
        sandbox = check_vat_number(m["vat_digits"], token)
        print("\n---")
        print(f"Sample CompanyNumber: {m['sample_number']}")
        print(f"Sample CompanyName:   {m['sample_name']}")
        print(f"Peppol entity name:   {m['peppol_name']}")
        print(f"VAT number (digits):  {m['vat_digits']}")
        print(f"Checksum valid:       {valid} ({style})")
        print(f"Sandbox response:     {sandbox}")


def main() -> None:
    """CLI entry point: dispatch to inspect/scan/join based on sys.argv
    (see module docstring for usage).
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if mode == "inspect":
        inspect_one()
    elif mode == "scan":
        max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else None
        scan(max_pages)
    elif mode == "join":
        max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else None
        join(max_pages)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
