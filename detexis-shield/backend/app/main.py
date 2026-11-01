from datetime import datetime, timezone
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql, sqlite
from .auth import current_site
from .db import Base, engine, get_db
from .models import Event, Site
from .schemas import BatchIn

app = FastAPI(title="Detexis Shield API")
Base.metadata.create_all(engine)  # TODO(you): replace with Alembic migrations


def insert_ignore(db: Session, rows: list[dict]):
    """Idempotent insert: duplicate event_ids are skipped, so retries are safe."""
    dialect = postgresql if db.bind.dialect.name == "postgresql" else sqlite
    stmt = dialect.insert(Event).values(rows).on_conflict_do_nothing(index_elements=["event_id"])
    db.execute(stmt)
    db.commit()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/v1/events", status_code=202)
def ingest(batch: BatchIn, site: Site = Depends(current_site), db: Session = Depends(get_db)):
    # site_id always comes from the API key, never from the payload (tenant isolation).
    rows = [{**e.model_dump(), "site_id": site.id} for e in batch.events]
    if rows:
        insert_ignore(db, rows)
    # TODO(you): enqueue event_ids to Redis/RQ for rules -> ML -> correlation workers.
    return {"accepted": len(rows)}


@app.get("/v1/config")
def config(site: Site = Depends(current_site)):
    # Blocking stays disabled in v1 regardless of the stored mode.
    return {"mode": "monitor", "rules_version": 0, "honeytokens": ["/.env", "/admin-backup"]}


@app.post("/v1/heartbeat")
def heartbeat(site: Site = Depends(current_site), db: Session = Depends(get_db)):
    site.last_heartbeat = datetime.now(timezone.utc)
    db.add(site)
    db.commit()
    return {"ok": True}
