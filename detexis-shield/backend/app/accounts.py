"""Owner authentication is independent of sensor API keys."""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from .auth import new_api_key
from .db import get_db
from .models import User, BrowserSession, Site, ApiKey
from .redis_store import get_redis
from .safe_fetch import domain_name, UnsafeTarget

router = APIRouter(prefix="/app/api")
pages = APIRouter()
hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
dummy = hasher.hash(secrets.token_urlsafe(32))
COOKIE = "__Host-dxs_session"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


def same_origin(request):
    origin = urlsplit(request.headers.get("origin", ""))
    if origin.scheme != "https" or origin.netloc != request.url.netloc:
        raise HTTPException(403, "Use this website over HTTPS to submit changes")


def throttle(request, redis):
    ip = request.client.host if request.client else "unknown"
    try:
        count = redis.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n", 1, "dxs:account:" + digest(ip))
    except RedisError:
        raise HTTPException(503, "Account access temporarily unavailable")
    if count > 10:
        raise HTTPException(429, "Please wait before trying again", headers={"Retry-After": "60"})


def issue_session(db, user, response):
    token = secrets.token_urlsafe(32)
    csrf = digest("csrf:" + token)
    db.add(BrowserSession(token_hash=digest(token), user_id=user.id, csrf_hash=digest(csrf),
                          expires_at=datetime.now(timezone.utc) + timedelta(hours=24)))
    db.commit()
    response.set_cookie(COOKIE, token, max_age=86400, secure=True, httponly=True, samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"email": user.email, "csrf_token": csrf}


def owner(request: Request, db=Depends(get_db)):
    token = request.cookies.get(COOKIE, "")
    session = db.get(BrowserSession, digest(token)) if 20 <= len(token) <= 128 else None
    now = datetime.now(timezone.utc)
    if session is None:
        raise HTTPException(401, "Sign in to continue")
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise HTTPException(401, "Session expired; sign in again")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        same_origin(request)
        if not hmac.compare_digest(session.csrf_hash, digest(request.headers.get("x-csrf-token", ""))):
            raise HTTPException(403, "Refresh your session before submitting")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Sign in to continue")
    return user


@router.post("/register", status_code=201)
def register(body: Credentials, request: Request, response: Response, db=Depends(get_db), redis=Depends(get_redis)):
    same_origin(request)
    throttle(request, redis)
    user = User(email=body.email, password_hash=hasher.hash(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to create account; try signing in")
    return issue_session(db, user, response)


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db=Depends(get_db), redis=Depends(get_redis)):
    same_origin(request)
    throttle(request, redis)
    user = db.scalar(select(User).where(User.email == body.email))
    try:
        hasher.verify(user.password_hash if user else dummy, body.password)
    except (VerificationError, InvalidHashError):
        raise HTTPException(401, "Email or password is incorrect")
    if user is None:
        raise HTTPException(401, "Email or password is incorrect")
    previous = request.cookies.get(COOKIE, "")
    old = db.get(BrowserSession, digest(previous)) if len(previous) <= 128 else None
    if old is not None:
        db.delete(old)
    return issue_session(db, user, response)


@router.get("/session")
def session_info(request: Request, response: Response, user=Depends(owner), db=Depends(get_db)):
    # Stable within this session so opening a second tab cannot break the first.
    csrf = digest("csrf:" + request.cookies[COOKIE])
    response.headers["Cache-Control"] = "no-store"
    return {"email": user.email, "csrf_token": csrf}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, user=Depends(owner), db=Depends(get_db)):
    db.delete(db.get(BrowserSession, digest(request.cookies[COOKIE])))
    db.commit()
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")


class NewSite(BaseModel):
    domain: str = Field(max_length=253)


@router.get("/sites")
def sites(user=Depends(owner), db=Depends(get_db)):
    def verified(site):
        if site.verified_at is None:
            return False
        stamp = site.verified_at
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp > datetime.now(timezone.utc) - timedelta(days=7)
    return [{"id": site.id, "domain": site.domain, "last_heartbeat": site.last_heartbeat, "verified": verified(site)}
            for site in db.scalars(select(Site).where(Site.owner_id == user.id).order_by(Site.created_at.desc()).limit(10))]


