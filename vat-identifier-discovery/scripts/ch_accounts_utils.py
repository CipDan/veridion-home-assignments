"""Helpers for Companies House bulk accounts data (daily iXBRL/HTML filings):
https://download.companieshouse.gov.uk/en_accountsdata.html

Each daily ZIP contains one file per filed account, named
"Prod223_4293_<CompanyNumber>_<MadeUpDate>.html" -- the same CompanyNumber
format (zero-padded 8 chars, or a 2-letter prefix like SC/NI/FC + 6 digits)
as the sample CSV's " CompanyNumber" column, so the join is an exact key
match, not a fuzzy name join like the other Tier 3 candidates.

These are full statutory accounts, not a VAT register -- a VAT number only
shows up if a company chose to disclose one somewhere in its notes (e.g. VAT
group membership, deferred VAT commentary). This module does a plain-text
regex scan for such disclosures, not XBRL-aware tag parsing: there is no
dedicated UK GAAP/FRS 102 taxonomy concept for "VAT registration number", so
a free-text search over the rendered document is the only way to find one.
"""

from __future__ import annotations

import html
import re
import zipfile
from collections.abc import Iterator

import requests

DAILY_URL_TEMPLATE = "https://download.companieshouse.gov.uk/Accounts_Bulk_Data-{date}.zip"

_FILENAME_RE = re.compile(r"^Prod\d+_\d+_([A-Za-z0-9]+)_(\d{8})\.html$")

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# Requires the word "VAT" directly followed by a registration/number-style
# keyword (mandatory -- this is what excludes an unrelated mention like
# "input VAT of 123456789"), then tolerates prose connecting the keyword to
# the value itself ("is", "was", "of", ":", "-", or nothing), then a 9-digit
# number, optionally GB-prefixed.
VAT_MENTION_RE = re.compile(
    r"VAT\s*(?:REGISTRATION|REG\.?|NUMBER|NO)\.?\s*(?:NUMBER|NO\.?)?\s*(?:IS|WAS|OF|:|-)?\s*(GB\s?\d{9}|\d{9})",
    re.IGNORECASE,
)

# Bare word-boundary match on "VAT" -- used only to distinguish "the topic
# never comes up in these filings" from "it comes up, but not in a format
# VAT_MENTION_RE recognises" when the mention hit-rate turns out to be zero.
_VAT_WORD_RE = re.compile(r"\bVAT\b", re.IGNORECASE)


def contains_vat_word(text: str) -> bool:
    return _VAT_WORD_RE.search(text) is not None


def download_daily_zip(date: str, dest_path: str) -> None:
    """Download one day's bulk accounts ZIP (date format YYYY-MM-DD)."""
    url = DAILY_URL_TEMPLATE.format(date=date)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)


def iter_company_numbers_in_zip(zip_path: str) -> Iterator[tuple[str, str]]:
    """Yield (CompanyNumber, member_filename) for every filing in the ZIP,
    parsed from the filename -- no need to read file contents for this.
    """
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            match = _FILENAME_RE.match(name)
            if match:
                yield match.group(1), name


def read_member_text(zip_path: str, member_name: str) -> str:
    """Read one filing's HTML out of the ZIP (without extracting the whole
    archive to disk) and reduce it to plain text for regex scanning.
    """
    with zipfile.ZipFile(zip_path) as zf:
        raw = zf.read(member_name).decode("utf-8", errors="replace")
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return _WHITESPACE_RE.sub(" ", text)


def find_vat_mentions(text: str, context_chars: int = 60) -> list[dict]:
    """Return every VAT_MENTION_RE match in text, with surrounding context
    for manual false-positive inspection.

    Each result: {"raw": matched digits/GB-prefixed value, "context": the
    surrounding text window}.
    """
    results = []
    for match in VAT_MENTION_RE.finditer(text):
        start = max(0, match.start() - context_chars)
        end = min(len(text), match.end() + context_chars)
        results.append({"raw": match.group(1), "context": text[start:end]})
    return results


if __name__ == "__main__":
    samples = [
        "The company's VAT registration number is GB123456789.",
        "VAT Reg No: 123456789",
        "VAT number GB 123456789 is shown on all invoices.",
        "Input VAT of 123456789 was reclaimed in the period.",  # should NOT match (no reg/no/number phrasing)
    ]
    for s in samples:
        print(f"{s!r} -> {find_vat_mentions(s)}")
