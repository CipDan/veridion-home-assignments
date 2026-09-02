"""One-off inspection driver for Batch 2 (Tier 2 full validation): confirms
gov_uk_utils and ckan_utils work against real endpoints before building the
full validation pipeline. Run with: py -3.14 inspect_batch2_sources.py
"""

import requests
import json
import gov_uk_utils
import ckan_utils

DEPARTMENT_COLLECTIONS = {
    "DEFRA": "/government/collections/defra-departmental-spending-over-25000",
    "DWP": "/government/collections/dwp-departmental-spending-over-25000",
    "HM Treasury": "/government/collections/hm-treasury-spend-over-25000",
    "HMRC": "/government/collections/hmrc-spending-over-25000",
}

BROADER_SURVEY_COLLECTIONS = {
    "DBT": "/government/collections/dbt-departmental-spending-over-25000",
    "Cabinet Office": "/government/collections/cabinet-office-spend-data",
    "MHCLG": "/government/collections/mhclg-departmental-spending-over-250",
    "DfT": "/government/collections/dft-departmental-spending-over-25000",
}

BROADER_SURVEY_PUBLICATIONS = {
    "DHSC": "/government/publications/dhsc-spending-over-25000-march-2026",
}


def inspect_departments() -> None:
    """Print each core department's publication count, then the CSV
    attachment URLs of its first two publications, as a smoke test of
    gov_uk_utils against real endpoints.
    """
    for dept_name, base_path in DEPARTMENT_COLLECTIONS.items():
        collection = gov_uk_utils.fetch_content(base_path)
        doc_paths = gov_uk_utils.get_collection_document_paths(collection)
        print(f"\n{dept_name}: {len(doc_paths)} publications found")
        for path in doc_paths[:2]:
            publication = gov_uk_utils.fetch_content(path)
            csv_urls = gov_uk_utils.get_csv_attachment_urls(publication)
            print(f"  {path} -> {csv_urls}")


def _report_vat_column_presence(dept_name: str, publication_path: str) -> None:
    """Fetch one publication's first CSV attachment and print whether "vat"
    appears (case-insensitively) anywhere in its first 5 lines, along with
    an ASCII-safe preview of the header row. Helper for
    survey_vat_column_presence().
    """
    publication = gov_uk_utils.fetch_content(publication_path)
    csv_urls = gov_uk_utils.get_csv_attachment_urls(publication)
    if not csv_urls:
        print(f"{dept_name}: no CSV attachment on {publication_path}")
        return
    _, url = csv_urls[0]
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    text = response.content.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()[:5]
    has_vat_column = any("vat" in line.lower() for line in lines)
    header_preview = (lines[0] if lines else "").encode("ascii", errors="replace").decode("ascii")
    print(f"{dept_name}: VAT column present in first 5 lines = {has_vat_column} | first line: {header_preview}")


def survey_vat_column_presence() -> None:
    """Quick check: does this department's latest spend CSV mention "vat"
    anywhere in its first 5 lines (header included)?
    """
    print("\n--- Broader department survey: VAT column presence in latest publication ---")
    for dept_name, base_path in BROADER_SURVEY_COLLECTIONS.items():
        try:
            collection = gov_uk_utils.fetch_content(base_path)
        except Exception as exc:
            print(f"{dept_name}: collection fetch failed ({exc})")
            continue
        doc_paths = gov_uk_utils.get_collection_document_paths(collection)
        if not doc_paths:
            print(f"{dept_name}: no publications found")
            continue
        _report_vat_column_presence(dept_name, doc_paths[0])
    for dept_name, publication_path in BROADER_SURVEY_PUBLICATIONS.items():
        _report_vat_column_presence(dept_name, publication_path)


def inspect_council_datasets() -> None:
    """Print the total count of CKAN "spend over 500" datasets, then a
    random sample of up to 3 with their resource counts and CSV resource URLs,
    as a smoke test of ckan_utils against the real CKAN API.
    """
    total = ckan_utils.get_total_count("spend over 500")
    print(f"\nCKAN 'spend over 500' total datasets: {total}")
    sample = ckan_utils.random_sample_packages("spend over 500", n=3, seed=42)
    for package in sample:
        print(f"\n{package.get('title')} (org: {package.get('organization', {}).get('title')})")
        print(f"  resources: {len(package.get('resources', []))}")
        for name, url in ckan_utils.get_csv_resource_urls(package):
            print(f"    CSV: {name} -> {url}")


def inspect_ckan_organization_schema() -> None:
    """Print the full organization object + resource metadata of a few CKAN
    council-spend results, to see what fields are available for filtering
    to genuine, currently-active local councils (vs NHS bodies, development
    corporations, or dead 2010-era webarchive links).
    """
    result = ckan_utils.package_search("council spend over 500", rows=5, start=0)
    print(f"count={result['count']}")
    for pkg in result["results"]:
        print(json.dumps({
            "title": pkg.get("title"),
            "organization": pkg.get("organization"),
            "metadata_modified": pkg.get("metadata_modified"),
            "resources": [
                {"name": r.get("name"), "format": r.get("format"), "url": r.get("url"),
                 "created": r.get("created"), "last_modified": r.get("last_modified")}
                for r in pkg.get("resources", [])[:2]
            ],
        }, indent=2))


def count_distinct_council_organizations() -> None:
    """After reworking random_sample_distinct_organizations() to sample from a
    full distinct-organization frame instead of deduplicated package offsets,
    confirm how large that qualifying-organization population actually is.
    """
    all_packages = ckan_utils.get_all_packages("council spend over 500")
    print(f"Total datasets for 'council spend over 500': {len(all_packages)}")
    by_org_id = {}
    for package in all_packages:
        if not ckan_utils.is_local_council(package):
            continue
        org_id = package.get("organization", {}).get("id")
        if org_id is None or org_id in by_org_id:
            continue
        by_org_id[org_id] = package
    print(f"Distinct qualifying council organizations: {len(by_org_id)}")


def list_council_keyword_organizations() -> None:
    """List every distinct organization title that contains one of
    is_local_council()'s inclusion keywords, split into what the filter
    currently accepts vs. excludes -- a manual check for non-council bodies
    the exclusion list has yet to catch (this is how the Higher Education
    Funding Council for England gap was originally found; it's since been
    added to _NON_COUNCIL_ORG_KEYWORDS).
    """
    all_packages = ckan_utils.get_all_packages("council spend over 500")
    inclusion_keywords = ("council", "borough", "county", "unitary", "combined authority")
    seen_titles: set[str] = set()
    accepted = set()
    excluded = set()
    for package in all_packages:
        title = (package.get("organization", {}) or {}).get("title", "")
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        if not any(keyword in title.lower() for keyword in inclusion_keywords):
            continue
        if ckan_utils.is_local_council(package):
            accepted.add(title)
        else:
            excluded.add(title)
    print(f"Accepted as local council ({len(accepted)}):")
    for title in sorted(accepted):
        safe_print_title = title.encode("ascii", errors="replace").decode("ascii")
        print(f"  {safe_print_title}")
    print(f"\nExcluded as non-council ({len(excluded)}):")
    for title in sorted(excluded):
        safe_print_title = title.encode("ascii", errors="replace").decode("ascii")
        print(f"  {safe_print_title}")


if __name__ == "__main__":
    list_council_keyword_organizations()
    print()
    count_distinct_council_organizations()
