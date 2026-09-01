"""Helpers for the data.gov.uk CKAN API (no auth required).

Used to enumerate local council "spend over £500" transparency datasets,
which have no single central bulk-download point the way departmental
spend-over-£25k data does.
"""

import random

import requests

CKAN_API_BASE = "https://ckan.publishing.service.gov.uk/api/3/action"


def package_search(query: str, rows: int = 20, start: int = 0) -> dict:
    """Run a CKAN package_search query, returning the raw 'result' object (count + results)."""
    response = requests.get(
        f"{CKAN_API_BASE}/package_search",
        params={"q": query, "rows": str(rows), "start": str(start)},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["result"]


def get_total_count(query: str) -> int:
    """Number of datasets matching a query, without fetching any result rows."""
    return package_search(query, rows=0, start=0)["count"]


def random_sample_packages(query: str, n: int, seed: int) -> list[dict]:
    """Randomly sample up to n dataset records matching a CKAN query, without fetching the full result set.

    Draws n distinct random offsets into the total result count and fetches one record per offset;
    an offset can come back empty if the catalogue changes between the count and the fetch, so
    fewer than n records may be returned.
    """
    total = get_total_count(query)
    rng = random.Random(seed)
    offsets = rng.sample(range(total), k=min(n, total))
    packages = []
    for offset in offsets:
        result = package_search(query, rows=1, start=offset)
        if result["results"]:
            packages.append(result["results"][0])
    return packages


def get_all_packages(query: str, page_size: int = 100) -> list[dict]:
    """Fetch every dataset record matching a CKAN query, paginated."""
    total = get_total_count(query)
    packages = []
    start = 0
    while start < total:
        result = package_search(query, rows=page_size, start=start)
        packages.extend(result["results"])
        start += page_size
    return packages


def get_csv_resource_urls(package: dict) -> list[tuple[str, str]]:
    """Return (name, url) for every CSV resource attached to a CKAN dataset record."""
    resources = package.get("resources", [])
    results = []
    for resource in resources:
        fmt = (resource.get("format") or "").upper()
        url = resource.get("url", "")
        if fmt == "CSV" or url.lower().endswith(".csv"):
            results.append((resource.get("name", ""), url))
    return results


_NON_COUNCIL_ORG_KEYWORDS = (
    "british council",
    "science and technology facilities council",
    "arts council",
    "research council",
    "design council",
    "innovate uk",
    "met office",
    "sport england",
    "national trust",
    "higher education funding council",
    "council for healthcare regulatory excellence",
    "general social care council",
    "children's workforce development council",
)


def is_local_council(package: dict) -> bool:
    """True if the publishing organization's title reads as a UK local authority.

    CKAN's organization schema has no dedicated "local authority" type field,
    so this is a title-keyword heuristic -- filters out NHS trusts/ICBs,
    development corporations, and UK national bodies that happen to have
    "Council" in their name (British Council, Research Councils, etc.) but
    aren't local government.
    """
    title = (package.get("organization", {}) or {}).get("title", "").lower()
    if any(keyword in title for keyword in _NON_COUNCIL_ORG_KEYWORDS):
        return False
    keywords = ("council", "borough", "county", "unitary", "combined authority")
    return any(keyword in title for keyword in keywords)


def random_sample_distinct_organizations(
    query: str, n: int, seed: int, organization_filter=None
) -> list[dict]:
    """Randomly sample up to n dataset records with distinct publishing organizations,
    drawn uniformly from the full population of qualifying organizations.

    A plain random_sample_packages() draw can return the same council multiple
    times (many councils publish several dataset entries, e.g. current +
    archived), and sampling random package offsets with on-the-fly dedup would
    weight the result by how many datasets each organization happens to
    publish rather than sampling councils on equal footing. Instead, this
    fetches every matching dataset once, reduces to one representative record
    per distinct (optionally filtered) organization, then samples n of those
    organizations uniformly at random.
    """
    all_packages = get_all_packages(query)
    by_org_id: dict[str, dict] = {}
    for package in all_packages:
        if organization_filter is not None and not organization_filter(package):
            continue
        org_id = package.get("organization", {}).get("id")
        if org_id is None or org_id in by_org_id:
            continue
        by_org_id[org_id] = package
    distinct_packages = list(by_org_id.values())
    rng = random.Random(seed)
    return rng.sample(distinct_packages, k=min(n, len(distinct_packages)))


def get_best_csv_resource(package: dict) -> tuple[str, str] | None:
    """Pick one usable CSV resource from a dataset: excludes archived
    (webarchive.nationalarchives.gov.uk) links entirely, then picks the most
    recently created of what remains. Returns None if no live-looking CSV
    resource exists.
    """
    candidates = []
    for resource in package.get("resources", []):
        fmt = (resource.get("format") or "").upper()
        url = resource.get("url", "")
        if not url or (fmt != "CSV" and not url.lower().endswith(".csv")):
            continue
        if "webarchive.nationalarchives.gov.uk" in url:
            continue
        candidates.append(resource)
    if not candidates:
        return None
    candidates.sort(key=lambda r: r.get("created") or "", reverse=True)
    best = candidates[0]
    return best.get("name", ""), best.get("url", "")