@router.post("/sites", status_code=201)
def add_site(body: NewSite, user=Depends(owner), db=Depends(get_db)):
    try:
        domain = domain_name(body.domain)
    except UnsafeTarget:
        raise HTTPException(422, "Enter a hostname such as example.com without a URL path")
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    if db.scalar(select(func.count()).select_from(Site).where(Site.owner_id == user.id)) >= 10:
        raise HTTPException(409, "This workspace supports up to ten websites")
    if db.scalar(select(Site).where(Site.owner_id == user.id, Site.domain == domain)):
        raise HTTPException(409, "This website is already in your workspace")
    site = Site(domain=domain, owner_id=user.id)
    db.add(site)
    db.flush()
    raw, prefix, hashed = new_api_key()
    db.add(ApiKey(site_id=site.id, prefix=prefix, key_hash=hashed))
    db.commit()
    return {"id": site.id, "domain": site.domain, "api_key": raw, "site_salt": secrets.token_urlsafe(32)}


def owned_site(db, user, site_id):
    site = db.scalar(select(Site).where(Site.id == site_id, Site.owner_id == user.id).with_for_update())
    if site is None:
        raise HTTPException(404, "Website not found")
    return site


@router.get("/sites/{site_id}/keys")
def list_keys(site_id: str, user=Depends(owner), db=Depends(get_db)):
    owned_site(db, user, site_id)
    return [{"id": key.id, "prefix": key.prefix, "revoked": key.revoked} for key in
            db.scalars(select(ApiKey).where(ApiKey.site_id == site_id).order_by(ApiKey.revoked, ApiKey.id.desc()).limit(50))]


@router.post("/sites/{site_id}/keys", status_code=201)
def create_key(site_id: str, user=Depends(owner), db=Depends(get_db)):
    owned_site(db, user, site_id)
    if db.scalar(select(func.count()).select_from(ApiKey).where(ApiKey.site_id == site_id, ApiKey.revoked.is_(False))) >= 5:
        raise HTTPException(409, "Revoke an unused key first; five active keys are allowed")
    raw, prefix, hashed = new_api_key()
    key = ApiKey(site_id=site_id, prefix=prefix, key_hash=hashed)
    db.add(key)
    db.commit()
    return {"id": key.id, "prefix": prefix, "api_key": raw}


@router.post("/sites/{site_id}/keys/{key_id}/revoke", status_code=204)
def revoke_key(site_id: str, key_id: int, user=Depends(owner), db=Depends(get_db)):
    owned_site(db, user, site_id)
    key = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.site_id == site_id))
    if key is None:
        raise HTTPException(404, "Key not found")
    key.revoked = True
    db.commit()


@router.post("/sites/{site_id}/verification")
def verification_challenge(site_id: str, user=Depends(owner), db=Depends(get_db)):
    from .scan_api import start_verification
    return start_verification(site=owned_site(db, user, site_id), db=db)


@router.post("/sites/{site_id}/verify")
def verify_domain(site_id: str, user=Depends(owner), db=Depends(get_db), redis=Depends(get_redis)):
    from .scan_api import confirm_verification
    return confirm_verification(site=owned_site(db, user, site_id), db=db, redis=redis)


@router.post("/sites/{site_id}/scans", status_code=202)
def scan_domain(site_id: str, user=Depends(owner), db=Depends(get_db), redis=Depends(get_redis)):
    from .scan_api import request_scan
    return request_scan(site=owned_site(db, user, site_id), db=db, redis=redis)


@pages.get("/app")
def account_page(request: Request):
    from .dashboard import templates
    return templates.TemplateResponse(request=request, name="account.html", context={})


@pages.get("/")
def home():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/app", status_code=303)


@pages.get("/app/sites/{site_id}")
def site_dashboard(site_id: str, request: Request, user=Depends(owner), db=Depends(get_db)):
    from .dashboard import templates, context
    site = db.scalar(select(Site).where(Site.id == site_id, Site.owner_id == user.id))
    if site is None:
        raise HTTPException(404, "Website not found")
    return templates.TemplateResponse(request=request, name="dashboard.html", context={**context(db, site), "workspace_url": "/app", "feed_url": f"/app/sites/{site.id}/feed"})


@pages.get("/app/sites/{site_id}/feed")
def site_feed(site_id: str, request: Request, user=Depends(owner), db=Depends(get_db)):
    from .dashboard import templates, context
    site = db.scalar(select(Site).where(Site.id == site_id, Site.owner_id == user.id))
    if site is None:
        raise HTTPException(404, "Website not found")
    return templates.TemplateResponse(request=request, name="feed.html", context=context(db, site))
