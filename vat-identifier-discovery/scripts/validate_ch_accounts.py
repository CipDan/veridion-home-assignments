"""Batch 3 (Tier 3) validation: Companies House bulk accounts data (iXBRL/HTML).

Resolves FINDINGS.md Open Question #4: what fraction of filed accounts
actually mention a VAT registration number in their notes? Unlike the other
Tier 3/2 candidates, the join key here is CompanyNumber (exact) -- the
daily bulk ZIP's filenames already carry it, in the same format as the
sample CSV's " CompanyNumber" column.

Usage:
    py -3.14 validate_ch_accounts.py inspect [date]        # zip contents, one filing's text
    py -3.14 validate_ch_accounts.py scan [date]           # VAT-mention rate across ALL filings that day
    py -3.14 validate_ch_accounts.py join [date]           # scan + join to sample + checksum/sandbox
"""

from __future__ import annotations

import os
import sys

from ch_accounts_utils import (
    contains_vat_word,
    download_daily_zip,
    find_vat_mentions,
    iter_company_numbers_in_zip,
    read_member_text,
)
from csv_utils import load_columns
from hmrc_vat_check import check_vat_number, get_access_token, is_valid_uk_vat_checksum, normalize_vat_number

SAMPLE_CSV = "../BasicCompanyData-2026-08-01-part1_7.csv"
COMPANY_NAME_COL = "CompanyName"
COMPANY_NUMBER_COL = " CompanyNumber"

DEFAULT_DATE = "2026-08-26"


def zip_path_for_date(date: str) -> str:
    return f"ch_accounts_{date}.zip"


def ensure_zip(date: str) -> str:
    path = zip_path_for_date(date)
    if not os.path.exists(path):
        print(f"Downloading {date}'s bulk accounts ZIP (this is ~100MB+, may take a while)...")
        download_daily_zip(date, path)
    return path


def load_sample_lookup() -> dict[str, str]:
    """Build {CompanyNumber: CompanyName} from the sample CSV."""
    df = load_columns(SAMPLE_CSV, [COMPANY_NAME_COL, COMPANY_NUMBER_COL])
    return {number.strip().upper(): name for name, number in zip(df[COMPANY_NAME_COL], df[COMPANY_NUMBER_COL])}


def inspect(date: str) -> None:
    path = ensure_zip(date)
    entries = list(iter_company_numbers_in_zip(path))
    print(f"{date}: {len(entries)} filings in bulk ZIP")
    number, member_name = entries[0]
    print(f"\nFirst filing: CompanyNumber={number}, file={member_name}")
    text = read_member_text(path, member_name)
    print(f"Plain-text length: {len(text)} chars")
    hits = find_vat_mentions(text)
    print(f"VAT mentions in this one filing: {len(hits)}")
    for hit in hits:
        print(f"  raw={hit['raw']!r} context=...{hit['context']}...")


def scan(date: str) -> list[dict]:
    """Scan every filing in the day's ZIP for a VAT mention, regardless of
    whether its CompanyNumber is in our sample -- gives the overall
    disclosure rate this source's practice implies, before narrowing to the
    sample-matched subset in join().
    """
    path = ensure_zip(date)
    entries = list(iter_company_numbers_in_zip(path))
    print(f"{date}: {len(entries)} filings in bulk ZIP")

    all_hits = []
    n_filings_with_vat_word = 0
    for number, member_name in entries:
        text = read_member_text(path, member_name)
        if contains_vat_word(text):
            n_filings_with_vat_word += 1
        for hit in find_vat_mentions(text):
            all_hits.append({"company_number": number, "member_name": member_name, **hit})

    n_filings_with_hit = len({h["company_number"] for h in all_hits})
    print(f"Filings with >=1 VAT mention: {n_filings_with_hit}/{len(entries)} "
          f"({n_filings_with_hit / len(entries):.2%})")
    print(f"Total VAT-mention matches (a filing can have more than one): {len(all_hits)}")
    print(f"Filings mentioning the bare word 'VAT' at all (diagnostic -- distinguishes 'topic never "
          f"comes up' from 'comes up, but not in a recognised format'): {n_filings_with_vat_word}/{len(entries)} "
          f"({n_filings_with_vat_word / len(entries):.2%})")
    return all_hits


def join(date: str) -> None:
    path = ensure_zip(date)
    print("Loading sample CSV CompanyNumber lookup...")
    sample_lookup = load_sample_lookup()
    print(f"Sample lookup size: {len(sample_lookup)}")

    entries = list(iter_company_numbers_in_zip(path))
    matched_entries = [(number, member_name) for number, member_name in entries if number.upper() in sample_lookup]
    print(f"{date}: {len(entries)} filings in bulk ZIP, {len(matched_entries)} have a CompanyNumber in the sample CSV")

    if not matched_entries:
        print("No overlap between this day's filers and the sample CSV -- nothing to scan for VAT mentions.")
        return

    hits = []
    for number, member_name in matched_entries:
        text = read_member_text(path, member_name)
        for hit in find_vat_mentions(text):
            hits.append({"company_number": number, "member_name": member_name, **hit})

    n_filings_with_hit = len({h["company_number"] for h in hits})
    print(f"Sample-matched filings with >=1 VAT mention: {n_filings_with_hit}/{len(matched_entries)} "
          f"({n_filings_with_hit / len(matched_entries):.2%})")

    if not hits:
        return

    token = get_access_token()
    n_checksum_valid = 0
    n_checked = 0
    seen_vrns = set()
    for hit in hits:
        raw_upper = hit["raw"].strip().upper()
        vrn = normalize_vat_number(raw_upper)
        valid, style = is_valid_uk_vat_checksum(vrn)
        sample_name = sample_lookup[hit["company_number"].upper()]

        print("\n---")
        print(f"Sample CompanyNumber: {hit['company_number']}")
        print(f"Sample CompanyName:   {sample_name}")
        print(f"Filing:               {hit['member_name']}")
        print(f"Matched raw value:    {hit['raw']}")
        print(f"Context:              ...{hit['context']}...")
        print(f"Normalized VRN:       {vrn}")
        print(f"Checksum valid:       {valid} ({style})")

        n_checked += 1
        if valid:
            n_checksum_valid += 1

        if vrn in seen_vrns:
            continue  # avoid a redundant sandbox call for a VRN already checked this run
        seen_vrns.add(vrn)
        sandbox = check_vat_number(vrn, token)
        print(f"Sandbox response:     {sandbox}")

        if not valid:
            print("  ^^ FLAGGED: checksum-invalid -- likely a false positive from the regex match, not a real VRN")

    print(f"\nTotal VAT-mention matches: {len(hits)}")
    print(f"Checksum valid: {n_checksum_valid}/{n_checked} "
          f"({(n_checked - n_checksum_valid) / n_checked:.1%} measured false-positive rate)")
    print(f"Distinct VRNs sandbox-checked: {len(seen_vrns)}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    date = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DATE
    if mode == "inspect":
        inspect(date)
    elif mode == "scan":
        scan(date)
    elif mode == "join":
        join(date)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
