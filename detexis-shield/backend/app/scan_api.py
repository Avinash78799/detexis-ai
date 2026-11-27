import hashlib
import hmac
import secrets
import os
import httpx
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from redis.exceptions import RedisError

from .auth import legacy_site
from .db import get_db
from .models import Scan, Site
from .redis_store import get_redis
from .safe_fetch import domain_name, UnsafeTarget
from .scanner import txt
from .worker import utc

router = APIRouter()


@router.post("/v1/domain/verification")
def start_verification(site=Depends(legacy_site), db=Depends(get_db)):
    try:
        domain = domain_name(site.domain)
    except UnsafeTarget:
        raise HTTPException(422, "site must use a valid DNS domain")
    token = "dxs-verification=" + secrets.token_urlsafe(32)
    site.verification_hash = hashlib.sha256(token.encode()).hexdigest()
    site.verified_at = None
    db.commit()
    return {"record": "_detexis." + domain, "type": "TXT", "value": token,
            "http_url": f"https://{domain}/.well-known/detexis-shield.txt",
            "instructions": "Publish the value in either the TXT record or the exact HTTPS file"}


def verify_http(domain, expected_hash):
    try:
        with httpx.Client(timeout=15, trust_env=False) as http:
            response = http.post(os.getenv("SCANNER_SERVICE_URL", "http://scanner:8001") + "/verify",
                                 json={"domain": domain, "expected_hash": expected_hash})
            response.raise_for_status()
            return response.json().get("verified") is True
    except Exception:
        return False


@router.post("/v1/domain/verify")
def confirm_verification(site=Depends(legacy_site), db=Depends(get_db), redis=Depends(get_redis)):
    site_id, domain, expected_hash = site.id, site.domain, site.verification_hash
    if not expected_hash:
        raise HTTPException(409, "request a verification token first")
    try:
        if not redis.set(f"dxs:verify-cooldown:{site_id}", "1", nx=True, ex=60):
            raise HTTPException(429, "verification cooldown", headers={"Retry-After": "60"})
    except RedisError:
        raise HTTPException(503, "verification temporarily unavailable")
    try:
        values = txt("_detexis." + domain_name(domain))
    except Exception:
        values = []
    dns_verified = any(hmac.compare_digest(hashlib.sha256(value.encode()).hexdigest(), expected_hash) for value in values)
    if not dns_verified and not verify_http(domain, expected_hash):
        raise HTTPException(422, "verification token not found in DNS or the well-known HTTPS file")
    # The lookup can outlive a challenge rotation. Verify only the challenge checked above.
    confirmed = db.scalar(update(Site).where(
        Site.id == site_id, Site.domain == domain, Site.verification_hash == expected_hash,
    ).values(verified_at=datetime.now(timezone.utc)).returning(Site.id))
    if confirmed is None:
        raise HTTPException(409, "Verification challenge changed. Refresh the website settings before trying again")
    db.commit()
    return {"verified": True}


@router.post("/v1/scans", status_code=202)
def request_scan(site=Depends(legacy_site), db=Depends(get_db), redis=Depends(get_redis)):
    site = db.scalar(select(Site).where(Site.id == site.id).with_for_update().execution_options(populate_existing=True))
    if site.verified_at is None or utc(site.verified_at) < datetime.now(timezone.utc) - timedelta(days=7):
        raise HTTPException(403, "recent domain ownership verification required")
    scans = select(Scan).where(Scan.site_id == site.id)
    pending = db.scalar(scans.where(Scan.status == "pending", Scan.created_at >= site.verified_at))
    recent = db.scalar(scans.where(Scan.status.in_(("complete", "failed"))).order_by(Scan.created_at.desc()).limit(1))
    if pending:
        record = pending
    else:
        if recent and utc(recent.created_at) > datetime.now(timezone.utc) - timedelta(hours=1):
            raise HTTPException(429, "scan cooldown", headers={"Retry-After": "3600"})
        record = Scan(site_id=site.id)
        db.add(record)
    db.commit()
    try:
        from .scan_jobs import enqueue_scan
        enqueue_scan(record.id, redis)
    except RedisError:
        pass  # Maintenance requeues pending scans.
    return {"scan_id": record.id}


@router.get("/v1/scans/{scan_id}")
def get_scan(scan_id: str, site=Depends(legacy_site), db=Depends(get_db)):
    record = db.scalar(select(Scan).where(Scan.id == scan_id, Scan.site_id == site.id))
    if record is None:
        raise HTTPException(404, "scan not found")
    return {"id": record.id, "status": record.status, "result": record.result}
