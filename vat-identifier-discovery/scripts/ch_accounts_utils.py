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
import os
import re
import tempfile
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
# the value itself -- any run of "is", "was", "of", "no"/"no.", ":", "-" (in
# any combination and order, e.g. "number is:" or "number no."), or nothing
# -- then a 9-digit number (optionally GB/XI-prefixed, and optionally
# grouped with whitespace between digits, e.g. "GB 553 5578 81") with an
# optional 3-digit branch/group suffix for 12-digit VRNs. normalize_vat_number()
# strips all whitespace and any GB/XI prefix, so a grouped raw match still
# normalizes correctly. The trailing (?!\s?\d) stops a longer digit run
# (e.g. a 10+ digit number, possibly with a space before the extra digit)
# from being partially captured as a 9- or 12-digit match.
VAT_MENTION_RE = re.compile(
    r"VAT\s*(?:REGISTRATION|REG\.?|NUMBER|NO)\.?\s*(?:NUMBER|NO\.?)?\s*(?:(?:IS|WAS|OF|NO\.?|:|-)\s*)*"
    r"((?:GB|XI)\s?\d(?:\s?\d){8}(?:\s?\d{3})?|\d(?:\s?\d){8}(?:\s?\d{3})?)(?!\s?\d)",
    re.IGNORECASE,
)

# Bare word-boundary match on "VAT" -- used only to distinguish "the topic
# never comes up in these filings" from "it comes up, but not in a format
# VAT_MENTION_RE recognises" when the mention hit-rate turns out to be zero.
_VAT_WORD_RE = re.compile(r"\bVAT\b", re.IGNORECASE)


def contains_vat_word(text: str) -> bool:
    """Return True if the bare word "VAT" appears anywhere in text."""
    return _VAT_WORD_RE.search(text) is not None

def find_vat_word_contexts(text: str, context_chars: int = 80) -> list[str]:
    """Return the surrounding-text window around every bare "VAT" occurrence,
    for manually reading what a filing actually says when it mentions VAT but
    VAT_MENTION_RE found no registration-number-style match -- the check
    needed to tell "no VRN disclosed" apart from "disclosed in a format the
    pattern doesn't recognise".
    """
    contexts = []
    for match in _VAT_WORD_RE.finditer(text):
        start = max(0, match.start() - context_chars)
        end = min(len(text), match.end() + context_chars)
        contexts.append(text[start:end])
    return contexts


def download_daily_zip(date: str, dest_path: str) -> None:
    """Download one day's bulk accounts ZIP (date format YYYY-MM-DD).

    Streams into a temp file in the same directory and atomically renames it
    into place only once the download completes successfully -- so a crash
    or interruption partway through can't leave a partial ZIP that
    ensure_zip() would mistake for a complete, already-downloaded one.
    """
    url = DAILY_URL_TEMPLATE.format(date=date)
    dest_dir = os.path.dirname(dest_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dest_dir)
    try:
        with os.fdopen(fd, "wb") as f, requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        os.replace(tmp_path, dest_path)
    except BaseException:
        os.remove(tmp_path)
        raise


def iter_company_numbers_in_zip(zip_path: str) -> Iterator[tuple[str, str]]:
    """Yield (CompanyNumber, member_filename) for every filing in the ZIP,
    parsed from the filename -- no need to read file contents for this.
    """
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            match = _FILENAME_RE.match(name)
            if match:
                yield match.group(1), name


def read_member_text(zf: zipfile.ZipFile, member_name: str) -> str:
    """Read one filing's HTML out of an already-open ZIP (so callers scanning
    many members can open the archive once instead of once per member) and
    reduce it to plain text for regex scanning.
    """
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
    from hmrc_vat_check import is_valid_uk_vat_checksum, normalize_vat_number

    samples = [
        "The company's VAT registration number is GB123456789.",
        "VAT Reg No: 123456789",
        "VAT number GB 123456789 is shown on all invoices.",
        "Input VAT of 123456789 was reclaimed in the period.",  # should NOT match (no reg/no/number phrasing)
        "VAT registration number is GB553557881001.",  # 12-digit VRN (9-digit + branch/group suffix)
        "VAT Reg No: 553557881 001",  # 12-digit VRN with a space before the suffix
        "VAT number 5535578810012 has too many digits.",  # should NOT match (13-digit run, no valid boundary)
        "VAT registration number: XI553557881.",  # XI prefix
        "VAT registration number: GB 553 5578 81.",  # grouped digits, no branch suffix
        "VAT Reg No: 553557881 0012",  # should NOT match (9 digits + a 4-digit run, no valid 9/12-digit boundary)
        "VAT registration number is: 123456789.",  # sequential "is" + ":" connector tokens
        "VAT registration number no. 123456789.",  # "no." connector after the "number" label
    ]
    for s in samples:
        print(f"{s!r} -> {find_vat_mentions(s)}")

    print("\n--- 12-digit VRN extraction stays intact through normalize/checksum ---")
    for s in ("VAT registration number is GB553557881001.", "VAT Reg No: 553557881 001"):
        hits = find_vat_mentions(s)
        assert len(hits) == 1, f"expected exactly one match for {s!r}, got {hits}"
        raw = hits[0]["raw"]
        vrn = normalize_vat_number(raw)
        assert vrn == "553557881001", f"normalize_vat_number({raw!r}) -> {vrn!r}, expected '553557881001'"
        valid, style = is_valid_uk_vat_checksum(vrn)
        print(f"{s!r} -> raw={raw!r} vrn={vrn!r} valid={valid} style={style}")

    print("\n--- XI prefix and grouped digits normalize the same as an ungrouped GB match ---")
    for s in ("VAT registration number: XI553557881.", "VAT registration number: GB 553 5578 81."):
        hits = find_vat_mentions(s)
        assert len(hits) == 1, f"expected exactly one match for {s!r}, got {hits}"
        raw = hits[0]["raw"]
        vrn = normalize_vat_number(raw)
        assert vrn == "553557881", f"normalize_vat_number({raw!r}) -> {vrn!r}, expected '553557881'"
        print(f"{s!r} -> raw={raw!r} vrn={vrn!r}")

    no_match = find_vat_mentions("VAT Reg No: 553557881 0012")
    assert no_match == [], f"expected no match for a 9-digit run followed by a stray 4-digit run, got {no_match}"
