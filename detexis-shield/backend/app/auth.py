import hashlib
import hmac
import secrets
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import ApiKey, Site


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_api_key() -> tuple[str, str, str]:
    """Return (raw_key, prefix, key_hash). Show raw_key to the user ONCE."""
    prefix = secrets.token_hex(6)
    raw = f"dxs_{prefix}_{secrets.token_urlsafe(32)}"
    return raw, prefix, hash_key(raw)


def current_site(x_api_key: str | None = Header(None), db: Session = Depends(get_db)) -> Site:
    if not x_api_key or len(x_api_key) > 128:
        raise HTTPException(401, "invalid api key")
    parts = (x_api_key or "").split("_", 2)
    if len(parts) < 3 or parts[0] != "dxs":
        raise HTTPException(401, "invalid api key")
    row = db.scalar(select(ApiKey).where(ApiKey.prefix == parts[1], ApiKey.revoked == False))  # noqa: E712
    if not row or not hmac.compare_digest(row.key_hash, hash_key(x_api_key)):
        raise HTTPException(401, "invalid api key")
    site = db.get(Site, row.site_id)
    if not site:
        raise HTTPException(401, "invalid api key")
    return site
