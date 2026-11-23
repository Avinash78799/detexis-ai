from datetime import datetime, timedelta, timezone
import pytest
from app.db import SessionLocal
from app.maintenance import purge
from app.models import Event, Scan, HourBucket, Site
from app.worker import baseline_threshold
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


@pytest.mark.parametrize("days", [7, 30])
@pytest.mark.parametrize("minute", [0, 37, 59])
def test_retention_preserves_boundary_hour_for_each_sites_baseline(monkeypatch, days, minute):
    import app.maintenance as maintenance

    stamp = datetime(2026, 11, 23, 12, minute, 15, tzinfo=timezone.utc)
    hour = stamp.replace(minute=0, second=0, microsecond=0)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return stamp.astimezone(tz) if tz else stamp.replace(tzinfo=None)

    monkeypatch.setattr(maintenance, "datetime", Clock)
    sites = [make_site(f"retention-hour-{days}-{index}.test")[0] for index in range(2)]
    with SessionLocal() as db:
        for site_id, count in zip(sites, [200, 300]):
            db.get(Site, site_id).created_at = hour - timedelta(days=40)
            for day in range(1, days + 1):
                db.add(HourBucket(site_id=site_id, hour=hour - timedelta(days=day), count=count))
            db.add(HourBucket(site_id=site_id, hour=hour - timedelta(days=days, hours=1), count=999))
        db.commit()

    # Raw request retention still uses the exact cutoff, not the rounded hour.
    expired = seed(sites[0], "/expired-within-boundary-hour", received_at=hour - timedelta(days=days))
    recent = seed(sites[0], "/within-retention", received_at=stamp - timedelta(days=days) + timedelta(seconds=1))
    purge(days)

    with SessionLocal() as db:
        for site_id, count in zip(sites, [200, 300]):
            assert db.get(HourBucket, (site_id, hour - timedelta(days=days))) is not None
            assert db.get(HourBucket, (site_id, hour - timedelta(days=days, hours=1))) is None
            assert baseline_threshold(db, db.get(Site, site_id), hour) == count
        assert db.get(Event, (expired, sites[0])) is None
        assert db.get(Event, (recent, sites[0])) is not None
