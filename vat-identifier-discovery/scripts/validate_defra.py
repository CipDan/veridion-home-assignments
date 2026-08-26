"""Batch 2 (Tier 2) validation: DEFRA "spending over £25,000" full validation.

Extends the single-example DEFRA row already in FINDINGS.md into a real,
multi-month hit-rate / blank-rate / false-positive measurement. This is the
only one of 9 departments surveyed (see inspect_batch2_sources.py) whose
monthly spend CSV carries a VAT column at all -- DWP, HM Treasury, HMRC, DBT,
Cabinet Office, MHCLG, DfT, and DHSC do not.

Usage:
    py -3.14 validate_defra.py inspect            # column headers, sample CSV headers
    py -3.14 validate_defra.py scan [n_months]    # blank-rate across n_months files
    py -3.14 validate_defra.py join [n_months]    # scan + join to sample + HMRC/checksum
"""

from __future__ import annotations

import sys

import pandas as pd

import gov_uk_utils
from csv_utils import get_header, load_columns
from hmrc_vat_check import check_vat_number, get_access_token, is_valid_uk_vat_checksum, normalize_vat_number

DEFRA_COLLECTION = "/government/collections/defra-departmental-spending-over-25000"
SAMPLE_CSV = "../BasicCompanyData-2026-08-01-part1_7.csv"

SUPPLIER_COL = "Supplier "
VAT_COL = "Vat Registration Num"
POSTCODE_SOURCE_COL = "Supplier Postcode"


def get_defra_month_urls(n_months: int) -> list[tuple[str, str]]:
    """Return (publication_path, csv_url) for the n_months most recent DEFRA publications."""
    collection = gov_uk_utils.fetch_content(DEFRA_COLLECTION)
    doc_paths = gov_uk_utils.get_collection_document_paths(collection)
    results = []
    for path in doc_paths[:n_months]:
        publication = gov_uk_utils.fetch_content(path)
        csv_urls = gov_uk_utils.get_csv_attachment_urls(publication)
        if csv_urls:
            results.append((path, csv_urls[0][1]))
    return results


