"""Helpers for Web Data Commons' schema.org class-specific quad extracts
(2024-12 release, Organization class):
https://webdatacommons.org/structureddata/2024-12/stats/schema_org_subsets.html

- Organization_domain_stats.csv: one row per pay-level domain (pld), giving
  quad/entity counts and a {property: density} dict recording which
  schema.org properties are populated on that domain's Organization
  entities. Small enough (a few hundred MB) to scan directly for a
  vatID hit-rate, unlike the full 488GB N-Quads corpus.
- Organization_lookup.csv: maps each pld to the part_N.gz file its quads
  live in.
- part_N.gz: the actual N-Quads data, gzip-compressed, one quad per line.
"""

from __future__ import annotations

import ast
import csv
import gzip
import json
import os
import tempfile
from collections.abc import Iterator
from urllib.parse import urlparse

import requests

BASE_URL = "https://data.dws.informatik.uni-mannheim.de/structureddata/2024-12/quads/classspecific/Organization"
DOMAIN_STATS_URL = f"{BASE_URL}/Organization_domain_stats.csv"
LOOKUP_URL = f"{BASE_URL}/Organization_lookup.csv"

VAT_ID_PREDICATE = "http://schema.org/vatID"
NAME_PREDICATE = "http://schema.org/name"
URL_PREDICATE = "http://schema.org/url"


def download_file(url: str, dest_path: str) -> None:
    """Stream-download a (potentially large) file to dest_path.

    Streams into a temp file in the same directory and atomically renames it
    into place only once the download completes successfully -- so a crash
    or interruption partway through can't leave a partial file that
    ensure_file() would mistake for a complete, already-downloaded one.
    """
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


def iter_domain_stats(path: str) -> Iterator[tuple[str, int, int, dict[str, float]]]:
    """Yield (domain, n_quads, n_entities, {property: density}) per row of
    Organization_domain_stats.csv.
    """
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        assert header == ["Domain", "#Quads of Subset", "#Entities of class", "Properties and Density"]
        for row in reader:
            if not row:
                continue
            domain, n_quads, n_entities, properties_repr = row
            properties = ast.literal_eval(properties_repr) if properties_repr else {}
            yield domain, int(n_quads), int(n_entities), properties


def is_uk_domain(domain: str) -> bool:
    """Heuristic: domain ends in '.uk' (.co.uk, .org.uk, .gov.uk, ...).

    This is a domain-hosting signal, not proof the underlying organization
    is UK-registered (a UK company can trade under a .com domain and a
    non-UK entity can hold a .uk one) -- treat as a coverage filter, not
    ground truth.
    """
    return domain.lower().endswith(".uk")


def load_file_lookup(path: str, target_domains: set[str]) -> dict[str, str]:
    """Return {domain: part_file_name} for target_domains, scanning
    Organization_lookup.csv (pld,tld,file_lookup) row by row rather than
    loading the whole file into memory.
    """
    result = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["pld", "tld", "file_lookup"]
        for row in reader:
            if not row:
                continue
            pld, _tld, file_lookup = row
            if pld in target_domains:
                result[pld] = file_lookup
    return result


def parse_nquad_line(line: str) -> tuple[str, str, str, str] | None:
    """Parse one line of N-Quads into (subject, predicate, object_raw, graph).

    object_raw is returned still N-Triples-encoded (a bracketed IRI, a blank
    node id, or a quoted literal with an optional @lang/^^datatype suffix) --
    use strip_literal() to get a literal's plain text. Returns None for
    blank or unparseable lines.
    """
    line = line.strip()
    if not line.endswith(" ."):
        return None
    body = line[:-2].strip()

    parts = body.split(" ", 1)
    if len(parts) != 2:
        return None
    subject, rest = parts

    parts = rest.split(" ", 1)
    if len(parts) != 2:
        return None
    predicate, rest = parts
    if not (predicate.startswith("<") and predicate.endswith(">")):
        return None
    predicate = predicate[1:-1]

    # WDC quads always carry a graph (the source page URL) as the final
    # "<...>" token; everything before it is the object.
    last_close = rest.rfind(">")
    last_open = rest.rfind("<", 0, last_close) if last_close != -1 else -1
    if last_open == -1:
        return None
    graph = rest[last_open + 1:last_close]
    object_raw = rest[:last_open].strip()

    return subject, predicate, object_raw, graph


def strip_literal(object_raw: str) -> str:
    """Strip a quoted N-Triples literal's surrounding quotes and any
    trailing @lang/^^datatype suffix. Returns object_raw unchanged if it
    isn't a quoted literal (e.g. it's an IRI or blank node).
    """
    if not object_raw.startswith('"'):
        return object_raw
    end_quote = object_raw.rfind('"')
    return object_raw[1:end_quote]


def _pld_of_host(host: str, target_domains: set[str]) -> str | None:
    """Return whichever suffix of host (checked longest-first) is a member
    of target_domains, e.g. host="www.example.co.uk" matches pld
    "example.co.uk". None if no suffix matches.
    """
    labels = host.split(".")
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])
        if candidate in target_domains:
            return candidate
    return None


def extract_entities_for_domains(part_gz_path: str, target_domains: set[str]) -> dict[str, dict]:
    """Scan a part_N.gz N-Quads file, collecting schema.org name/url/vatID
    values for every quad whose graph URL's host falls under one of
    target_domains.

    Returns {subject: {"domain": ..., "graph": ..., "name": ..., "url": ...,
    "vatID": ...}} (the latter three keys present only if seen).
    """
    entities: dict[str, dict] = {}
    with gzip.open(part_gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = parse_nquad_line(line)
            if parsed is None:
                continue
            subject, predicate, object_raw, graph = parsed
            if predicate not in (VAT_ID_PREDICATE, NAME_PREDICATE, URL_PREDICATE):
                continue
            host = urlparse(graph).hostname or ""
            domain = _pld_of_host(host, target_domains)
            if domain is None:
                continue
            entry = entities.setdefault(subject, {"domain": domain, "graph": graph})
            if predicate == VAT_ID_PREDICATE:
                entry["vatID"] = strip_literal(object_raw)
            elif predicate == NAME_PREDICATE:
                entry["name"] = strip_literal(object_raw)
            elif predicate == URL_PREDICATE:
                entry["url"] = strip_literal(object_raw)
    return entities


def save_checkpoint(path: str, target_domains: set[str], processed_parts: set[str], entities: dict[str, dict]) -> None:
    """Persist extraction progress after each part file is scanned, so a
    crash or interruption partway through a multi-hundred-file run doesn't
    lose everything already extracted. Written to a temp file and then
    renamed into place (atomic on the same filesystem), so an interruption
    mid-write can't corrupt the previous, still-good checkpoint.

    target_domains is stored alongside processed_parts/entities so a later
    run with a different domain selection can detect the mismatch (see
    load_checkpoint) instead of silently skipping domains that happen to
    live in an already-"processed" part file.
    """
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "target_domains": sorted(target_domains),
                "processed_parts": sorted(processed_parts),
                "entities": entities,
            },
            f,
        )
    os.replace(tmp_path, path)


def load_checkpoint(path: str, target_domains: set[str]) -> tuple[set[str], dict[str, dict]]:
    """Load a previously saved checkpoint, or (set(), {}) if none exists yet
    or its stored target_domains doesn't match the current run's -- reusing
    processed_parts/entities from a different domain selection would
    silently skip domains newly added to target_domains that happen to live
    in an already-"processed" part file.
    """
    if not os.path.exists(path):
        return set(), {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if set(data.get("target_domains", [])) != target_domains:
        return set(), {}
    return set(data["processed_parts"]), data["entities"]
