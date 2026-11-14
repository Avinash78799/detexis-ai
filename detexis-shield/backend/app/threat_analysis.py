"""On-demand analysis. Samples are not persisted or added to the incident stream."""
import base64
import binascii
import hashlib
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from detexis_shield.features import extract_features
from detexis_shield.redact import redact_query

from .accounts import owner, throttle
from .redis_store import get_redis
from .rules import evaluate
from . import malware

router = APIRouter(prefix="/app/api/analyze")
scan_slot = threading.BoundedSemaphore(1)


class RequestSample(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    query: str = Field(default="", max_length=1024)
    user_agent: str = Field(default="", max_length=512)
    status: int = Field(default=200, ge=100, le=599)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value):
        if not value.startswith("/") or value.startswith("//") or any(c in value for c in "\r\n?#"):
            raise ValueError("Use a path starting with /; enter the query separately")
        return value


@router.post("/request")
def analyze_request(body: RequestSample, request: Request, user=Depends(owner), redis=Depends(get_redis)):
    throttle(request, redis, identity=user.id, limit=30, namespace="request-analysis")
    query = redact_query(body.query)
    findings = [finding.json() for finding in evaluate(body.path, query, body.user_agent, body.status)]
    severity = next((level for level in ("high", "medium", "low")
                     if any(f["severity"] == level for f in findings)), "none")
    return {"verdict": "suspicious_pattern" if findings else "no_pattern_detected",
            "severity": severity, "findings": findings,
            "features": extract_features(body.path, query), "engine": "shield-rules-v1",
            "scope": "Single request; no traffic history, site honeytokens, body inspection or malware analysis.",
            "limitations": "A match is a review signal, not proof of compromise. No match does not establish safety. Named secret fields are excluded; inputs are not stored by this tool."}


class FileSample(BaseModel):
    # One MiB decoded; base64's expansion is bounded before decoding.
    content_base64: str = Field(min_length=4, max_length=4 * ((malware.MAX_FILE_BYTES + 2) // 3))


@router.post("/file")
def analyze_file(body: FileSample, request: Request, user=Depends(owner), redis=Depends(get_redis)):
    throttle(request, redis, identity=user.id, limit=5, namespace="file-analysis")
    try:
        content = base64.b64decode(body.content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, "Invalid base64 file content")
    if not 0 < len(content) <= malware.MAX_FILE_BYTES:
        raise HTTPException(413, "Choose a nonempty file no larger than 1 MiB")
    if not scan_slot.acquire(blocking=False):
        raise HTTPException(503, "File scanner is busy; try again shortly")
    try:
        result = malware.scan(content)
    except malware.ScanUnavailable:
        malware.invalidate_status()
        raise HTTPException(503, "File scanning is unavailable or incomplete. No safety verdict was produced.")
    finally:
        scan_slot.release()
    return {**result, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
            "limitations": "Signature scanning cannot detect every threat. No signature detected does not mean safe. Samples are not executed or retained by this tool."}


@router.get("/capabilities")
def capabilities(user=Depends(owner)):
    return {"request_engine": "shield-rules-v1", "file_engine": "ClamAV",
            "file_max_bytes": malware.MAX_FILE_BYTES,
            **malware.status(),
            "note": "Status can be cached for five seconds. Every scan checks the engine and signature age again."}
