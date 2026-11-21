from fastapi.testclient import TestClient
from app.main import app
from test_smoke import make_site
from test_pipeline import seed


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
    from app.models import Site
    site_id, key = make_site("stale-sensor.test")
    with SessionLocal() as db:
        site = db.get(Site, site_id)
        site.last_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=4)
        site.verified_at = datetime.now(timezone.utc) - timedelta(days=8)
        db.commit()
    with TestClient(app) as client:
        page = client.get("/dashboard", auth=("site", key))
        assert "Heartbeat overdue" in page.text
        assert "Verification expired" in page.text