def read_spend_csv(url: str) -> pd.DataFrame:
    """Read a gov.uk spend CSV, trying utf-8 first and falling back to cp1252
    (these transparency exports mix encodings; DEFRA's files have shown mangled
    £ signs under a naive utf-8 decode).
    """
    try:
        return pd.read_csv(url, dtype="string", encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(url, dtype="string", encoding="cp1252")


def normalize_name(name: str) -> str:
    return "".join(name.upper().split())


def inspect() -> None:
    print("Sample CSV header:", get_header(SAMPLE_CSV))
    urls = get_defra_month_urls(1)
    path, csv_url = urls[0]
    print(f"\nLatest DEFRA publication: {path}\nCSV: {csv_url}")
    df = read_spend_csv(csv_url)
    print("DEFRA CSV header:", list(df.columns))
    print(f"Row count: {len(df)}")


def scan(n_months: int) -> None:
    month_urls = get_defra_month_urls(n_months)
    total_rows = 0
    total_populated = 0
    for path, csv_url in month_urls:
        df = read_spend_csv(csv_url)
        populated = df[VAT_COL].notna() & (df[VAT_COL].str.strip() != "")
        n_populated = int(populated.sum())
        total_rows += len(df)
        total_populated += n_populated
        print(f"{path}: {len(df)} rows, {n_populated} with populated {VAT_COL!r} ({n_populated / len(df):.1%})")
    print(f"\nTotal across {len(month_urls)} months: {total_rows} rows, {total_populated} populated "
          f"({total_populated / total_rows:.1%} population rate, {1 - total_populated / total_rows:.1%} blank rate)")


def load_sample_lookup() -> dict[str, tuple[str, str, str]]:
    """Build {normalized CompanyName: (CompanyNumber, original name, postcode)}."""
    df = load_columns(SAMPLE_CSV, ["CompanyName", " CompanyNumber", "RegAddress.PostCode"])
    lookup = {}
    for name, number, postcode in zip(df["CompanyName"], df[" CompanyNumber"], df["RegAddress.PostCode"]):
        key = normalize_name(name)
        postcode_str = postcode.strip() if pd.notna(postcode) else ""
        lookup[key] = (number.strip(), name, postcode_str)
    return lookup


def join(n_months: int) -> None:
    print("Loading sample CSV CompanyName lookup...")
    sample_lookup = load_sample_lookup()
    print(f"Sample lookup size: {len(sample_lookup)}")

    month_urls = get_defra_month_urls(n_months)
    total_rows = 0
    total_populated = 0
    matches = []

    for path, csv_url in month_urls:
        df = read_spend_csv(csv_url)
        total_rows += len(df)
        populated_mask = df[VAT_COL].notna() & (df[VAT_COL].str.strip() != "")
        total_populated += int(populated_mask.sum())
        populated_df = df[populated_mask]
        for supplier, vat_raw, postcode in zip(
            populated_df[SUPPLIER_COL], populated_df[VAT_COL], populated_df[POSTCODE_SOURCE_COL]
        ):
            sample_hit = sample_lookup.get(normalize_name(supplier))
            if sample_hit:
                source_postcode = postcode.strip() if pd.notna(postcode) else ""
                matches.append({
                    "month": path,
                    "supplier": supplier,
                    "vat_raw": vat_raw,
                    "source_postcode": source_postcode,
                    "sample_number": sample_hit[0],
                    "sample_name": sample_hit[1],
                    "sample_postcode": sample_hit[2],
                })

    print(f"\n{len(month_urls)} months, {total_rows} rows, {total_populated} with populated VAT "
          f"({total_populated / total_rows:.1%})")
    print(f"Matched to sample CSV by normalized Supplier/CompanyName: {len(matches)} rows "
          f"(some may repeat the same company across months)")

    if not matches:
        return

    token = get_access_token()
    n_checksum_valid = 0
    n_foreign_prefix = 0
    n_postcode_agrees = 0
    seen_vrns = set()
    non_uk_prefixes = ("LU", "DE", "FR", "NL", "IE", "IT", "ES", "BE", "DK", "SE", "AT", "PL")
    for m in matches:
        raw_upper = m["vat_raw"].strip().upper()
        is_foreign_prefixed = raw_upper.startswith(non_uk_prefixes)
        if is_foreign_prefixed:
            n_foreign_prefix += 1
        vrn = normalize_vat_number(m["vat_raw"])
        valid, style = is_valid_uk_vat_checksum(vrn)
        if valid:
            n_checksum_valid += 1
        postcode_agrees = bool(m["source_postcode"]) and m["source_postcode"] == m["sample_postcode"]
        if postcode_agrees:
            n_postcode_agrees += 1

        if vrn in seen_vrns:
            continue  # avoid redundant sandbox calls for the same company across months
        seen_vrns.add(vrn)

        sandbox = check_vat_number(vrn, token)
        print("\n---")
        print(f"Month:                {m['month']}")
        print(f"Sample CompanyNumber: {m['sample_number']}")
        print(f"Sample CompanyName:   {m['sample_name']}")
        print(f"DEFRA Supplier name:  {m['supplier']}")
        print(f"Source VAT (raw):     {m['vat_raw']}")
        print(f"Normalized VRN:       {vrn}")
        print(f"Checksum valid:       {valid} ({style})")
        print(f"Foreign-prefixed:     {is_foreign_prefixed}")
        print(f"Postcode agrees:      {postcode_agrees} (source={m['source_postcode']!r}, sample={m['sample_postcode']!r})")
        print(f"Sandbox response:     {sandbox}")

        if not valid and not is_foreign_prefixed:
            print("  ^^ FLAGGED: GB-context VRN that fails the checksum -- likely genuine false positive/data error")

    n_uk_context = len(matches) - n_foreign_prefix
    n_uk_checksum_invalid = len(matches) - n_checksum_valid - n_foreign_prefix
    print(f"\nTotal matched rows: {len(matches)} ({n_foreign_prefix} foreign-prefixed, e.g. AMAZON WEB SERVICES EMEA "
          f"SARL's LU VAT -- excluded from the UK false-positive rate since they are not claiming to be UK VAT numbers)")
    print(f"Checksum valid: {n_checksum_valid}/{len(matches)} matched rows overall")
    print(f"Of {n_uk_context} GB-context rows (foreign-prefixed excluded): "
          f"{n_uk_context - n_uk_checksum_invalid} valid, {n_uk_checksum_invalid} checksum-invalid "
          f"({n_uk_checksum_invalid / n_uk_context:.1%} measured false-positive rate)")
    print(f"Postcode agrees (disambiguation signal, NOT a false-positive indicator -- registered office often "
          f"differs from trading/invoicing address): {n_postcode_agrees}/{len(matches)} matched rows")
    print(f"Distinct VRNs sandbox-checked: {len(seen_vrns)}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if mode == "inspect":
        inspect()
    elif mode == "scan":
        n_months = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        scan(n_months)
    elif mode == "join":
        n_months = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        join(n_months)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
