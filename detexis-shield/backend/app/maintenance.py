"""Run every minute in its own process: recover jobs, deliver alerts, retain data."""
import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from .alerts import send_pending
from .db import SessionLocal
from .models import Alert, Event, HourBucket, Incident, Scan
from .worker import recover_pending


def purge(days=None):
    days = int(os.getenv("RETENTION_DAYS", "30")) if days is None else days
    if days < 7:
        raise ValueError("retention must be at least seven days")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with SessionLocal() as db:
        old = select(Incident.id).where(Incident.last_seen < cutoff)
        db.execute(delete(Alert).where(Alert.incident_id.in_(old)))
        db.execute(delete(Incident).where(Incident.last_seen < cutoff))
        db.execute(delete(Event).where(Event.received_at < cutoff))
        db.execute(delete(HourBucket).where(HourBucket.hour < cutoff))
        db.execute(delete(Scan).where(Scan.created_at < cutoff))
        db.commit()


def tick():
    recover_pending()
    send_pending()
    from .scan_jobs import schedule_rescans
    from .redis_store import get_redis
    schedule_rescans(get_redis())
    purge()


if __name__ == "__main__":
    import logging
    while True:
        try:
            tick()
        except Exception:
            logging.error("Maintenance failed; will retry next minute")
        time.sleep(60)
