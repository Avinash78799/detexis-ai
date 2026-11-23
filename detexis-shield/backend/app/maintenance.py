"""Run every minute in its own process: recover jobs, deliver alerts, retain data."""
import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from .alerts import send_pending
from .db import SessionLocal
from .models import Alert, Event, HourBucket, Incident, Scan, BrowserSession, IncidentAction, SensorHealthAlert, Site
from .worker import recover_pending


def purge(days=None):
    days = int(os.getenv("RETENTION_DAYS", "30")) if days is None else days
    if days < 7:
        raise ValueError("retention must be at least seven days")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with SessionLocal() as db:
        db.execute(delete(BrowserSession).where(BrowserSession.expires_at < datetime.now(timezone.utc)))
        db.commit()
        sites = list(db.scalars(select(Site.id).order_by(Site.id)))
    for site_id in sites:
        with SessionLocal() as db:
            # Match worker/triage's Site -> Incident lock order. NO KEY UPDATE
            # permits ingest's foreign-key checks; skip active sites and retry
            # them on the next maintenance pass instead of blocking processing.
            site = db.scalar(select(Site.id).where(Site.id == site_id)
                             .with_for_update(key_share=True, skip_locked=True))
            if site is None:
                continue
            old = select(Incident.id).where(Incident.site_id == site_id, Incident.last_seen < cutoff)
            db.execute(delete(IncidentAction).where(IncidentAction.incident_id.in_(old)))
            db.execute(delete(Alert).where(Alert.incident_id.in_(old)))
            db.execute(delete(Incident).where(Incident.site_id == site_id, Incident.last_seen < cutoff))
            db.execute(delete(Event).where(Event.site_id == site_id, Event.received_at < cutoff))
            # Keep the complete boundary hour for the seven-day baseline.
            bucket_cutoff = cutoff.replace(minute=0, second=0, microsecond=0)
            db.execute(delete(HourBucket).where(HourBucket.site_id == site_id, HourBucket.hour < bucket_cutoff))
            db.execute(delete(Scan).where(Scan.site_id == site_id, Scan.created_at < cutoff))
            db.execute(delete(SensorHealthAlert).where(SensorHealthAlert.site_id == site_id,
                                                      SensorHealthAlert.resolved_at < cutoff))
            # A failure rolls back this site's entire graph; completed sites
            # remain cleaned and later passes retry incomplete sites.
            db.commit()


def tick():
    recover_pending()
    from .sensor_health import check_sensor_health
    check_sensor_health()
    send_pending()
    from .scan_jobs import schedule_rescans
    from .redis_store import get_redis
    schedule_rescans(get_redis())
    purge()


def run_once():
    tick()
    # Refresh only after every maintenance operation completed successfully.
    from .maintenance_health import record_success
    from .redis_store import get_redis
    record_success(get_redis())


if __name__ == "__main__":
    import logging
    from .maintenance_health import progress_key
    from .redis_store import get_redis
    # A restarted process must earn its own healthy status.
    get_redis().delete(progress_key())
    while True:
        try:
            run_once()
        except Exception:
            logging.error("Maintenance failed; will retry next minute")
        time.sleep(60)
