from datetime import datetime, timezone
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql, sqlite
from .auth import current_site
from .db import get_db
from .models import Event, Site
from .schemas import BatchIn
from .redis_store import get_redis
from .rate_limit import enforce_limit
from .body_limit import IngestBodyLimit
from .dashboard import router as dashboard_router
from .scan_api import router as scan_router
from .accounts import router as account_router, pages as account_pages
from pathlib import Path
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Detexis Shield API")
app.add_middleware(IngestBodyLimit)
app.include_router(dashboard_router)
app.include_router(scan_router)
app.include_router(account_router)
app.include_router(account_pages)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    if request.url.path.startswith(("/dashboard", "/v1/", "/app")):
        response.headers["Cache-Control"] = "no-store"
    return response


def insert_ignore(db: Session, rows: list[dict]):
    """Idempotent insert: duplicate event_ids are skipped, so retries are safe."""
    dialect = postgresql if db.bind.dialect.name == "postgresql" else sqlite
    stmt = dialect.insert(Event).values(rows).on_conflict_do_nothing(index_elements=["site_id", "event_id"])
    inserted = db.execute(stmt.returning(Event.event_id)).scalars().all()
    db.commit()
    return inserted


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/ready")
def ready(db: Session = Depends(get_db), redis=Depends(get_redis)):
    from fastapi import HTTPException
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        redis.ping()
    except Exception:
        raise HTTPException(503, "dependencies unavailable")
    return {"ok": True}


@app.post("/v1/events", status_code=202)
def ingest(batch: BatchIn, site: Site = Depends(current_site), db: Session = Depends(get_db),
           redis=Depends(get_redis)):
    enforce_limit(redis, site.id, len(batch.events))
    # site_id always comes from the API key, never from the payload (tenant isolation).
    rows = [{**e.model_dump(), "site_id": site.id} for e in batch.events]
    inserted = insert_ignore(db, rows) if rows else []
    from .worker import enqueue_batch
    from redis.exceptions import RedisError
    queued = True
    if inserted:
        try:
            enqueue_batch(site.id, inserted, redis)
        except RedisError:
            queued = False  # Durable pending rows are recovered by maintenance.
    return {"accepted": len(inserted), "duplicates": len(rows) - len(inserted), "queued": queued}


@app.get("/v1/config")
def config(site: Site = Depends(current_site)):
    # Blocking stays disabled in v1 regardless of the stored mode.
    return {"mode": "monitor", "rules_version": 1, "honeytokens": site.honeytokens}


@app.post("/v1/heartbeat")
def heartbeat(site: Site = Depends(current_site), db: Session = Depends(get_db)):
    site.last_heartbeat = datetime.now(timezone.utc)
    db.add(site)
    db.commit()
    return {"ok": True}
