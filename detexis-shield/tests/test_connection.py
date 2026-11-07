from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import SessionLocal
from app.models import Site, Event, ApiKey
from test_accounts import register
from test_smoke import event


def test_connection_diagnostics_lifecycle_and_tenant_privacy():
    with TestClient(app, base_url="https://testserver") as owner, TestClient(app, base_url="https://testserver") as other:
        headers = register(owner, "connection-owner")
        register(other, "connection-other")
        created = owner.post("/app/api/sites", headers=headers, json={"domain": "connection.example"}).json()
        site_id = created["id"]
        path = f"/app/api/sites/{site_id}/connection"
        assert other.get(path).status_code == 404
        with TestClient(app, base_url="https://testserver") as anonymous:
            assert anonymous.get(path).status_code == 401
        first = owner.get(path)
        assert first.headers["cache-control"] == "no-store"
        assert first.json()["heartbeat"] == "waiting"
        assert first.json()["latest_event_processing"] == "waiting"
        assert first.json()["last_event_received_at"] is None
        assert first.json()["active_key"] is True

        sensor_headers = {"X-API-Key": created["api_key"]}
        assert owner.post("/v1/heartbeat", headers=sensor_headers).status_code == 200
        request_event = event("/private-customer-path")
        request_event["query_redacted"] = "q=private-customer-query"
        assert owner.post("/v1/events", headers=sensor_headers, json={"events": [request_event]}).status_code == 202
        receiving = owner.get(path)
        assert receiving.json()["heartbeat"] == "reporting"
        assert receiving.json()["latest_event_processing"] == "pending"
        assert receiving.json()["last_event_received_at"]
        assert "private-customer" not in receiving.text
        assert created["api_key"] not in receiving.text
        with SessionLocal() as db:
            row = db.get(Event, (request_event["event_id"], site_id))
            row.received_at = datetime.now(timezone.utc) - timedelta(minutes=2)
            db.get(Site, site_id).last_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=4)
            for key in db.scalars(select(ApiKey).where(ApiKey.site_id == site_id)):
                key.revoked = True
            db.commit()
        delayed = owner.get(path).json()
        assert delayed["heartbeat"] == "overdue"
        assert delayed["latest_event_processing"] == "delayed"
        assert delayed["active_key"] is False
        with SessionLocal() as db:
            db.get(Event, (request_event["event_id"], site_id)).processed_at = datetime.now(timezone.utc)
            db.commit()
        assert owner.get(path).json()["latest_event_processing"] == "processed"


def test_connection_uses_receipt_time_and_excludes_other_sites():
    with TestClient(app, base_url="https://testserver") as owner:
        headers = register(owner, "connection-order")
        a = owner.post("/app/api/sites", headers=headers, json={"domain": "connection-a.example"}).json()
        b = owner.post("/app/api/sites", headers=headers, json={"domain": "connection-b.example"}).json()
        old = event()
        recent = event()
        # Sensor timestamps may be skewed. Receipt time determines the check.
        old["ts"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        for item in [old, recent]:
            assert owner.post("/v1/events", headers={"X-API-Key": a["api_key"]}, json={"events": [item]}).status_code == 202
        with SessionLocal() as db:
            row = db.get(Event, (old["event_id"], a["id"]))
            row.received_at = datetime.now(timezone.utc) - timedelta(minutes=5)
            row.processed_at = datetime.now(timezone.utc)
            db.commit()
        assert owner.get(f'/app/api/sites/{a["id"]}/connection').json()["latest_event_processing"] == "pending"
        empty = owner.get(f'/app/api/sites/{b["id"]}/connection').json()
        assert empty["latest_event_processing"] == "waiting" and empty["heartbeat"] == "waiting"
