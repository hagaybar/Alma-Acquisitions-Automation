"""Regression test: AlmaAPIError messages and api_client debug logs must not carry credentials.

Pins the contract this repo's ~35 `print(f"...{e}")` and exception-logging sites
depend on. Fails if a future almaapitk upgrade regresses redaction. Guards F3 of
the security audit in issue #2.

Skipped when ALMA_SB_API_KEY is not set (requires a real SANDBOX round-trip).
"""

import io
import logging
import os
import re

import pytest

from almaapitk import AlmaAPIClient, AlmaAPIError


REDACTED = "***REDACTED***"
NONEXISTENT_POL_ENDPOINT = "almaws/v1/acq/po-lines/POL-DOES-NOT-EXIST-99999999"


def _key_or_skip() -> str:
    key = os.environ.get("ALMA_SB_API_KEY", "")
    if not key:
        pytest.skip("ALMA_SB_API_KEY not set; skipping live-call regression test")
    return key


def _assert_no_credential_material(text: str, key: str, *, allow_redacted_marker: bool = True) -> None:
    assert key not in text, "raw API key value appears in captured text"
    assert not re.search(r"apikey=[A-Za-z0-9_\-]+", text), "apikey= query parameter with value"
    for match in re.finditer(r"[Aa]uthorization\s*[:=]\s*([^\s,'\"\\}]+)", text):
        value = match.group(1).strip("'\"")
        if allow_redacted_marker and value == REDACTED:
            continue
        raise AssertionError(f"Authorization header value not redacted: {match.group(0)!r}")


def test_alma_api_error_str_carries_no_key() -> None:
    """str(AlmaAPIError) is the upstream errorMessage only — no URL, no key."""
    key = _key_or_skip()
    client = AlmaAPIClient("SANDBOX")
    with pytest.raises(AlmaAPIError) as exc_info:
        client.get(NONEXISTENT_POL_ENDPOINT)
    _assert_no_credential_material(str(exc_info.value), key)
    _assert_no_credential_material(repr(exc_info.value), key)


def test_print_pattern_is_safe() -> None:
    """The `print(f'Error: {e}')` pattern used ~35 times in this repo is safe."""
    key = _key_or_skip()
    client = AlmaAPIClient("SANDBOX")
    with pytest.raises(AlmaAPIError) as exc_info:
        client.get(NONEXISTENT_POL_ENDPOINT)
    rendered = f"✗ Error: {exc_info.value}"
    _assert_no_credential_material(rendered, key)


def test_debug_logging_redacts_authorization_header() -> None:
    """almaapitk's DEBUG api_client log must show Authorization: ***REDACTED***."""
    key = _key_or_skip()
    client = AlmaAPIClient("SANDBOX")
    # Swap the handler's stream so we catch what reaches the terminal regardless of pytest capture timing.
    api_logger = logging.getLogger("almapi.api_client")
    stream_handlers = [
        h for h in api_logger.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    ]
    assert stream_handlers, "expected almaapitk to attach a StreamHandler to almapi.api_client"

    buf = io.StringIO()
    originals = [(h, h.stream) for h in stream_handlers]
    for h, _ in originals:
        h.stream = buf
    try:
        with pytest.raises(AlmaAPIError):
            client.get(NONEXISTENT_POL_ENDPOINT)
        captured = buf.getvalue()
    finally:
        for h, original_stream in originals:
            h.stream = original_stream

    assert "Authorization" in captured, "debug log should contain an Authorization line"
    _assert_no_credential_material(captured, key)
