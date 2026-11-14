from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.db import SessionLocal
from app.maintenance import purge
from app.models import Event, Scan
from test_pipeline import seed
from test_smoke import make_site


def test_retention_removes_old_events_and_scans_but_keeps_recent():
    site, _ = make_site("retention.test")
    old = datetime.now(timezone.utc) - timedelta(days=40)
    expired = seed(site, "/old", received_at=old)
    recent = seed(site, "/recent")
    with SessionLocal() as db:
        scan = Scan(site_id=site, created_at=old, status="complete", result={})
        db.add(scan)
        db.commit()
        scan_id = scan.id
    purge(30)
    with SessionLocal() as db:
        assert db.get(Event, (expired, site)) is None
        assert db.get(Event, (recent, site)) is not None
        assert db.get(Scan, scan_id) is None
