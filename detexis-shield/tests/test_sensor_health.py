from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.main import app
from app.models import Site, ApiKey, SensorHealthAlert, Incident
from app.sensor_health import check_sensor_health
from app.maintenance import purge
from test_accounts import register
from test_smoke import make_site


def history(site):
    with SessionLocal() as db:
        return db.scalars(select(SensorHealthAlert).where(SensorHealthAlert.site_id == site).order_by(SensorHealthAlert.opened_at)).all()


def heartbeat_at(site, value):
    with SessionLocal() as db:
        db.get(Site, site).last_heartbeat = value
        if value:
            for key in db.scalars(select(ApiKey).where(ApiKey.site_id == site)):
                key.created_at = value-timedelta(seconds=1)
        db.commit()


def test_heartbeat_gap_lifecycle_deduplication_and_tenant_scoping():
    now = datetime.now(timezone.utc)
    with TestClient(app, base_url="https://testserver") as a, TestClient(app, base_url="https://testserver") as b:
        headers = register(a,"sensor-health-owner")
        register(b,"sensor-health-other")
        created = a.post("/app/api/sites", headers=headers, json={"domain":"health-owned.example"}).json()
        site = created["id"]
        heartbeat_at(site, now-timedelta(minutes=4))
        check_sensor_health(at=now)
        check_sensor_health(at=now)
        assert len(history(site)) == 1
        feed = a.get("/app/api/sensor-health")
        assert feed.headers["cache-control"] == "no-store"
        assert feed.json()["open_count"] == 1
        assert feed.json()["alerts"][0]["site_id"] == site
        assert created["api_key"] not in feed.text
        assert b.get("/app/api/sensor-health").json()["alerts"] == []
        assert b.get("/app/api/sensor-health").json()["open_count"] == 0
        page = a.get("/app/sensor-health")
        assert page.status_code == 200 and "HEARTBEAT OVERDUE" in page.text
        assert "does not prove" in page.text and "health-owned.example" in page.text
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(Incident).where(Incident.site_id == site)) == 0
            # The database also enforces the one-open-gap invariant.
            db.add(SensorHealthAlert(site_id=site, heartbeat_at=now-timedelta(minutes=4)))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        assert a.post("/v1/heartbeat", headers={"X-API-Key":created["api_key"]}).status_code == 200
        check_sensor_health(at=now+timedelta(seconds=5))
        assert history(site)[0].resolution == "heartbeat_resumed"
        assert a.get("/app/api/sensor-health").json()["open_count"] == 0
        heartbeat_at(site, now-timedelta(minutes=4))
        check_sensor_health(at=now+timedelta(seconds=6))
        assert len(history(site)) == 2
        with SessionLocal() as db:
            for key in db.scalars(select(ApiKey).where(ApiKey.site_id == site)):
                key.revoked = True
            db.commit()
        check_sensor_health(at=now+timedelta(seconds=7))
        assert history(site)[-1].resolution == "monitoring_disabled"
        assert a.get("/app/api/sensor-health").json()["open_count"] == 0


def test_never_connected_recent_and_grace_boundary_do_not_alert():
    now = datetime.now(timezone.utc)
    sites = [make_site("health-boundary-"+str(i)+".example")[0] for i in range(3)]
    heartbeat_at(sites[1], now-timedelta(seconds=179))
    heartbeat_at(sites[2], now-timedelta(seconds=180))
    check_sensor_health(at=now)
    assert all(not history(site) for site in sites)


def test_newly_provisioned_key_gets_configuration_grace_without_hiding_open_gap():
    now = datetime.now(timezone.utc)
    site, _ = make_site("health-reconfigure.example")
    heartbeat_at(site, now-timedelta(minutes=10))
    with SessionLocal() as db:
        db.scalar(select(ApiKey).where(ApiKey.site_id == site)).created_at = now
        db.commit()
    check_sensor_health(at=now)
    assert history(site) == []
    check_sensor_health(at=now+timedelta(minutes=4))
    assert len(history(site)) == 1
    with SessionLocal() as db:
        db.scalar(select(ApiKey).where(ApiKey.site_id == site)).created_at = now+timedelta(minutes=4)
        db.commit()
    check_sensor_health(at=now+timedelta(minutes=4))
    assert history(site)[0].resolved_at is None


def test_open_gaps_do_not_starve_new_transitions_in_bounded_batches():
    now = datetime.now(timezone.utc)
    sites = [make_site("health-batch-"+str(i)+".example")[0] for i in range(3)]
    for site in sites:
        heartbeat_at(site, now-timedelta(minutes=4))
    for _ in range(10):
        check_sensor_health(at=now,limit=1)
    assert all(len(history(site)) == 1 for site in sites)


def test_health_history_retention_keeps_open_and_recent_signals():
    now = datetime.now(timezone.utc)
    site, _ = make_site("health-retention.example")
    old = now-timedelta(days=40)
    with SessionLocal() as db:
        expired = SensorHealthAlert(site_id=site,opened_at=old,heartbeat_at=old,resolved_at=old,resolution="heartbeat_resumed")
        active = SensorHealthAlert(site_id=site,opened_at=old,heartbeat_at=old)
        recent = SensorHealthAlert(site_id=site,opened_at=now,heartbeat_at=now,resolved_at=now,resolution="heartbeat_resumed")
        db.add_all([expired,active,recent]); db.commit()
        expired_id = expired.id
    purge(30)
    assert len(history(site)) == 2 and all(row.id != expired_id for row in history(site))


def test_health_navigation_requires_authentication_and_bounds_output():
    with TestClient(app,base_url="https://testserver") as client:
        assert client.get("/app/api/sensor-health").status_code == 401
        response = client.get("/app/sensor-health",headers={"Accept":"text/html"},follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/app?next=%2Fapp%2Fsensor-health"
        register(client,"health-page-owner")
        assert client.get("/app/api/sensor-health?limit=101").status_code == 422
    with pytest.raises(ValueError):
        check_sensor_health(at=datetime.now())
