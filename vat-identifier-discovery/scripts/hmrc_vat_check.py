"""Reusable helpers for validating UK VAT numbers against the HMRC "Check a UK VAT
number" API (sandbox) and against the standalone modulus-97 checksum.

Sandbox limitation (see FINDINGS.md): the sandbox environment only recognises a
fixed list of HMRC-provided mock VAT reference numbers (see
https://github.com/hmrc/vat-registered-companies-api/tree/master/public/api/conf/2.0/test-data).
Real VAT numbers discovered from actual sources will return 404 NOT_FOUND from
sandbox -- this does not mean the discovered number is invalid, it means sandbox
cannot confirm it. Production credentials would be required for genuine HMRC
confirmation. `is_valid_uk_vat_checksum` is the structural fallback used instead.

Credentials (HMRC_CLIENT_ID, HMRC_CLIENT_SECRET) are read from the environment at
call time only, via a .env file in the project root. Never log or persist them.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://test-api.service.hmrc.gov.uk/oauth/token"
API_BASE = "https://test-api.service.hmrc.gov.uk"
ACCEPT_HEADER = "application/vnd.hmrc.2.0+json"

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Sandbox rate limiting (see FINDINGS.md Open Question #9): sequential calls
# were observed to hit 429 MESSAGE_THROTTLED_OUT about half the time with no
# delay between them. Space calls out, and back off with retries on 429.
_MIN_CALL_INTERVAL_SECONDS = 1.0
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 3.0

_last_call_time: float | None = None


def get_access_token() -> str:
    """Obtain an OAuth2 client-credentials bearer token for the sandbox."""
    load_dotenv(_ENV_PATH)
    client_id = os.environ["HMRC_CLIENT_ID"]
    client_secret = os.environ["HMRC_CLIENT_SECRET"]

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "read:vat",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _wait_for_rate_limit() -> None:
    """Space sandbox calls at least _MIN_CALL_INTERVAL_SECONDS apart."""
    global _last_call_time
    if _last_call_time is not None:
        elapsed = time.monotonic() - _last_call_time
        remaining = _MIN_CALL_INTERVAL_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)
    _last_call_time = time.monotonic()


def check_vat_number(vrn: str, token: str) -> dict:
    """Look up a VRN (9 or 12 digits, no GB/XI prefix) via the sandbox API.

    Returns the parsed JSON body regardless of status code (the caller decides
    how to interpret 200/400/404/500), plus a "status_code" key. Self-throttles
    (see _MIN_CALL_INTERVAL_SECONDS) and retries with backoff on 429.
    """
    url = f"{API_BASE}/organisations/vat/check-vat-number/lookup/{vrn}"

    for attempt in range(_MAX_RETRIES + 1):
        _wait_for_rate_limit()
        response = requests.get(
            url,
            headers={
                "Accept": ACCEPT_HEADER,
                "Authorization": f"Bearer {token}",
            },
            timeout=15,
        )
        if response.status_code == 429 and attempt < _MAX_RETRIES:
            time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
            continue
        body = response.json() if response.content else {}
        body["status_code"] = response.status_code
        return body

    raise AssertionError("unreachable: loop always returns or raises")


def normalize_vat_number(raw: str) -> str:
    """Strip a GB/XI country prefix and any whitespace, keep digits only."""
    cleaned = raw.strip().upper()
    for prefix in ("GB", "XI"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    return "".join(ch for ch in cleaned if ch.isdigit())


def is_valid_uk_vat_checksum(vrn: str) -> tuple[bool, str]:
    """Validate a normalized (digits-only) UK VAT number via modulus-97.

    Applies to standard 9-digit business VRNs (the checksum is computed over
    the first 9 digits; a 12-digit VRN's trailing 3 digits are a branch/group
    suffix and are ignored here). Returns (is_valid, style) where style is
    "old" (pre-Nov-2009 numbering), "new" (modulus 9755, post-Nov-2009), or
    "none" if neither matches.

    Known limitation: government department (GD) and health authority (HA)
    VRNs use a separate, non-checksummed numbering scheme and will always
    report as invalid here even if genuinely issued.
    """
    if len(vrn) not in (9, 12) or not vrn.isdigit():
        return False, "none"

    base = vrn[:9]
    weights = (8, 7, 6, 5, 4, 3, 2)
    total = sum(int(d) * w for d, w in zip(base[:7], weights))
    check_digits = int(base[7:9])

    old_check = (97 - total % 97) % 97
    new_check = (97 - (total + 55) % 97) % 97

    if old_check == check_digits:
        return True, "old"
    if new_check == check_digits:
        return True, "new"
    return False, "none"


if __name__ == "__main__":
    print("--- Proving the sandbox integration works (HMRC's own mock VRN) ---")
    token = get_access_token()
    mock_result = check_vat_number("553557881", token)
    print(mock_result)

    print("\n--- Real discovered VRN (DEFRA example, GB100177077) ---")
    real_vrn = normalize_vat_number("GB100177077")
    real_result = check_vat_number(real_vrn, token)
    print(real_result)

    valid, style = is_valid_uk_vat_checksum(real_vrn)
    print(f"\nChecksum validation for {real_vrn}: valid={valid} style={style}")
