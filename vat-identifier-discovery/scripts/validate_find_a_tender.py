"""Batch 1 (Tier 1) validation: Find a Tender / OCDS procurement records.

Scans the bulk OCDS release data (data.open-contracting.org publication #41,
downloaded as fts_2026.jsonl.gz) for parties carrying a GB-COH (Companies
House number) identifier, records whether a GB-VAT identifier is populated
alongside it, and joins matches against the Companies House sample CSV on
CompanyNumber (exact).

See FINDINGS.md Tier 1 / Open Questions #2 for the question this answers:
is the GB-VAT additionalIdentifiers pattern actually populated on Find a
Tender's own live published records?
"""

from __future__ import annotations

import sys

from csv_utils import load_columns
from hmrc_vat_check import get_access_token, is_valid_uk_vat_checksum, check_vat_number
from ocds_utils import extract_gb_coh_vat_pairs, iter_records

SAMPLE_CSV = "../BasicCompanyData-2026-08-01-part1_7.csv"
DEFAULT_FTS_JSONL_GZ = "fts_2026.jsonl.gz"

# Sample CSV's CompanyNumber column has a leading space in the header.
COMPANY_NUMBER_COL = " CompanyNumber"
COMPANY_NAME_COL = "CompanyName"
POSTCODE_COL = "RegAddress.PostCode"


def load_sample_lookup() -> dict[str, dict]:
    """Build {normalized CompanyNumber: {name, postcode}} from the sample CSV."""
    # Unpacked positionally (as plain tuples) rather than via itertuples()
    # attribute access: " CompanyNumber" (leading space) and
    # "RegAddress.PostCode" (a dot) aren't valid Python identifiers, so
    # itertuples() silently renames those fields to "_1"/"_2" and getattr()
    # by name fails. pandas.read_csv(usecols=...) always returns columns in
    # the CSV's own file order regardless of the usecols list's order, so
    # the unpacking order below (name, number, postcode) matches this
    # sample's column layout (CompanyName, CompanyNumber, ..., PostCode).
    df = load_columns(SAMPLE_CSV, [COMPANY_NAME_COL, COMPANY_NUMBER_COL, POSTCODE_COL])
    lookup = {}
    for name, number, postcode in df.itertuples(index=False, name=None):
        lookup[number.strip().upper()] = {"name": name, "postcode": postcode}
    return lookup


def scan_fts(path: str = DEFAULT_FTS_JSONL_GZ, limit: int | None = None) -> dict:
    """Scan the FTS bulk file, returning coverage stats and GB-COH+GB-VAT hits."""
    n_records = 0
    n_parties_gbcoh = 0
    n_parties_gbvat = 0
    vat_hits = []

    for record in iter_records(path):
        n_records += 1
        for pair in extract_gb_coh_vat_pairs(record):
            n_parties_gbcoh += 1
            if pair["vat_number"]:
                n_parties_gbvat += 1
                vat_hits.append(pair)
        if limit is not None and n_records >= limit:
            break

    return {
        "n_records": n_records,
        "n_parties_gbcoh": n_parties_gbcoh,
        "n_parties_gbvat": n_parties_gbvat,
        "vat_hits": vat_hits,
    }


def join_against_sample(vat_hits: list[dict], sample_lookup: dict[str, dict]) -> list[dict]:
    """Join GB-VAT hits against the sample CSV on normalized CompanyNumber."""
    matches = []
    for hit in vat_hits:
        number = hit["company_number"].strip().upper().zfill(8)
        sample_row = sample_lookup.get(number)
        if sample_row is not None:
            matches.append({**hit, "sample": sample_row})
    return matches


def main() -> None:
    """CLI entry point: scan the FTS bulk file for GB-COH/GB-VAT pairs, join
    hits to the sample CSV, and print each match's checksum validity and an
    HMRC sandbox lookup (see module docstring for usage: [path] [limit]).
    """
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FTS_JSONL_GZ
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Scanning {path} (limit={limit})...")
    stats = scan_fts(path=path, limit=limit)
    print(f"Records scanned: {stats['n_records']}")
    print(f"Parties with GB-COH identifier: {stats['n_parties_gbcoh']}")
    print(f"Parties with GB-COH AND GB-VAT identifier: {stats['n_parties_gbvat']}")

    if not stats["vat_hits"]:
        print("No GB-VAT hits found in this scan window.")
        return

    print("\nLoading sample CSV CompanyNumber lookup...")
    sample_lookup = load_sample_lookup()
    print(f"Sample lookup size: {len(sample_lookup)}")

    matches = join_against_sample(stats["vat_hits"], sample_lookup)
    print(f"\nGB-VAT hits joined to sample CSV by CompanyNumber: {len(matches)}")

    if not matches:
        return

    token = get_access_token()
    for m in matches:
        vrn = m["vat_number"].strip().upper()
        digits = "".join(ch for ch in vrn if ch.isdigit())
        valid, style = is_valid_uk_vat_checksum(digits)
        sandbox = check_vat_number(digits, token)
        print("\n---")
        print(f"CompanyNumber:      {m['company_number']}")
        print(f"Sample CompanyName: {m['sample']['name']}")
        print(f"FTS party name:     {m['party_name']}")
        print(f"VAT number (raw):   {m['vat_number']}")
        print(f"Checksum valid:     {valid} ({style})")
        print(f"Sandbox response:   {sandbox}")


if __name__ == "__main__":
    main()
