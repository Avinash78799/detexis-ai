import hashlib
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode

SENSITIVE_KEYS = {"password", "passwd", "pwd", "token", "access_token", "secret",
                  "api_key", "apikey", "authorization", "session", "sid", "otp", "card"}

MAX_QUERY_INPUT = 8192
MAX_QUERY_STORED = 1024
MAX_QUERY_FIELDS = 50


def hash_ip(ip: str, site_salt: str) -> str:
    """Per-site, per-day salted hash: same IP correlates within a day, not long-term."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{site_salt}:{day}:{ip}".encode()).hexdigest()


def redact_query(query: str, max_len: int = MAX_QUERY_STORED) -> str:
    """Keep param names and values (rules need payloads) but mask sensitive keys."""
    # Bound parsing before allocating pairs, and retain escaped parameter boundaries.
    bounded = "&".join(query[:MAX_QUERY_INPUT].split("&", MAX_QUERY_FIELDS)[:MAX_QUERY_FIELDS])
    pairs = parse_qsl(bounded, keep_blank_values=True)
    return urlencode([(k, "[REDACTED]" if k.lower() in SENSITIVE_KEYS else v)
                      for k, v in pairs])[:max_len]
