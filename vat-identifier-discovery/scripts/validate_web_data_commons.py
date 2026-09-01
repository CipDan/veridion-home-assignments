"""Batch 3 (Tier 3) validation: Web Data Commons schema.org Organization
extract from Common Crawl.

Resolves FINDINGS.md Open Question #3: what fraction of Organization
entities -- especially UK ones -- have a populated schema.org vatID
property? Organization_domain_stats.csv (one row per domain, with a
{property: density} dict) makes this answerable without downloading the
full 488GB N-Quads corpus: survey() scans it directly for vatID presence.

join() then locates which part_N.gz file(s) hold the UK domains that do
carry vatID (via Organization_lookup.csv), downloads only those, and pulls
out the actual vatID/name values to match against the sample CSV by
CompanyName -- there is no Companies House number in this data, so (like
PEPPOL) this is a fuzzy name join, not an exact-key one.

Usage:
    py -3.14 validate_web_data_commons.py inspect            # download+preview domain_stats
    py -3.14 validate_web_data_commons.py survey             # global + UK vatID hit-rate
    py -3.14 validate_web_data_commons.py join [max_domains]  # survey + part-file extraction + sample join
"""

from __future__ import annotations

import os
import re
import sys

import wdc_utils
from csv_utils import load_columns
from hmrc_vat_check import check_vat_number, get_access_token, is_valid_uk_vat_checksum, normalize_vat_number

SAMPLE_CSV = "../BasicCompanyData-2026-08-01-part1_7.csv"
COMPANY_NAME_COL = "CompanyName"
COMPANY_NUMBER_COL = " CompanyNumber"

# Cached/downloaded artifacts are resolved relative to this script's own
# directory (not the process's current working directory) so they always
# land in vat-identifier-discovery/scripts/ -- where the .gitignore patterns
# for *.gz/Organization_*.csv/*_checkpoint.json expect them -- even when the
# script is invoked from the repository root or elsewhere.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DOMAIN_STATS_PATH = os.path.join(SCRIPT_DIR, "Organization_domain_stats.csv")
LOOKUP_PATH = os.path.join(SCRIPT_DIR, "Organization_lookup.csv")
CHECKPOINT_PATH = os.path.join(SCRIPT_DIR, "wdc_join_checkpoint.json")

# WDC part files are always named "part_<number>.gz" (see wdc_utils module
# docstring). file_lookup values come from a downloaded CSV and are used
# directly as local file paths (download destination, then os.remove) --
# enforcing this exact shape before any path operation rejects traversal
# ("../x") or other malformed names rather than acting on them.
PART_NAME_RE = re.compile(r"part_\d+\.gz")

# vatID is free-form scraped text -- normalize_vat_number() keeps "digits
# only" from whatever it's given, so unrelated digit fragments scattered
# through garbage text (e.g. "Company Reg No 12345678, VAT: XYZZY999000111")
# would otherwise be silently concatenated into a fake-looking VRN. Require
# the raw value to already be just an optional GB/XI prefix plus digits/
# whitespace before normalizing, catching that upstream.
RAW_VATID_RE = re.compile(r"(?:GB|XI)?[\d\s]+")


def _part_local_path(part_name: str) -> str:
    """Resolve a bare 'part_<number>.gz' name (as stored in the checkpoint
    and returned by load_file_lookup()) to its local download path under
    SCRIPT_DIR, so every on-disk check/download/removal of a part file
    agrees on the same location regardless of the process's cwd.
    """
    return os.path.join(SCRIPT_DIR, part_name)


def normalize_name(name: str) -> str:
    """Uppercase and strip all whitespace, so minor formatting differences
    between WDC's scraped entity names and the sample CSV's CompanyName
    don't block a match.
    """
    return "".join(name.upper().split())


def ensure_file(path: str, url: str) -> str:
    """Return the local path to url's downloaded file, downloading it
    first if it isn't already cached on disk.
    """
    if not os.path.exists(path):
        print(f"Downloading {url} -> {path} (large, may take a while)...")
        wdc_utils.download_file(url, path)
    return path


