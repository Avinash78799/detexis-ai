import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode

SENSITIVE_KEYS = {"password", "passwd", "pwd", "token", "access_token", "secret",
                  "api_key", "apikey", "authorization", "session", "sid", "otp", "card"}

MAX_QUERY_INPUT = 8192
MAX_QUERY_STORED = 1024
MAX_QUERY_FIELDS = 50
_PERCENT_RUN = re.compile(rb'(?:%[0-9A-Fa-f]{2})+')


def _parse_query(query: str) -> list[tuple[str, str]]:
    """Equivalent bounded-query decoding; batch contiguous escapes in native hex code.

    Ordinary/Unicode inputs retain urllib behavior. On long ASCII encodings,
    split separators before decoding so escaped delimiters remain field values.
    Decode UTF-8 only after joining decoded runs, preserving replacement behavior.
    Callers bound input length and field count before entering this helper.
    """
    if not query.isascii() or query.count('%') < 64:
        return parse_qsl(query, keep_blank_values=True)

    def decode(value):
        raw = value.replace('+', ' ').encode('ascii')
        decoded = _PERCENT_RUN.sub(lambda match: bytes.fromhex(
            match[0].replace(b'%', b'').decode('ascii')), raw)
        return decoded.decode('utf-8', errors='replace')

    return [(decode(key), decode(value)) for field in query.split('&') if field
            for key, _, value in [field.partition('=')]]


def hash_ip(ip: str, site_salt: str) -> str:
    """Per-site, per-day salted hash: same IP correlates within a day, not long-term."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{site_salt}:{day}:{ip}".encode()).hexdigest()


def redact_query(query: str, max_len: int = MAX_QUERY_STORED) -> str:
    """Keep param names and values (rules need payloads) but mask sensitive keys."""
    # Bound parsing before allocating pairs, and retain escaped parameter boundaries.
    bounded = "&".join(query[:MAX_QUERY_INPUT].split("&", MAX_QUERY_FIELDS)[:MAX_QUERY_FIELDS])
    pairs = _parse_query(bounded)
    return urlencode([(k, "[REDACTED]" if k.lower() in SENSITIVE_KEYS else v)
                      for k, v in pairs])[:max_len]
