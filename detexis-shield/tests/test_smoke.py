"""Run from repo root: pytest -q   (uses SQLite, no Docker needed)"""
import os
import sys
import uuid
from datetime import datetime, timezone

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
sys.path.insert(0, "backend")
sys.path.insert(0, "sensor-sdk")

from fastapi.testclient import TestClient  # noqa: E402
from app.auth import new_api_key  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ApiKey, Event, Site  # noqa: E402
from detexis_shield.redact import redact_query  # noqa: E402

Base.metadata.create_all(engine)
client = TestClient(app)


def make_site(domain):
    raw, prefix, key_hash = new_api_key()
    with SessionLocal() as db:
        s = Site(domain=domain)
        db.add(s)
        db.flush()
        db.add(ApiKey(site_id=s.id, prefix=prefix, key_hash=key_hash))
        db.commit()
        return s.id, raw


def event(path="/"):
    return {"event_id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc).isoformat(),
            "ip_hash": "x" * 64, "method": "GET", "path": path, "status": 200, "latency_ms": 1.2}


def test_ingest_requires_valid_key():
    assert client.post("/v1/events", json={"events": [event()]}, headers={"X-API-Key": "dxs_bad_key"}).status_code == 401


def test_ingest_idempotent_and_tenant_isolated():
    a_id, a_key = make_site("a.test")
    b_id, b_key = make_site("b.test")
    e = event("/a-only")
    for _ in range(2):  # retry same event: must not duplicate
        r = client.post("/v1/events", json={"events": [e]}, headers={"X-API-Key": a_key})
        assert r.status_code == 202
    with SessionLocal() as db:
        rows = db.query(Event).filter(Event.event_id == e["event_id"]).all()
        assert len(rows) == 1 and rows[0].site_id == a_id
        assert db.query(Event).filter(Event.site_id == b_id).count() == 0


def test_batch_cap():
    _, key = make_site("c.test")
    r = client.post("/v1/events", json={"events": [event() for _ in range(101)]}, headers={"X-API-Key": key})
    assert r.status_code == 422


def test_redaction():
    out = redact_query("q=hello&password=hunter2&token=abc")
    assert "hunter2" not in out and "abc" not in out and "q=hello" in out
