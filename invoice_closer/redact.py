"""Redaction for the detailed log.

The log keeps record identifiers and states (they are what makes it useful), and
removes what must not be kept: credentials, e-mail addresses, and free-text notes
that may name staff or patrons.
"""
import re
from typing import Any

SECRET_KEY = re.compile(r"(api[_-]?key|authorization|token|password|secret)", re.I)
FREE_TEXT_KEY = re.compile(r"^(note|notes|receiving_note|vendor_note|renewal_note|"
                           r"vendor_contact_person|contact_person)$", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
APIKEY_IN_URL = re.compile(r"(apikey=)[^&\s]+", re.I)
LONG_SECRET = re.compile(r"\bl[0-9a-f]{4,}[0-9a-f]{20,}\b")  # Alma API key shape

REDACTED = "<redacted>"


def redact_text(text: str) -> str:
    text = APIKEY_IN_URL.sub(r"\1" + REDACTED, text)
    text = EMAIL.sub("<email>", text)
    text = LONG_SECRET.sub(REDACTED, text)
    return text


def redact(value: Any) -> Any:
    """Return a redacted deep copy of a JSON-like value."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if SECRET_KEY.search(str(k)):
                out[k] = REDACTED
            elif FREE_TEXT_KEY.match(str(k)):
                out[k] = REDACTED if v else v
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