def inspect() -> None:
    """Download (if needed) and preview Organization_domain_stats.csv:
    total domain count plus the first 5 rows' quad/entity counts and
    property densities, as a quick eyeball check before survey()/join().
    """
    domain_stats_path = ensure_file(DOMAIN_STATS_PATH, wdc_utils.DOMAIN_STATS_URL)
    n_domains = 0
    preview_rows: list[tuple[str, int, int, dict[str, float]]] = []
    for domain, n_quads, n_entities, properties in wdc_utils.iter_domain_stats(domain_stats_path):
        n_domains += 1
        if len(preview_rows) < 5:
            preview_rows.append((domain, n_quads, n_entities, properties))
    print(f"Organization_domain_stats.csv: {n_domains} domains")
    for domain, n_quads, n_entities, properties in preview_rows:
        print(f"  {domain}: {n_quads} quads, {n_entities} entities, properties={properties}")


def survey() -> list[str]:
    """Scan domain_stats.csv for vatID presence, globally and among .uk
    domains. Returns the list of UK domains whose properties dict includes
    'vatID', for join() to extract from the part files.
    """
    domain_stats_path = ensure_file(DOMAIN_STATS_PATH, wdc_utils.DOMAIN_STATS_URL)

    n_domains = 0
    n_domains_with_vatid = 0
    n_uk_domains = 0
    uk_domains_with_vatid = []

    for domain, _n_quads, _n_entities, properties in wdc_utils.iter_domain_stats(domain_stats_path):
        n_domains += 1
        has_vatid = "vatID" in properties
        if has_vatid:
            n_domains_with_vatid += 1
        if wdc_utils.is_uk_domain(domain):
            n_uk_domains += 1
            if has_vatid:
                uk_domains_with_vatid.append(domain)

    if n_domains == 0:
        print("No domains found in domain_stats.csv -- nothing to survey.")
        return uk_domains_with_vatid

    print(f"Total domains surveyed: {n_domains}")
    print(f"Domains with vatID populated (any density > 0): {n_domains_with_vatid} "
          f"({n_domains_with_vatid / n_domains:.3%})")
    print(f"Of those, .uk domains: {n_uk_domains} total, {len(uk_domains_with_vatid)} with vatID "
          f"({len(uk_domains_with_vatid) / n_uk_domains:.3%} of .uk domains)" if n_uk_domains else
          f"Of those, .uk domains: {n_uk_domains} total")
    print(f"\n.uk domains with vatID populated ({len(uk_domains_with_vatid)}):")
    for domain in uk_domains_with_vatid:
        print(f"  {domain}")

    return uk_domains_with_vatid


def load_sample_name_lookup() -> dict[str, list[tuple[str, str]]]:
    """Build {normalized CompanyName: [(CompanyNumber, original name), ...]}.

    A normalized name can map to more than one CompanyNumber in the sample
    (distinct companies that happen to share a name) -- keeping every
    candidate lets join() tell an unambiguous match from an ambiguous one.
    """
    df = load_columns(os.path.join(SCRIPT_DIR, SAMPLE_CSV), [COMPANY_NAME_COL, COMPANY_NUMBER_COL])
    lookup: dict[str, list[tuple[str, str]]] = {}
    for name, number in zip(df[COMPANY_NAME_COL], df[COMPANY_NUMBER_COL], strict=True):
        lookup.setdefault(normalize_name(name), []).append((number.strip(), name))
    return lookup


