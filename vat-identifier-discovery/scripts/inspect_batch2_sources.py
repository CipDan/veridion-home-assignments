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
    for dept_name, base_path in DEPARTMENT_COLLECTIONS.items():
        collection = gov_uk_utils.fetch_content(base_path)
        doc_paths = gov_uk_utils.get_collection_document_paths(collection)
        print(f"\n{dept_name}: {len(doc_paths)} publications found")
        for path in doc_paths[:2]:
            publication = gov_uk_utils.fetch_content(path)
            csv_urls = gov_uk_utils.get_csv_attachment_urls(publication)
            print(f"  {path} -> {csv_urls}")


def _report_vat_column_presence(dept_name: str, publication_path: str) -> None:
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
    """Quick header-only check: does this department's latest spend CSV have a VAT column at all?"""
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


if __name__ == "__main__":
    inspect_ckan_organization_schema()
