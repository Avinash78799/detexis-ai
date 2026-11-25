from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.models import User, BrowserSession
from app.db import SessionLocal
from test_smoke import event, make_site

ORIGIN = {"Origin": "https://testserver"}


def register(client, name):
    response = client.post("/app/api/register", headers=ORIGIN,
                           json={"email": name + "@example.test", "password": "long-enough-test-passphrase"})
    assert response.status_code == 201, response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    return {**ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


def test_accounts_csrf_site_isolation_and_logout():
    make_site("existing-unclaimed.test")
    with TestClient(app, base_url="https://testserver") as a, TestClient(app, base_url="https://testserver") as b:
        headers = register(a, "owner-a")
        register(b, "owner-b")
        assert a.post("/app/api/sites", headers=ORIGIN, json={"domain": "owned.example"}).status_code == 403
        created = a.post("/app/api/sites", headers=headers, json={"domain": "owned.example"})
        assert created.status_code == 201, created.text
        assert created.json()["api_key"].startswith("dxs_")
        site_id = created.json()["id"]
        assert a.get(f"/app/sites/{site_id}").status_code == 200
        assert a.get(f"/app/sites/{site_id}/feed").status_code == 200
        assert b.get(f"/app/sites/{site_id}").status_code == 404
        assert b.get(f"/app/sites/{site_id}/feed").status_code == 404
        assert b.get(f"/app/api/sites/{site_id}/keys").status_code == 404
        b_csrf = b.get("/app/api/session").json()["csrf_token"]
        assert b.post(f"/app/api/sites/{site_id}/verification", headers={**ORIGIN, "X-CSRF-Token": b_csrf}, json={}).status_code == 404
        assert a.post(f"/app/api/sites/{site_id}/scans", headers=headers, json={}).status_code == 403
        challenge = a.post(f"/app/api/sites/{site_id}/verification", headers=headers, json={})
        assert challenge.status_code == 200 and challenge.json()["record"] == "_detexis.owned.example"
        replacement = a.post(f"/app/api/sites/{site_id}/keys", headers=headers, json={})
        assert replacement.status_code == 201
        sensor_key = replacement.json()["api_key"]
        assert a.get("/v1/config", headers={"X-API-Key": sensor_key}).status_code == 200
        key_id = replacement.json()["id"]
        assert a.post(f"/app/api/sites/{site_id}/keys/{key_id}/revoke", headers=headers, json={}).status_code == 204
        assert a.get("/v1/config", headers={"X-API-Key": sensor_key}).status_code == 401
        assert a.get("/app/api/sites").status_code == 200
        # Another tab can restore the same session without invalidating CSRF.
        assert a.get("/app/api/session").json()["csrf_token"] == headers["X-CSRF-Token"]
        assert [site["domain"] for site in a.get("/app/api/sites").json()] == ["owned.example"]
        assert b.get("/app/api/sites").json() == []
        assert a.post("/app/api/logout", headers=headers).status_code == 204
        assert a.get("/app/api/sites").status_code == 401
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "owner-a@example.test"))
        assert user.password_hash.startswith("$argon2id$")
        assert db.scalar(select(BrowserSession).where(BrowserSession.user_id == user.id)) is None


def test_cross_origin_registration_rejected_and_login_rate_limited():
    with TestClient(app, base_url="https://testserver") as client:
        body = {"email": "rate@example.test", "password": "long-enough-test-passphrase"}
        assert client.post("/app/api/register", headers={"Origin": "https://evil.test"}, json=body).status_code == 403
        for _ in range(10):
            assert client.post("/app/api/login", headers=ORIGIN, json=body).status_code == 401
        assert client.post("/app/api/login", headers=ORIGIN, json=body).status_code == 429


def test_owner_site_sensor_key_can_report_but_cannot_manage_the_site(monkeypatch):
    with TestClient(app, base_url="https://testserver") as owner, TestClient(app) as sensor:
        owner_headers = register(owner, "sensor-scope-owner")
        created = owner.post("/app/api/sites", headers=owner_headers, json={"domain":"sensor-scope.example"})
        assert created.status_code == 201
        site = created.json()
        key = site["api_key"]
        headers = {"X-API-Key":key}
        assert sensor.post("/v1/heartbeat", headers=headers).status_code == 200
        assert sensor.get("/v1/config", headers=headers).status_code == 200
        assert sensor.post("/v1/events", headers=headers, json={"events":[event("/health")]}).status_code == 202

        for path in ("/dashboard", "/dashboard/feed"):
            response = sensor.get(path, auth=("site", key))
            assert response.status_code == 403 and "www-authenticate" not in response.headers
        assert sensor.get("/v1/incidents", headers=headers).status_code == 403
        assert sensor.get("/v1/scans/fixture", headers=headers).status_code == 403
        for path in ("/v1/domain/verification", "/v1/domain/verify", "/v1/scans"):
            assert sensor.post(path, headers=headers).status_code == 403

        path = f"/app/api/sites/{site['id']}"
        challenge = owner.post(path + "/verification", headers=owner_headers).json()
        monkeypatch.setattr("app.scan_api.txt", lambda _domain: [challenge["value"]])
        assert owner.post(path + "/verify", headers=owner_headers).status_code == 200
        assert owner.post(path + "/scans", headers=owner_headers).status_code == 202
        assert owner.get(f"/app/sites/{site['id']}").status_code == 200
