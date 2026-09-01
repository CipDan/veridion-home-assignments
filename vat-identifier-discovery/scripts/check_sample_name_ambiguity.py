"""One-off audit check for a specific, verifiable docstring claim:
validate_peppol.py's load_sample_name_lookup() docstring states that a
normalized CompanyName maps to more than one CompanyNumber in "631 cases as
of the 2026-08-01 snapshot". This script re-derives that count from the
current sample CSV to confirm whether the docstring's figure still holds.

Usage:
    py -3.14 check_sample_name_ambiguity.py
"""

from __future__ import annotations

from csv_utils import load_columns

SAMPLE_CSV = "../BasicCompanyData-2026-08-01-part1_7.csv"
COMPANY_NAME_COL = "CompanyName"
COMPANY_NUMBER_COL = " CompanyNumber"


def normalize_name(name: str) -> str:
    """Uppercase and strip all whitespace, matching validate_peppol.py's own normalize_name()."""
    return "".join(name.upper().split())


def build_name_lookup() -> tuple[dict[str, list[tuple[str, str]]], int]:
    """Build {normalized CompanyName: [(CompanyNumber, original name), ...]} from the sample CSV, plus its row count."""
    df = load_columns(SAMPLE_CSV, [COMPANY_NAME_COL, COMPANY_NUMBER_COL])
    lookup: dict[str, list[tuple[str, str]]] = {}
    for name, number in zip(df[COMPANY_NAME_COL], df[COMPANY_NUMBER_COL]):
        lookup.setdefault(normalize_name(name), []).append((number.strip(), name))
    return lookup, len(df)


def count_ambiguous_names(lookup: dict[str, list[tuple[str, str]]]) -> int:
    """Count normalized names that map to more than one distinct CompanyNumber."""
    return sum(1 for candidates in lookup.values() if len(candidates) > 1)


if __name__ == "__main__":
    lookup, n_rows = build_name_lookup()
    print(f"Total sample rows: {n_rows}")
    print(f"Distinct normalized CompanyName values: {len(lookup)}")
    print(f"Normalized names mapping to >1 CompanyNumber: {count_ambiguous_names(lookup)}")
