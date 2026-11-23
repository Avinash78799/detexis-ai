from datetime import datetime, timedelta, timezone
import pytest
from app.db import SessionLocal, engine
from app.maintenance import purge
from app.models import Alert, Event, Incident, IncidentAction, Scan, HourBucket, Site
from app.worker import baseline_threshold, process_batch
from sqlalchemy import select, event as sql_events
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


@pytest.mark.parametrize("interrupt_cleanup", [False, True])
def test_retention_removes_expired_incident_history_and_preserves_recent_tenants(isolated_redis, interrupt_cleanup):
    stamp = datetime.now(timezone.utc)
    expired_at = stamp - timedelta(days=40)
    sites = [make_site(f"retention-history-{index}.test")[0] for index in range(2)]
    expected = {}
    for site_id in sites:
        old = seed(site_id, "/.env", received_at=expired_at)
        recent = seed(site_id, "/.env", received_at=stamp)
        assert process_batch(site_id, [old, recent], isolated_redis) == 2
        with SessionLocal() as db:
            rows = db.scalars(select(Incident).where(Incident.site_id == site_id)
                              .order_by(Incident.last_seen)).all()
            assert len(rows) == 2
            for row in rows:
                row.status = "acknowledged"
                db.add(IncidentAction(incident_id=row.id, previous_status="open",
                                      status="acknowledged", note="Retained review history"))
            db.commit()
            expected[site_id] = (old, recent, rows[0].id, rows[1].id)

    if interrupt_cleanup:
        def fail_parent_delete(connection, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("DELETE FROM INCIDENTS "):
                raise RuntimeError("Synthetic cleanup interruption")

        sql_events.listen(engine, "before_cursor_execute", fail_parent_delete)
        try:
            with pytest.raises(RuntimeError, match="Synthetic cleanup interruption"):
                purge(30)
        finally:
            sql_events.remove(engine, "before_cursor_execute", fail_parent_delete)
        with SessionLocal() as db:
            for site_id, (old, recent, expired_incident, live_incident) in expected.items():
                for event_id in [old, recent]:
                    assert db.get(Event, (event_id, site_id)) is not None
                for incident_id in [expired_incident, live_incident]:
                    assert db.get(Incident, incident_id) is not None
                    assert len(db.scalars(select(Alert).where(Alert.incident_id == incident_id)).all()) == 1
                    assert len(db.scalars(select(IncidentAction).where(IncidentAction.incident_id == incident_id)).all()) == 1

    purge(30)
    # Repeating cleanup must preserve the same live records and review history.
    purge(30)
    with SessionLocal() as db:
        for site_id, (old, recent, expired_incident, live_incident) in expected.items():
            assert db.get(Event, (old, site_id)) is None
            assert db.get(Event, (recent, site_id)).processed_at is not None
            assert db.get(Incident, expired_incident) is None
            live = db.get(Incident, live_incident)
            assert live.site_id == site_id and live.status == "acknowledged" and live.event_count == 1
            assert not db.scalars(select(IncidentAction).where(IncidentAction.incident_id == expired_incident)).all()
            actions = db.scalars(select(IncidentAction).where(IncidentAction.incident_id == live_incident)).all()
            assert len(actions) == 1 and actions[0].note == "Retained review history"
            assert not db.scalars(select(Alert).where(Alert.incident_id == expired_incident)).all()
            alerts = db.scalars(select(Alert).where(Alert.incident_id == live_incident)).all()
            assert len(alerts) == 1 and alerts[0].site_id == site_id
