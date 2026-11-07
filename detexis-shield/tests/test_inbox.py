from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import SessionLocal
from app.models import Incident, IncidentAction
from app.worker import process_batch
from app import incident_inbox
from test_accounts import register, ORIGIN
from test_pipeline import seed


def test_triage_returns_not_found_when_retention_removes_incident(monkeypatch):
    with TestClient(app, base_url="https://testserver") as client:
        headers = register(client, "inbox-retention-race")
        site = client.post("/app/api/sites", headers=headers, json={"domain":"retention.example"}).json()["id"]
        stamp = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = Incident(site_id=site, ip_hash="a" * 64, bucket=0, severity="low",
                           rules=[], correlations=[], first_seen=stamp, last_seen=stamp)
            db.add(row)
            db.commit()
            incident_id = row.id

        original = incident_inbox.owned_site

        def remove_before_locked_read(db, user, site_id):
            result = original(db, user, site_id)
            # Deterministically reproduce retention winning before the second read.
            db.delete(db.get(Incident, incident_id))
            db.flush()
            return result

        monkeypatch.setattr(incident_inbox, "owned_site", remove_before_locked_read)
        response = client.post(f"/app/api/incidents/{incident_id}/status", headers=headers,
                               json={"status":"resolved"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Incident not found"
        with SessionLocal() as db:
            assert db.scalar(select(IncidentAction).where(IncidentAction.incident_id == incident_id)) is None


def test_inbox_evidence_triage_reopen_and_tenant_boundaries(isolated_redis):
    with TestClient(app, base_url="https://testserver") as owner, TestClient(app, base_url="https://testserver") as other:
        headers = register(owner, "inbox-owner")
        other_headers = register(other, "inbox-other")
        site = owner.post("/app/api/sites", headers=headers, json={"domain":"inbox.example"}).json()["id"]
        stamp = datetime.now(timezone.utc)
        event = seed(site, "/.env", received_at=stamp)
        assert process_batch(site, [event], isolated_redis) == 1
        listed = owner.get("/app/api/inbox").json()["incidents"]
        assert len(listed) == 1 and listed[0]["domain"] == "inbox.example"
        assert other.get("/app/api/inbox").json()["incidents"] == []
        incident = listed[0]["id"]
        path = f"/app/api/incidents/{incident}"
        assert other.get(path).status_code == 404
        assert other.post(path + "/status", headers=other_headers, json={"status":"resolved"}).status_code == 404
        assert owner.post(path + "/status", headers=ORIGIN, json={"status":"resolved"}).status_code == 403
        assert "honeytoken" in {finding["rule_id"] for finding in owner.get(path).json()["evidence"][0]["findings"]}
        note = '<img src=x onerror="alert(1)">'
        assert owner.post(path + "/status", headers=headers, json={"status":"resolved","note":note}).status_code == 200
        assert owner.get(path).json()["actions"][0]["note"] == note
        newer = seed(site, "/.env", received_at=stamp)
        process_batch(site, [newer], isolated_redis)
        detail = owner.get(path).json()
        assert detail["status"] == "open"
        assert detail["actions"][0]["actor"] == "System"
        assert len(detail["evidence"]) == 2
        owner.post(path + "/status", headers=headers, json={"status":"false_positive","note":"Authorized scanner"})
        process_batch(site, [seed(site, "/.env", received_at=stamp)], isolated_redis)
        assert owner.get(path).json()["status"] == "false_positive"
        assert owner.get("/app/inbox").status_code == 200


def test_inbox_cursor_preserves_incidents_with_equal_timestamps():
    with TestClient(app, base_url="https://testserver") as client:
        headers = register(client, "inbox-pagination")
        site = client.post("/app/api/sites", headers=headers, json={"domain":"pagination.example"}).json()["id"]
        stamp = datetime.now(timezone.utc)
        with SessionLocal() as db:
            for index in range(3):
                db.add(Incident(site_id=site, ip_hash=str(index)*64, bucket=index, severity="low", rules=[], correlations=[], first_seen=stamp,last_seen=stamp))
            db.commit()
        ids = []
        cursor = {}
        for _ in range(3):
            response = client.get("/app/api/inbox", params={"limit":1, **cursor})
            assert response.status_code == 200
            page = response.json()
            ids.append(page["incidents"][0]["id"])
            cursor = page["next"]
        assert len(set(ids)) == 3
        assert client.get("/app/api/inbox", params={"limit":1, **cursor}).json()["incidents"] == []


def test_logged_out_browser_preserves_inbox_destination_without_redirecting_api_calls():
    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/app/inbox?incident=sample", headers={"Accept":"text/html"}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/app?next=%2Fapp%2Finbox%3Fincident%3Dsample"
        assert client.get("/app/api/inbox", headers={"Accept":"text/html"}).status_code == 401
