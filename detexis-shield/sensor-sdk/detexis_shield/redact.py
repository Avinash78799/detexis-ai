import hashlib
from datetime import datetime, timezone
from urllib.parse import parse_qsl

SENSITIVE_KEYS = {"password", "passwd", "pwd", "token", "access_token", "secret",
                  "api_key", "apikey", "authorization", "session", "sid", "otp", "card"}


def hash_ip(ip: str, site_salt: str) -> str:
    """Per-site, per-day salted hash: same IP correlates within a day, not long-term."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{site_salt}:{day}:{ip}".encode()).hexdigest()


def redact_query(query: str, max_len: int = 1024) -> str:
    """Keep param names and values (rules need payloads) but mask sensitive keys."""
    parts = []
    for k, v in parse_qsl(query, keep_blank_values=True)[:50]:
        parts.append(f"{k}=[REDACTED]" if k.lower() in SENSITIVE_KEYS else f"{k}={v}")
    return "&".join(parts)[:max_len]
