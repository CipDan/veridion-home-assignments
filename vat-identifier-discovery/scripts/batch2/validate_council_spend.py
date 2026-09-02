"""Batch 2 (Tier 2) validation: local council "spend over £500" transparency data.

Resolves FINDINGS.md Open Question #6: does any council actually populate a
VAT column? Unlike DEFRA (one centrally-templated CSV format), ~350 councils
each publish independently with no shared schema, so there is no bulk-download
route the way there is for departmental spend -- this randomly samples
distinct councils via the data.gov.uk CKAN API and checks each one's most
recent live CSV resource for a VAT-like column, then joins/validates any hits
against the sample CSV exactly as the DEFRA and PEPPOL batches did.

Usage:
    py -3.14 validate_council_spend.py survey [n]   # sample n councils, report VAT column presence
    py -3.14 validate_council_spend.py join [n]      # survey + join/validate any VAT hits against the sample
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ckan_utils
from csv_utils import load_columns
from hmrc_vat_check import check_vat_number, get_access_token, is_valid_uk_vat_checksum, normalize_vat_number

QUERY = "council spend over 500"
SAMPLE_CSV = "../../BasicCompanyData-2026-08-01-part1_7.csv"
SEED = 26082026  # today's date, for a reproducible-but-arbitrary random sample


def read_council_csv(url: str) -> tuple[pd.DataFrame, int]:
    """Read a council CSV, returning (dataframe, malformed_rows_skipped) so
    callers can flag a result as incomplete instead of silently treating a
    partially-parsed file as fully validated.
    """
    skipped = 0

    def _count_bad_line(bad_line: list[str]) -> None:
        """pandas on_bad_lines callback: count a malformed row, then drop it (by returning None) instead of raising."""
        nonlocal skipped
        skipped += 1
        return None

    try:
        df = pd.read_csv(url, dtype="string", encoding="utf-8-sig", on_bad_lines=_count_bad_line, engine="python")
    except UnicodeDecodeError:
        skipped = 0  # discard any count from the aborted utf-8-sig attempt
        df = pd.read_csv(url, dtype="string", encoding="cp1252", on_bad_lines=_count_bad_line, engine="python")
    return df, skipped


def safe_print(text: str) -> None:
    """Print, replacing every non-ASCII character with '?' so the output is
    safe on any console codepage (some council CSVs have emoji/unusual
    unicode in column names or values); this is stricter than necessary on
    a codepage like cp1252 that could actually render some of those
    characters.
    """
    print(text.encode("ascii", errors="replace").decode("ascii"))


def looks_like_html(columns: list[str]) -> bool:
    """True if a 'CSV' resource actually served an HTML error/landing page."""
    return any(col.strip().lower().startswith("<!doctype") or col.strip().lower().startswith("<html") for col in columns)


VAT_REGISTRATION_KEYWORDS = ("vat registration", "vat number", "vrn")
VAT_NON_IDENTIFIER_KEYWORDS = ("status", "rate", "amount")


def find_vat_column(columns: list[str]) -> str | None:
    """Match only explicit VAT-registration-number columns, not any column that
    merely mentions VAT (e.g. 'Irrecoverable VAT (N)' is an accounting field,
    not a VRN column -- it would otherwise poison normalization/HMRC checks),
    nor a VAT-adjacent status/rate/amount field (e.g. 'VAT registration status',
    'VRN status') that isn't itself an identifier.
    """
    for col in columns:
        lowered = col.lower()
        if any(keyword in lowered for keyword in VAT_NON_IDENTIFIER_KEYWORDS):
            continue
        if any(keyword in lowered for keyword in VAT_REGISTRATION_KEYWORDS):
            return col
    return None


def find_column(columns: list[str], keywords: tuple[str, ...]) -> str | None:
    """Return the first column whose lowercased name contains any of keywords, or None if none match."""
    for col in columns:
        lowered = col.lower()
        if any(keyword in lowered for keyword in keywords):
            return col
    return None


def survey(n: int) -> list[dict]:
    """Sample n distinct councils from CKAN, fetch each one's most recent
    live CSV resource, and report whether it has a VAT-like column.

    Returns one dict per successfully-checked council: {council, url,
    vat_column, df, skipped_rows} -- used by join() to extract and
    validate any VAT hits without re-fetching.
    """
    total = ckan_utils.get_total_count(QUERY)
    print(f"Sampling up to {n} distinct council datasets from CKAN ('{QUERY}', {total} total datasets)...")
    packages = ckan_utils.random_sample_distinct_organizations(
        QUERY, n=n, seed=SEED, organization_filter=ckan_utils.is_local_council
    )
    print(f"Distinct councils sampled: {len(packages)}\n")

    n_no_csv = 0
    n_fetch_failed = 0
    n_html_not_csv = 0
    n_with_vat_column = 0
    n_with_skipped_rows = 0
    results = []
    for pkg in packages:
        council_name = pkg.get("organization", {}).get("title", "?")
        resource = ckan_utils.get_best_csv_resource(pkg)
        if resource is None:
            safe_print(f"{council_name}: no live CSV resource found")
            n_no_csv += 1
            continue
        name, url = resource
        if not url.lower().startswith("https://"):
            safe_print(f"{council_name}: resource URL is not HTTPS ({url!r}) -- skipping for transport security")
            n_no_csv += 1
            continue
        try:
            df, n_skipped_rows = read_council_csv(url)
        except Exception as exc:
            safe_print(f"{council_name}: fetch/parse failed ({type(exc).__name__}: {exc})")
            n_fetch_failed += 1
            continue
        if looks_like_html(list(df.columns)):
            safe_print(f"{council_name}: resource URL served an HTML page, not a real CSV (dead/broken link)")
            n_html_not_csv += 1
            continue
        vat_col = find_vat_column(list(df.columns))
        if vat_col is not None:
            n_with_vat_column += 1
        if n_skipped_rows:
            n_with_skipped_rows += 1
        skip_note = f", {n_skipped_rows} malformed row(s) skipped -- result may be incomplete" if n_skipped_rows else ""
        safe_print(f"{council_name}: resource={name!r} rows={len(df)}{skip_note} VAT column={vat_col!r} | columns={list(df.columns)}")
        results.append({
            "council": council_name, "url": url, "vat_column": vat_col, "df": df, "skipped_rows": n_skipped_rows,
        })

    n_checked = len(packages) - n_no_csv - n_fetch_failed - n_html_not_csv
    print(f"\n{len(packages)} distinct councils sampled: {n_no_csv} with no live CSV resource, "
          f"{n_fetch_failed} fetch/parse failures, {n_html_not_csv} broken links serving HTML instead of CSV, "
          f"{n_checked} successfully checked")
    if n_with_skipped_rows:
        print(f"Warning: {n_with_skipped_rows} of {n_checked} checked council CSV(s) had malformed rows skipped "
              f"while parsing -- those results are incomplete, not fully validated")
    if n_checked:
        print(f"Of the {n_checked} checked, {n_with_vat_column} have a VAT-like column "
              f"({n_with_vat_column / n_checked:.1%})")
    return results


def load_sample_lookup() -> dict[str, tuple[str, str]]:
    """Build {normalized CompanyName: (CompanyNumber, original name)}."""
    df = load_columns(SAMPLE_CSV, ["CompanyName", " CompanyNumber"])
    return {
        "".join(name.upper().split()): (number.strip(), name)
        for name, number in zip(df["CompanyName"], df[" CompanyNumber"])
    }


def join(n: int) -> None:
    """Survey n councils, then for each one with a VAT column extract
    populated (supplier, VAT) pairs, join them to the sample CSV by
    normalized supplier name, and print each match's normalized VRN.

    A GB/XI-context value also gets its checksum validity and an HMRC
    sandbox lookup; a GD/HA (government/health authority) or other
    non-GB-prefixed value prints "N/A" instead, since neither the checksum
    nor the sandbox applies to it.
    """
    results = survey(n)
    hits = [r for r in results if r["vat_column"] is not None]
    if not hits:
        print("\nNo sampled council carried a VAT column -- nothing to join or validate.")
        return

    print(f"\n{len(hits)} council(s) with a VAT column found -- extracting and joining to sample CSV.")
    sample_lookup = load_sample_lookup()
    token: str | None = None  # acquired lazily -- only if a value actually needs the HMRC sandbox

    # Same classification as validate_defra.py's join(): any non-GB/XI prefixed
    # value isn't a UK VAT number at all (skip checksum/sandbox), and GD/HA-
    # prefixed values use HMRC's separate non-checksummed government/health-
    # authority numbering scheme, so is_valid_uk_vat_checksum would always
    # misreport them as invalid.
    uk_prefixes = ("GB", "XI")
    unsupported_uk_prefixes = ("GD", "HA")

    for hit in hits:
        df = hit["df"]
        vat_col = hit["vat_column"]
        supplier_col = find_column(list(df.columns), ("supplier", "payee", "vendor", "creditor"))
        if supplier_col is None:
            print(f"\n{hit['council']}: has a VAT column ({vat_col!r}) but no recognizable supplier-name "
                  f"column among {list(df.columns)} -- cannot join to sample, skipping.")
            continue

        if hit.get("skipped_rows"):
            print(f"\n{hit['council']}: warning -- {hit['skipped_rows']} malformed row(s) were skipped while "
                  f"parsing this CSV; join results below may be incomplete.")

        populated = df[
            df[vat_col].notna() & (df[vat_col].str.strip() != "")
            & df[supplier_col].notna() & (df[supplier_col].str.strip() != "")
        ]
        print(f"\n{hit['council']}: {len(df)} rows, {len(populated)} with populated {vat_col!r}")

        for supplier, vat_raw in zip(populated[supplier_col], populated[vat_col]):
            key = "".join(supplier.upper().split())
            sample_hit = sample_lookup.get(key)
            if not sample_hit:
                continue
            raw_upper = vat_raw.strip().upper()
            vrn = normalize_vat_number(vat_raw)
            print("\n---")
            print(f"Council:              {hit['council']}")
            print(f"Sample CompanyNumber: {sample_hit[0]}")
            print(f"Sample CompanyName:   {sample_hit[1]}")
            print(f"Source Supplier name: {supplier}")
            print(f"Source VAT (raw):     {vat_raw}")
            print(f"Normalized VRN:       {vrn}")

            if raw_upper.startswith(unsupported_uk_prefixes):
                print("Checksum valid:       N/A -- unsupported GD/HA non-checksummed format (HMRC sandbox not called)")
                continue
            prefix = raw_upper[:2]
            if prefix.isalpha() and prefix not in uk_prefixes:
                print("Checksum valid:       N/A -- non-GB prefixed, not a UK VAT number (HMRC sandbox not called)")
                continue

            valid, style = is_valid_uk_vat_checksum(vrn)
            if token is None:
                token = get_access_token()
            sandbox = check_vat_number(vrn, token)
            print(f"Checksum valid:       {valid} ({style})")
            print(f"Sandbox response:     {sandbox}")


def main() -> None:
    """CLI entry point: dispatch to survey/join based on sys.argv (see
    module docstring for usage).
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "survey"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    if mode == "survey":
        survey(n)
    elif mode == "join":
        join(n)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
