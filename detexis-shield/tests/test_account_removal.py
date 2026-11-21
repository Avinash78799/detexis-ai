from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError

from app.main import app
from app.db import SessionLocal
from app.models import (Alert, ApiKey, BrowserSession, Event, HourBucket, Incident,
                        IncidentAction, Scan, SensorHealthAlert, Site, User)
from app.worker import process_batch
from test_accounts import register, ORIGIN
from test_smoke import event

PASSWORD = "long-enough-test-passphrase"
BODY = {"password": PASSWORD, "confirmation": "DELETE"}


def populated_owner(client, redis):
    headers = register(client, "remove-" + uuid.uuid4().hex)
    created = client.post("/app/api/sites", headers=headers, json={"domain": "removal.example"}).json()
    item = event("/.env")
    assert client.post("/v1/events", headers={"X-API-Key": created["api_key"]}, json={"events": [item]}).status_code == 202
    process_batch(created["id"], [item["event_id"]], redis)
    incident = client.get("/app/api/inbox").json()["incidents"][0]["id"]
    assert client.post(f"/app/api/incidents/{incident}/status", headers=headers,
                       json={"status": "acknowledged", "note": "Private owner review"}).status_code == 200
    with SessionLocal() as db:
        user_id = db.get(Site, created["id"]).owner_id
        stamp = datetime.now(timezone.utc)
        db.add_all([Scan(site_id=created["id"], status="complete", result={"fixture": True}),
                    SensorHealthAlert(site_id=created["id"], heartbeat_at=stamp, opened_at=stamp),
                    SensorHealthAlert(site_id=created["id"], heartbeat_at=stamp-timedelta(hours=1),
                                      opened_at=stamp-timedelta(hours=1), resolved_at=stamp,
                                      resolution="heartbeat_resumed")])
        db.commit()
    return headers, created, user_id, incident


def test_account_removal_erases_owned_history_sessions_and_keys_only(isolated_redis):
    with TestClient(app, base_url="https://testserver") as a, TestClient(app, base_url="https://testserver") as b, TestClient(app, base_url="https://testserver") as second_device:
        headers, first, user_id, incident = populated_owner(a, isolated_redis)
        other_headers, other, other_user, other_incident = populated_owner(b, isolated_redis)
        extra = a.post("/app/api/sites", headers=headers, json={"domain": "second-removal.example"}).json()
        with SessionLocal() as db:
            other_password = db.get(User, other_user).password_hash
            own_email = db.get(User, user_id).email
            original_session = db.scalar(select(BrowserSession.token_hash).where(BrowserSession.user_id == user_id))
        assert second_device.post("/app/api/login", headers=ORIGIN, json={"email":own_email,"password":PASSWORD}).status_code == 200
        response = a.post("/app/api/account/delete", headers=headers, json={**BODY, "user_id": other_user})
        assert response.status_code == 204, response.text
        assert "Max-Age=0" in response.headers["set-cookie"]
        assert a.get("/app/api/sites").status_code == 401
        assert second_device.get("/app/api/session").status_code == 401
        for key in [first["api_key"], extra["api_key"]]:
            assert a.get("/v1/config", headers={"X-API-Key": key}).status_code == 401
        assert b.get("/v1/config", headers={"X-API-Key": other["api_key"]}).status_code == 200
        assert b.get(f"/app/api/incidents/{other_incident}").status_code == 200
        assert len(b.get("/app/api/sites").json()) == 1
        with SessionLocal() as db:
            assert db.get(User, user_id) is None
            assert db.get(BrowserSession, original_session) is None
            assert db.scalar(select(func.count()).select_from(BrowserSession).where(BrowserSession.user_id == user_id)) == 0
            assert db.get(Incident, incident) is None
            assert db.scalar(select(IncidentAction).where(IncidentAction.incident_id == incident)) is None
            assert db.get(User, other_user).password_hash == other_password
            for model in [Alert, ApiKey, Event, HourBucket, Incident, Scan, SensorHealthAlert]:
                assert db.scalar(select(func.count()).select_from(model).where(model.site_id.in_([first["id"], extra["id"]]))) == 0
                assert db.scalar(select(func.count()).select_from(model).where(model.site_id == other["id"])) > 0
            assert db.get(Site, first["id"]) is None and db.get(Site, extra["id"]) is None


def test_removal_requires_csrf_origin_confirmation_and_password():
    with TestClient(app, base_url="https://testserver") as client:
        headers = register(client, "remove-gates-" + uuid.uuid4().hex)
        assert client.post("/app/api/account/delete", headers=ORIGIN, json=BODY).status_code == 403
        assert client.post("/app/api/account/delete", headers={**headers, "Origin": "https://evil.test"}, json=BODY).status_code == 403
        assert client.post("/app/api/account/delete", headers=headers, json={"password": PASSWORD}).status_code == 422
        assert client.post("/app/api/account/delete", headers=headers, json={**BODY, "confirmation": "delete"}).status_code == 422
        assert client.post("/app/api/account/delete", headers=headers, json={**BODY, "password": "wrong-long-test-password"}).status_code == 401
        assert client.get("/app/api/session").status_code == 200


def test_removal_failure_rolls_back_every_live_record(monkeypatch, isolated_redis):
    import app.account_removal as removal
    original = removal.remove_account_data
    def interrupted(db, user_id):
        original(db, user_id)
        raise OperationalError("synthetic interruption", {}, Exception("synthetic"))
    with TestClient(app, base_url="https://testserver") as client:
        headers, created, user_id, incident = populated_owner(client, isolated_redis)
        monkeypatch.setattr(removal, "remove_account_data", interrupted)
        assert client.post("/app/api/account/delete", headers=headers, json=BODY).status_code == 503
        assert client.get("/app/api/session").status_code == 200
        assert client.get("/v1/config", headers={"X-API-Key": created["api_key"]}).status_code == 200
        assert client.get(f"/app/api/incidents/{incident}").json()["actions"][0]["note"] == "Private owner review"
        with SessionLocal() as db:
            assert db.get(User, user_id) is not None
            for model in [Alert, ApiKey, Event, HourBucket, Incident, Scan, SensorHealthAlert]:
                assert db.scalar(select(func.count()).select_from(model).where(model.site_id == created["id"])) > 0


def test_removal_without_sites_and_password_attempt_budget():
    with TestClient(app, base_url="https://testserver") as client:
        headers = register(client, "remove-empty-" + uuid.uuid4().hex)
        assert client.post("/app/api/account/delete", headers=headers, json=BODY).status_code == 204
        headers = register(client, "remove-budget-" + uuid.uuid4().hex)
        wrong = {**BODY, "password":"wrong-long-test-password"}
        for _ in range(3):
            assert client.post("/app/api/account/delete", headers=headers, json=wrong).status_code == 401
        assert client.post("/app/api/account/delete", headers=headers, json=BODY).status_code == 429
        assert client.get("/app/api/session").status_code == 200
