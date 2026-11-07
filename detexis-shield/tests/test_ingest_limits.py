import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from sqlalchemy import create_engine, inspect

from app.main import app
from app.rate_limit import enforce_limit
from app.redis_store import get_redis
from test_smoke import event, make_site


def test_site_limits_count_events_and_requests_atomically(isolated_redis, monkeypatch):
    monkeypatch.setenv("INGEST_REQUESTS_PER_MINUTE", "2")
    monkeypatch.setenv("INGEST_EVENTS_PER_MINUTE", "3")
    enforce_limit(isolated_redis, "a", 2)
    with pytest.raises(Exception) as raised:
        enforce_limit(isolated_redis, "a", 2)
    assert raised.value.status_code == 429
    assert 1 <= int(raised.value.headers["Retry-After"]) <= 60
    enforce_limit(isolated_redis, "b", 2)
    assert all(0 < isolated_redis.ttl(k) <= 60 for k in isolated_redis.keys())


def test_ingest_unavailable_when_budget_cannot_be_enforced(monkeypatch):
    class Offline:
        def eval(self, *args):
            raise ConnectionError("offline")
    app.dependency_overrides[get_redis] = lambda: Offline()
    _, key = make_site("offline.test")
    with TestClient(app) as client:
        response = client.post("/v1/events", json={"events": [event()]}, headers={"X-API-Key": key})
    assert response.status_code == 503


def test_payload_cannot_choose_rate_limit_tenant(monkeypatch):
    monkeypatch.setenv("INGEST_REQUESTS_PER_MINUTE", "1")
    _, first = make_site("first.test")
    _, second = make_site("second.test")
    with TestClient(app) as client:
        for key, expected in [(first, 202), (first, 429), (second, 202)]:
            body = {"events": [{**event(), "site_id": "spoofed"}]}
            assert client.post("/v1/events", json=body, headers={"X-API-Key": key}).status_code == expected


def test_same_event_id_is_independent_across_sites():
    from app.db import SessionLocal
    from app.models import Event
    first_id, first = make_site("ids-first.test")
    second_id, second = make_site("ids-second.test")
    item = event()
    with TestClient(app) as client:
        for key in (first, second, first):
            assert client.post("/v1/events", json={"events": [item]}, headers={"X-API-Key": key}).status_code == 202
    with SessionLocal() as db:
        assert {row.site_id for row in db.query(Event).filter(Event.event_id == item["event_id"])} == {first_id, second_id}


def test_ingest_body_cap_ignores_missing_content_length():
    with TestClient(app) as client:
        response = client.post("/v1/events", content=iter([b"x" * 600000, b"x" * 600000]))
    assert response.status_code == 413


def test_missing_auth_returns_401():
    with TestClient(app) as client:
        assert client.get("/v1/config").status_code == 401


def test_migration_round_trip(tmp_path):
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + (tmp_path / "migrations.db").as_posix()}
    def run(*args):
        result = subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", *args],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    run("upgrade", "head")
    engine = create_engine(env["DATABASE_URL"])
    assert set(inspect(engine).get_pk_constraint("events")["constrained_columns"]) == {"site_id", "event_id"}
    run("check")
    engine.dispose()
    run("downgrade", "base")
    engine = create_engine(env["DATABASE_URL"])
    assert "events" not in inspect(engine).get_table_names()
    engine.dispose()
