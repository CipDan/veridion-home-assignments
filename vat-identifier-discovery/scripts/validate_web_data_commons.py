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
    py -3.14 validate_web_data_commons.py inspect            # download+preview domain_stats/lookup
    py -3.14 validate_web_data_commons.py survey             # global + UK vatID hit-rate
    py -3.14 validate_web_data_commons.py join [max_domains]  # survey + part-file extraction + sample join
"""

from __future__ import annotations

import os
import sys

import wdc_utils
from csv_utils import load_columns
from hmrc_vat_check import check_vat_number, get_access_token, is_valid_uk_vat_checksum, normalize_vat_number

SAMPLE_CSV = "../BasicCompanyData-2026-08-01-part1_7.csv"
COMPANY_NAME_COL = "CompanyName"
COMPANY_NUMBER_COL = " CompanyNumber"

DOMAIN_STATS_PATH = "Organization_domain_stats.csv"
LOOKUP_PATH = "Organization_lookup.csv"
CHECKPOINT_PATH = "wdc_join_checkpoint.json"


def normalize_name(name: str) -> str:
    return "".join(name.upper().split())


def ensure_file(path: str, url: str) -> str:
    if not os.path.exists(path):
        print(f"Downloading {url} -> {path} (large, may take a while)...")
        wdc_utils.download_file(url, path)
    return path


def inspect() -> None:
    domain_stats_path = ensure_file(DOMAIN_STATS_PATH, wdc_utils.DOMAIN_STATS_URL)
    rows = list(wdc_utils.iter_domain_stats(domain_stats_path))
    print(f"Organization_domain_stats.csv: {len(rows)} domains")
    for domain, n_quads, n_entities, properties in rows[:5]:
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
    df = load_columns(SAMPLE_CSV, [COMPANY_NAME_COL, COMPANY_NUMBER_COL])
    lookup: dict[str, list[tuple[str, str]]] = {}
    for name, number in zip(df[COMPANY_NAME_COL], df[COMPANY_NUMBER_COL]):
        lookup.setdefault(normalize_name(name), []).append((number.strip(), name))
    return lookup


def join(max_domains: int | None) -> None:
    uk_domains_with_vatid = survey()
    if not uk_domains_with_vatid:
        print("\nNo .uk domains carry a populated vatID -- nothing to extract or join.")
        return

    target_domains = set(uk_domains_with_vatid[:max_domains] if max_domains else uk_domains_with_vatid)
    print(f"\nLooking up which part file(s) hold {len(target_domains)} target domain(s)...")
    lookup_path = ensure_file(LOOKUP_PATH, wdc_utils.LOOKUP_URL)
    file_lookup = wdc_utils.load_file_lookup(lookup_path, target_domains)
    needed_parts = sorted(set(file_lookup.values()))
    print(f"Part files needed: {len(needed_parts)} distinct file(s) for {len(target_domains)} domain(s) "
          f"-- each is downloaded, scanned, checkpointed, then deleted, so at most one sits on disk at a time")

    processed_parts, entities = wdc_utils.load_checkpoint(CHECKPOINT_PATH, target_domains)
    remaining_parts = [p for p in needed_parts if p not in processed_parts]
    if processed_parts:
        print(f"Resuming from checkpoint: {len(processed_parts)} part file(s) already done, "
              f"{len(remaining_parts)} remaining, {len(entities)} entities extracted so far")

    for part_name in remaining_parts:
        part_path = part_name
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
    for subject, entity in entities_with_vatid.items():
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

    token = get_access_token()
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

        sandbox = check_vat_number(vrn, token)
        print(f"Sandbox response:     {sandbox}")
        if not valid:
            print("  ^^ FLAGGED: checksum-invalid -- likely not a genuine UK VRN despite the vatID property name")

    print(f"\nChecksum valid: {n_checksum_valid}/{len(matches)} "
          f"({(len(matches) - n_checksum_valid) / len(matches):.1%} measured false-positive rate)")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if mode == "inspect":
        inspect()
    elif mode == "survey":
        survey()
    elif mode == "join":
        max_domains = int(sys.argv[2]) if len(sys.argv) > 2 else None
        join(max_domains)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
