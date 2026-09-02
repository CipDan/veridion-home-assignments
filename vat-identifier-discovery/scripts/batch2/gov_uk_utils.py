"""Helpers for gov.uk's public Content API (no auth required).

Used to enumerate a department's monthly "spending over £25,000" publications
from its collection page, and to pull the CSV attachment URL(s) off each
individual publication page, without scraping rendered HTML.
"""

import requests

CONTENT_API_BASE = "https://www.gov.uk/api/content"


def fetch_content(base_path: str) -> dict:
    """Fetch a gov.uk page's Content API JSON, e.g. base_path='/government/collections/defra-departmental-spending-over-25000'."""
    response = requests.get(f"{CONTENT_API_BASE}{base_path}", timeout=30)
    response.raise_for_status()
    return response.json()


def get_collection_document_paths(collection_json: dict) -> list[str]:
    """Return the base_path of every document linked from a collection page, in listed order."""
    documents = collection_json.get("links", {}).get("documents", [])
    return [doc["base_path"] for doc in documents if "base_path" in doc]


def get_csv_attachment_urls(publication_json: dict) -> list[tuple[str, str]]:
    """Return (title, url) for every CSV attachment on a publication page."""
    attachments = publication_json.get("details", {}).get("attachments", [])
    results = []
    for attachment in attachments:
        url = attachment.get("url", "")
        content_type = attachment.get("content_type", "")
        if content_type == "text/csv" or url.lower().endswith(".csv"):
            results.append((attachment.get("title", ""), url))
    return results
