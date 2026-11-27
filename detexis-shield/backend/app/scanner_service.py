"""Internal scanner API: no database client, Redis client or application secrets."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .scanner import scan
from .safe_fetch import UnsafeTarget
from .safe_fetch import fetch, domain_name
import hashlib
import hmac

app = FastAPI(docs_url=None, redoc_url=None)


class ScanInput(BaseModel):
    domain: str = Field(max_length=253)
    selectors: list[str] = Field(default_factory=list, max_length=5)


class VerificationInput(BaseModel):
    domain: str = Field(max_length=253)
    expected_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


@app.post("/verify")
def verify_page(body: VerificationInput):
    try:
        domain = domain_name(body.domain)
        result = fetch(f"https://{domain}/.well-known/detexis-shield.txt", domain)
        valid = result["status"] == 200 and len(result["body"]) <= 4096 and hmac.compare_digest(
            hashlib.sha256(result["body"].strip()).hexdigest(), body.expected_hash)
        return {"verified": valid}
    except Exception:
        return {"verified": False}


@app.post("/scan")
def run_scan(body: ScanInput):
    try:
        return scan(body.domain, body.selectors)
    except (UnsafeTarget, TimeoutError, OSError):
        raise HTTPException(422, "scan destination unavailable or unsafe")