def join(max_domains: int | None) -> None:
    """Survey which .uk domains carry a populated vatID, download and scan
    only the part file(s) that hold them (checkpointing progress and
    deleting each part file once scanned), then join the extracted
    name/vatID pairs to the sample CSV by normalized CompanyName and print
    each unambiguous match's checksum validity -- plus an HMRC sandbox
    lookup when the normalized VRN is a structurally valid 9 or 12 digits
    (otherwise sandbox is reported as skipped).

    max_domains caps how many surveyed UK domains are processed (None for
    no limit) -- useful for a quick partial run before committing to the
    full extraction.
    """
    if max_domains is not None and max_domains <= 0:
        print(f"Invalid max_domains: {max_domains} (must be a positive integer, or omitted for no limit)")
        return

    uk_domains_with_vatid = survey()
    if not uk_domains_with_vatid:
        print("\nNo .uk domains carry a populated vatID -- nothing to extract or join.")
        return

    target_domains = set(uk_domains_with_vatid[:max_domains] if max_domains else uk_domains_with_vatid)
    print(f"\nLooking up which part file(s) hold {len(target_domains)} target domain(s)...")
    lookup_path = ensure_file(LOOKUP_PATH, wdc_utils.LOOKUP_URL)
    file_lookup = wdc_utils.load_file_lookup(lookup_path, target_domains)
    missing_domains = target_domains - file_lookup.keys()
    if missing_domains:
        print(f"ERROR: {len(missing_domains)} target domain(s) have no entry in {LOOKUP_PATH}, "
              f"cannot locate their part file(s): {', '.join(sorted(missing_domains))}")
        return

    needed_parts = sorted(set(file_lookup.values()))
    invalid_parts = [p for p in needed_parts if not PART_NAME_RE.fullmatch(p)]
    if invalid_parts:
        print(f"ERROR: {len(invalid_parts)} part file name(s) from {LOOKUP_PATH} don't match the expected "
              f"'part_<number>.gz' format, refusing to use them as local paths: {', '.join(invalid_parts)}")
        return
    print(f"Part files needed: {len(needed_parts)} distinct file(s) for {len(target_domains)} domain(s) "
          f"-- each is downloaded, scanned, checkpointed, then deleted immediately after, keeping disk usage "
          f"flat outside of an interrupted run")

    processed_parts, entities, checkpoint_note = wdc_utils.load_checkpoint(CHECKPOINT_PATH, target_domains)
    if checkpoint_note:
        print(checkpoint_note)

    # Checkpoint entries are locally written by this script, but only ever
    # accept ones that fall within the current, already-validated part-file
    # set -- a stray or stale entry (e.g. from a hand-edited or corrupted
    # checkpoint file) shouldn't reach the os.path.exists()/os.remove() calls
    # below.
    needed_parts_set = set(needed_parts)
    stale_processed = processed_parts - needed_parts_set
    if stale_processed:
        print(f"Ignoring {len(stale_processed)} checkpoint entry/entries outside the current validated "
              f"part-file set: {', '.join(sorted(stale_processed))}")
        processed_parts &= needed_parts_set

    # A crash between save_checkpoint() and os.remove() below can leave a
    # part file on disk that's already marked processed -- since remaining_parts
    # skips anything in processed_parts, that leftover would never be revisited
    # or cleaned up otherwise, silently breaking the "at most one part file on
    # disk at a time" invariant.
    leftover_parts = [p for p in processed_parts if os.path.exists(_part_local_path(p))]
    for part_name in leftover_parts:
        os.remove(_part_local_path(part_name))
    if leftover_parts:
        print(f"Removed {len(leftover_parts)} already-processed part file(s) left over from an "
              f"interrupted run: {', '.join(leftover_parts)}")

    remaining_parts = [p for p in needed_parts if p not in processed_parts]
    if processed_parts:
        print(f"Resuming from checkpoint: {len(processed_parts)} part file(s) already done, "
              f"{len(remaining_parts)} remaining, {len(entities)} entities extracted so far")

    for part_name in remaining_parts:
        part_path = _part_local_path(part_name)
        if not os.path.exists(part_path):
            part_url = f"{wdc_utils.BASE_URL}/{part_name}"
            print(f"Downloading {part_url} -> {part_path} (~150-300MB, may take a while)...")
            wdc_utils.download_file(part_url, part_path)
        domains_in_this_part = {d for d, f in file_lookup.items() if f == part_name}
        print(f"Scanning {part_path} for {len(domains_in_this_part)} target domain(s)...")
        entities.update(wdc_utils.extract_entities_for_domains(part_path, domains_in_this_part))

        processed_parts.add(part_name)
        wdc_utils.save_checkpoint(CHECKPOINT_PATH, target_domains, processed_parts, entities)
        os.remove(part_path)
        print(f"Checkpointed ({len(processed_parts)}/{len(needed_parts)} parts done, "
              f"{len(entities)} entities so far) and removed {part_path}")

    entities_with_vatid = {k: v for k, v in entities.items() if v.get("vatID")}
    print(f"\nEntities extracted with a populated vatID: {len(entities_with_vatid)}")
    for subject, entity in list(entities_with_vatid.items())[:20]:
        print(f"  {subject}: name={entity.get('name')!r} vatID={entity.get('vatID')!r} domain={entity['domain']}")

    print("\nLoading sample CSV CompanyName lookup...")
    sample_lookup = load_sample_name_lookup()
    print(f"Sample lookup size: {len(sample_lookup)}")

    matches = []
    ambiguous = []
    for _subject, entity in entities_with_vatid.items():
        name = entity.get("name")
        if not name:
            continue
        candidates = sample_lookup.get(normalize_name(name))
        if not candidates:
            continue
        if len(candidates) > 1:
            ambiguous.append({"wdc_name": name, "vatid_raw": entity["vatID"], "candidates": candidates})
        else:
            sample_number, sample_name = candidates[0]
            matches.append({
                "wdc_name": name,
                "vatid_raw": entity["vatID"],
                "domain": entity["domain"],
                "sample_number": sample_number,
                "sample_name": sample_name,
            })

    print(f"\nMatched to sample CSV by normalized CompanyName (unambiguous): {len(matches)} raw match(es)")
    print(f"Ambiguous matches (name maps to >1 CompanyNumber, skipped): {len(ambiguous)}")

    # normalize_vat_number() only strips a GB/XI prefix -- a vatID carrying
    # some other country's prefix (e.g. "DE123456789") would otherwise have
    # just its letters stripped and be treated as if it were a UK VRN.
    # Inspect each raw value's two-letter prefix before normalizing, and
    # keep only unprefixed values (assumed UK, consistent with existing
    # behaviour) and GB/XI-prefixed ones out of dedup/counting as UK VRNs.
    uk_prefixes = ("GB", "XI")
    non_uk_matches = []
    uk_context_matches = []
    for m in matches:
        prefix = m["vatid_raw"].strip().upper()[:2]
        if prefix.isalpha() and prefix not in uk_prefixes:
            non_uk_matches.append(m)
        else:
            uk_context_matches.append(m)
    matches = uk_context_matches
    if non_uk_matches:
        print(f"\nExcluded {len(non_uk_matches)} match(es) with a non-GB/XI country-prefixed vatID "
              f"(not UK VRNs, reported separately):")
        for m in non_uk_matches:
            print(f"  {m['sample_number']} ({m['sample_name']}): vatID={m['vatid_raw']!r}")

    # vatID is free-form scraped text -- normalize_vat_number() keeps "digits
    # only" from whatever it's given, so a structurally garbage raw value must
    # be classified with RAW_VATID_RE *before* it ever reaches the canonical
    # normalization below. Classifying here (rather than only later, inside
    # the checksum loop) stops a malformed entry from being assigned a bogus
    # normalized vrn that could collide with, or be misreported as conflicting
    # with, a genuine valid VAT ID matched to the same company.
    raw_valid_matches = []
    raw_rejected_matches = []
    for m in matches:
        if RAW_VATID_RE.fullmatch(m["vatid_raw"].strip().upper()):
            raw_valid_matches.append(m)
        else:
            raw_rejected_matches.append(m)
    matches = raw_valid_matches
    if raw_rejected_matches:
        print(f"\nExcluded {len(raw_rejected_matches)} match(es) with a raw vatID that isn't just an optional "
              f"GB/XI prefix plus digits/whitespace (structurally not a VAT number, reported separately):")
        for m in raw_rejected_matches:
            print(f"  {m['sample_number']} ({m['sample_name']}): vatID={m['vatid_raw']!r}")

    # WDC can extract the same real-world organization many times over --
    # e.g. one domain repeating identical schema.org Organization markup on
    # every page, each occurrence getting its own RDF subject/blank-node id.
    # Collapse to one match per (sample CompanyNumber, vatID value) pair so
    # the reported hit-rate/false-positive rate reflects distinct findings,
    # not re-extraction noise, and so the sandbox isn't queried repeatedly
    # for an identical VRN.
    deduped_by_key: dict[tuple[str, str], dict] = {}
    vat_values_per_company: dict[str, set[str]] = {}
    for m in matches:
        vrn = normalize_vat_number(m["vatid_raw"])
        deduped_by_key.setdefault((m["sample_number"], vrn), m)
        vat_values_per_company.setdefault(m["sample_number"], set()).add(vrn)
    matches = list(deduped_by_key.values())
    print(f"Distinct (CompanyNumber, vatID) pairs after collapsing repeated extractions: {len(matches)}")

    conflicting = {num: vals for num, vals in vat_values_per_company.items() if len(vals) > 1}
    if conflicting:
        print(f"WARNING: {len(conflicting)} sample CompanyNumber(s) matched >1 DISTINCT vatID value across "
              f"different WDC entities -- a genuine conflict, not re-extraction noise:")
        for num, vals in conflicting.items():
            print(f"  {num}: {vals}")

    if not matches:
        return

    token: str | None = None
    n_checksum_valid = 0
    for m in matches:
        vrn = normalize_vat_number(m["vatid_raw"])
        valid, style = is_valid_uk_vat_checksum(vrn)
        if valid:
            n_checksum_valid += 1

        print("\n---")
        print(f"Sample CompanyNumber: {m['sample_number']}")
        print(f"Sample CompanyName:   {m['sample_name']}")
        print(f"WDC entity name:      {m['wdc_name']}")
        print(f"WDC domain:           {m['domain']}")
        print(f"vatID (raw):          {m['vatid_raw']}")
        print(f"Normalized VRN:       {vrn}")
        print(f"Checksum valid:       {valid} ({style})")

        # vatID is free-form scraped text (unlike ch_accounts' regex-constrained
        # matches), so it can be structurally garbage -- only spend a sandbox call,
        # and only obtain a token in the first place, on values check_vat_number's
        # own contract expects (9 or 12 digits).
        if vrn.isdigit() and len(vrn) in (9, 12):
            if token is None:
                token = get_access_token()
            sandbox = check_vat_number(vrn, token)
            print(f"Sandbox response:     {sandbox}")
        else:
            print("Sandbox response:     skipped -- not 9 or 12 digits, not a structurally valid UK VRN")
        if not valid:
            print("  ^^ FLAGGED: checksum-invalid -- likely not a genuine UK VRN despite the vatID property name")

    print(f"\nChecksum valid: {n_checksum_valid}/{len(matches)} "
          f"({(len(matches) - n_checksum_valid) / len(matches):.1%} checksum-invalid rate)")
    print("Note: this measures well-formedness only. The actual false-positive rate -- whether a "
          "checksum-valid vatID is genuinely registered to, and owned by, the matched company -- is "
          "unknown without authoritative HMRC/Companies House confirmation, which sandbox access cannot provide.")


def main() -> None:
    """CLI entry point: dispatch to inspect/survey/join based on sys.argv
    (see module docstring for usage).
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if mode == "inspect":
        inspect()
    elif mode == "survey":
        survey()
    elif mode == "join":
        try:
            max_domains = int(sys.argv[2]) if len(sys.argv) > 2 else None
        except ValueError:
            print(f"Invalid max_domains: {sys.argv[2]!r} (must be a positive integer, or omitted for no limit)")
            return
        join(max_domains)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
