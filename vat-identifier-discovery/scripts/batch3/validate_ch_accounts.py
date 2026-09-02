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
    py -3.14 validate_ch_accounts.py review [date] [sample_size] [seed]  # sample bare-VAT non-matches
"""

from __future__ import annotations

import os
import random
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ch_accounts_utils import (
    contains_vat_word,
    download_daily_zip,
    find_vat_mentions,
    find_vat_word_contexts,
    iter_company_numbers_in_zip,
    read_member_text,
)
from csv_utils import load_columns
from hmrc_vat_check import check_vat_number, get_access_token, is_valid_uk_vat_checksum, normalize_vat_number

SAMPLE_CSV = "../../BasicCompanyData-2026-08-01-part1_7.csv"
COMPANY_NAME_COL = "CompanyName"
COMPANY_NUMBER_COL = " CompanyNumber"

DEFAULT_DATE = "2026-08-26"


def zip_path_for_date(date: str) -> str:
    """Return the local cache path for date's bulk accounts ZIP."""
    return f"ch_accounts_{date}.zip"


def ensure_zip(date: str) -> str:
    """Return the local path to date's bulk accounts ZIP, downloading it
    first if it isn't already cached on disk.
    """
    path = zip_path_for_date(date)
    if not os.path.exists(path):
        print(f"Downloading {date}'s bulk accounts ZIP (this is ~100MB+, may take a while)...")
        download_daily_zip(date, path)
    return path


def load_sample_lookup() -> dict[str, str]:
    """Build {normalized (stripped, uppercased) CompanyNumber: CompanyName} from the sample CSV."""
    df = load_columns(SAMPLE_CSV, [COMPANY_NAME_COL, COMPANY_NUMBER_COL])
    return {number.strip().upper(): name for name, number in zip(df[COMPANY_NAME_COL], df[COMPANY_NUMBER_COL])}


def inspect(date: str) -> None:
    """Print the bulk ZIP's filing count, then the first filing's plain-text
    length and any VAT mentions found in it, as a quick eyeball check of
    the data before running scan()/join() over the whole ZIP.
    """
    path = ensure_zip(date)
    entries = list(iter_company_numbers_in_zip(path))
    print(f"{date}: {len(entries)} filings in bulk ZIP")
    if not entries:
        print("No recognized filings in this ZIP -- nothing to inspect.")
        return
    number, member_name = entries[0]
    print(f"\nFirst filing: CompanyNumber={number}, file={member_name}")
    with zipfile.ZipFile(path) as zf:
        text = read_member_text(zf, member_name)
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
    if not entries:
        print("No recognized filings in this ZIP -- nothing to scan.")
        return []

    all_hits = []
    n_filings_with_vat_word = 0
    with zipfile.ZipFile(path) as zf:
        for number, member_name in entries:
            text = read_member_text(zf, member_name)
            if contains_vat_word(text):
                n_filings_with_vat_word += 1
            for hit in find_vat_mentions(text):
                all_hits.append({"company_number": number, "member_name": member_name, **hit})

    n_filings_with_hit = len({h["member_name"] for h in all_hits})
    print(f"Filings with >=1 VAT mention: {n_filings_with_hit}/{len(entries)} "
          f"({n_filings_with_hit / len(entries):.2%})")
    print(f"Total VAT-mention matches (a filing can have more than one): {len(all_hits)}")
    print(f"Filings mentioning the bare word 'VAT' at all (diagnostic -- distinguishes 'topic never "
          f"comes up' from 'comes up, but not in a recognised format'): {n_filings_with_vat_word}/{len(entries)} "
          f"({n_filings_with_vat_word / len(entries):.2%})")
    return all_hits


def join(date: str) -> None:
    """Scan date's bulk ZIP for filings whose CompanyNumber is in the sample
    CSV, then for each VAT mention found print its checksum validity --
    plus an HMRC sandbox lookup the first time each distinct VRN is seen
    this run -- ending with a summary of the checksum-invalid rate.
    """
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
    with zipfile.ZipFile(path) as zf:
        for number, member_name in matched_entries:
            text = read_member_text(zf, member_name)
            for hit in find_vat_mentions(text):
                hits.append({"company_number": number, "member_name": member_name, **hit})

    n_filings_with_hit = len({h["member_name"] for h in hits})
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
          f"({(n_checked - n_checksum_valid) / n_checked:.1%} checksum-invalid rate)")
    print(f"Distinct VRNs sandbox-checked: {len(seen_vrns)}")


def review_bare_vat_mentions(date: str, sample_size: int = 20, seed: int = 0) -> None:
    """Manually-inspectable sample of filings that mention the bare word
    "VAT" but produced no VAT_MENTION_RE match -- resolves whether the
    pattern's 0-hit result is a genuine negative or a missed disclosure
    format (see FINDINGS.md, Companies House bulk accounts entry).
    """
    path = ensure_zip(date)
    entries = list(iter_company_numbers_in_zip(path))
    print(f"{date}: {len(entries)} filings in bulk ZIP")

    unmatched_bare_mentions = []
    with zipfile.ZipFile(path) as zf:
        for number, member_name in entries:
            text = read_member_text(zf, member_name)
            if contains_vat_word(text) and not find_vat_mentions(text):
                unmatched_bare_mentions.append((number, member_name, find_vat_word_contexts(text)))

    print(f"Filings with a bare 'VAT' mention but no VAT_MENTION_RE match: {len(unmatched_bare_mentions)}")

    sample = random.Random(seed).sample(unmatched_bare_mentions, k=min(sample_size, len(unmatched_bare_mentions)))
    for number, member_name, contexts in sample:
        print(f"\n--- CompanyNumber={number} file={member_name} ({len(contexts)} bare mention(s)) ---")
        for context in contexts:
            print(f"  ...{context}...")


def main() -> None:
    """CLI entry point: dispatch to inspect/scan/join/review based on
    sys.argv (see module docstring for usage).
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    date = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DATE
    if mode == "inspect":
        inspect(date)
    elif mode == "scan":
        scan(date)
    elif mode == "join":
        join(date)
    elif mode == "review":
        sample_size_raw = sys.argv[3] if len(sys.argv) > 3 else None
        seed_raw = sys.argv[4] if len(sys.argv) > 4 else None
        try:
            sample_size = int(sample_size_raw) if sample_size_raw is not None else 20
        except ValueError:
            print(f"Invalid sample_size: {sample_size_raw!r} (must be a positive integer)")
            return
        if sample_size <= 0:
            print(f"Invalid sample_size: {sample_size} (must be a positive integer)")
            return
        try:
            seed = int(seed_raw) if seed_raw is not None else 0
        except ValueError:
            print(f"Invalid seed: {seed_raw!r} (must be an integer)")
            return
        review_bare_vat_mentions(date, sample_size=sample_size, seed=seed)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
