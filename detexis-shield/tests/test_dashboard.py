from fastapi.testclient import TestClient
from app.main import app
from test_smoke import make_site
from test_pipeline import seed
from test_accounts import register


def test_dashboard_requires_auth_and_escapes_attacker_fields():
    site, key = make_site("dashboard.test")
    seed(site, '<img src=x onerror="alert(1)">')
    other, other_key = make_site("other-dashboard.test")
    seed(other, "/tenant-secret-marker")
    with TestClient(app) as client:
        assert client.get("/dashboard").status_code == 401
        response = client.get("/dashboard", auth=("site", key))
        assert response.status_code == 200
        assert '<img src=x' not in response.text
        assert "&lt;img" in response.text
        assert "tenant-secret-marker" not in response.text
        assert "tenant-secret-marker" in client.get("/dashboard/feed", auth=("site", other_key)).text
        assert response.headers["Cache-Control"] == "no-store"
        assert "unsafe-inline" not in response.headers["Content-Security-Policy"]
        assert 'id="feed-status" role="status"' in response.text
        assert 'id="refresh-feed"' in response.text
        assert '/static/dashboard.js?v=' in response.text
        assert '"timeout":10000' in response.text


def test_dashboard_reports_stale_heartbeat_and_expired_verification():
    from datetime import datetime, timedelta, timezone
    from app.db import SessionLocal
    from app.models import Scan, Site
    site_id, key = make_site("stale-sensor.test")
    with SessionLocal() as db:
        site = db.get(Site, site_id)
        site.last_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=4)
        site.verified_at = datetime.now(timezone.utc) - timedelta(days=8)
        db.add(Scan(site_id=site_id, status="unverified"))
        db.commit()
    with TestClient(app) as client:
        page = client.get("/dashboard", auth=("site", key))
        assert "Heartbeat overdue" in page.text
        assert "Verification expired" in page.text
        assert "<strong>Canceled</strong>" in page.text
        assert "Domain verification changed or expired before this scan could run." in page.text


def test_dashboard_describes_historical_correlation_without_asserting_order():
    from app.db import SessionLocal
    from app.models import Incident

    site, key = make_site("historical-correlation.test")
    with SessionLocal() as db:
        db.add(Incident(site_id=site, ip_hash="a" * 64, bucket=1, severity="high",
                        rules=["honeytoken", "xss"], correlations=["recon_to_exploit"]))
        db.commit()
    with TestClient(app) as client:
        page = client.get("/dashboard", auth=("site", key))
        assert page.status_code == 200
        assert "Reconnaissance and exploit indicators observed (order unverified)" in page.text
        assert "Reconnaissance observed before an exploit indicator" not in page.text


def test_dashboard_keeps_in_app_alerts_available_independently_of_external_delivery(isolated_redis):
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Alert
    from app.worker import process_batch

    with TestClient(app, base_url="https://testserver") as client:
        headers = register(client, "dashboard-alert-delivery")
        created = client.post("/app/api/sites", headers=headers, json={"domain": "alerts.example"}).json()
        page = f"/app/sites/{created['id']}/feed"
        assert "Latest external alert: No attempts recorded" in client.get(page).text
        event = seed(created["id"], "/.env")
        assert process_batch(created["id"], [event], isolated_redis) == 1
        assert "Latest external alert: Awaiting delivery check" in client.get(page).text
        for state, label in (("unconfigured", "No external destination"),
                             ("failed", "External delivery failed"), ("sent", "Delivered externally")):
            with SessionLocal() as db:
                db.scalar(select(Alert).where(Alert.site_id == created["id"])).status = state
                db.commit()
            response = client.get(page)
            assert "Latest external alert: " + label in response.text
            assert '<a href="/app/inbox">Review incident inbox</a>' in response.text
            assert client.get("/app/api/inbox").json()["incidents"]


def test_owner_dashboard_distinguishes_installation_and_processing_states():
    from datetime import datetime, timedelta, timezone
    from app.db import SessionLocal
    from app.models import Event

    with TestClient(app, base_url="https://testserver") as client:
        headers = register(client, "dashboard-connection")
        created = client.post("/app/api/sites", headers=headers, json={"domain": "dashboard-connection.test"})
        assert created.status_code == 201
        site = created.json()
        path = f"/app/sites/{site['id']}"
        initial = client.get(path)
        assert initial.status_code == 200
        assert "Open the sensor installation guide" in initial.text

        sensor_headers = {"X-API-Key": site["api_key"]}
        assert client.post("/v1/heartbeat", headers=sensor_headers).status_code == 200
        assert "The sensor has checked in" in client.get(path + "/feed").text

        event_id = seed(site["id"], "/first-request")
        assert "1 request is awaiting analysis in this feed" in client.get(path + "/feed").text
        with SessionLocal() as db:
            row = db.get(Event, (event_id, site["id"]))
            row.received_at = datetime.now(timezone.utc) - timedelta(minutes=2)
            db.commit()
        newer_event_id = seed(site["id"], "/newer-completed-request")
        with SessionLocal() as db:
            db.get(Event, (newer_event_id, site["id"])).processed_at = datetime.now(timezone.utc)
            db.commit()
        feed = client.get(path + "/feed").text
        assert "/newer-completed-request" in feed
        assert "ask your Shield operator to check the workers" in feed
        with SessionLocal() as db:
            db.get(Event, (event_id, site["id"])).processed_at = datetime.now(timezone.utc)
            db.commit()
        assert "Shield analyzed all requests shown" in client.get(path + "/feed").text
