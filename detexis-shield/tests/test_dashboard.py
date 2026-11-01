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
