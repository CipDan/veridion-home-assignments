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
        params={"q": query, "rows": rows, "start": start},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["result"]


def get_total_count(query: str) -> int:
    """Number of datasets matching a query, without fetching any result rows."""
    return package_search(query, rows=0, start=0)["count"]


def random_sample_packages(query: str, n: int, seed: int) -> list[dict]:
    """Randomly sample n dataset records matching a CKAN query, without fetching the full result set.

    Draws n distinct random offsets into the total result count and fetches one record per offset.
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
    query: str, n: int, seed: int, organization_filter=None, max_draws: int = 300
) -> list[dict]:
    """Randomly sample up to n dataset records with distinct publishing organizations.

    A plain random_sample_packages() draw can return the same council multiple
    times (many councils publish several dataset entries, e.g. current +
    archived). This keeps drawing random offsets (up to max_draws) until n
    distinct organizations are found or the draw pool is exhausted.
    """
    total = get_total_count(query)
    rng = random.Random(seed)
    offsets = rng.sample(range(total), k=min(max_draws, total))
    seen_org_ids = set()
    packages = []
    for offset in offsets:
        if len(packages) >= n:
            break
        result = package_search(query, rows=1, start=offset)
        if not result["results"]:
            continue
        package = result["results"][0]
        if organization_filter is not None and not organization_filter(package):
            continue
        org_id = package.get("organization", {}).get("id")
        if org_id in seen_org_ids:
            continue
        seen_org_ids.add(org_id)
        packages.append(package)
    return packages


def get_best_csv_resource(package: dict) -> tuple[str, str] | None:
    """Pick one usable CSV resource from a dataset: prefer non-archived, most
    recently created. Returns None if no live-looking CSV resource exists.
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
