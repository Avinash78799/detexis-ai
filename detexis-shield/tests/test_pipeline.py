import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Alert, Event, HourBucket, Incident, Site
from app.worker import baseline_threshold, process_batch
from app.alerts import send_pending
from test_smoke import event, make_site


def seed(site_id, path, **extra):
    data = {**event(path), **extra}
    data["ts"] = datetime.fromisoformat(data["ts"])
    with SessionLocal() as db:
        row = Event(site_id=site_id, **data)
        db.add(row)
        db.commit()
    return data["event_id"]


def test_pipeline_is_tenant_scoped_idempotent_and_recomputes_features(isolated_redis):
    a, _ = make_site("pipeline-a.test")
    b, _ = make_site("pipeline-b.test")
    probe = seed(a, "/.env", features={"schema_version": 99}, flags=["fake"])
    exploit = seed(a, "/search", query_redacted="q=union+select+password")
    other = seed(b, "/private")
    assert process_batch(a, [probe, exploit, other], isolated_redis) == 2
    assert process_batch(a, [probe, exploit], isolated_redis) == 0
    with SessionLocal() as db:
        incidents = db.scalars(select(Incident).where(Incident.site_id == a)).all()
        assert len(incidents) == 1
        assert incidents[0].event_count == 2
        assert "recon_to_exploit" in incidents[0].correlations
        assert len(db.scalars(select(Alert).where(Alert.site_id == a)).all()) == 1
        assert db.get(Event, (probe, a)).features["schema_version"] == 1
        assert db.get(Event, (other, b)).processed_at is None


def test_login_and_flood_state_isolated_and_canary_flags_not_trusted(isolated_redis):
    site, _ = make_site("state.test")
    ids = [seed(site, "/login", status=401) for _ in range(10)]
    process_batch(site, ids, isolated_redis)
    innocent = seed(site, "/normal", flags=["honeytoken_hit"])
    process_batch(site, [innocent], isolated_redis)
    with SessionLocal() as db:
        assert "login_brute_force" in [f["rule_id"] for f in db.get(Event, (ids[-1], site)).findings]
        assert db.get(Event, (innocent, site)).findings == []


def test_baseline_cold_start_and_hourly_threshold():
    site_id, _ = make_site("baseline.test")
    hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        site = db.get(Site, site_id)
        assert baseline_threshold(db, site, hour) is None
        site.created_at = hour - timedelta(days=8)
        for day in range(1, 8):
            db.add(HourBucket(site_id=site_id, hour=hour - timedelta(days=day), count=200))
        db.flush()
        assert baseline_threshold(db, site, hour) == 200


def test_alert_outbox_delivers_each_configured_channel_once(isolated_redis, monkeypatch):
    site, _ = make_site("alerts.test")
    process_batch(site, [seed(site, "/.env")], isolated_redis)
    calls = []
    monkeypatch.setenv("SHIELD_ALERT_TARGETS", json.dumps({site: {"email": "owner@example.test", "slack": "configured"}}))
    monkeypatch.setattr("app.alerts.deliver", lambda *args: calls.append(args))
    send_pending()
    send_pending()
    assert len([c for c in calls if c[1] in {"owner@example.test", "configured"}]) == 2


def test_ml_failure_keeps_rule_detection(isolated_redis, monkeypatch):
    monkeypatch.setenv("SHIELD_MODEL_DIR", "does-not-exist")
    site, _ = make_site("fallback.test")
    item = seed(site, "/.env")
    process_batch(site, [item], isolated_redis)
    with SessionLocal() as db:
        assert "honeytoken" in [f["rule_id"] for f in db.get(Event, (item, site)).findings]


def test_full_batch_groups_once_without_per_event_database_reads(isolated_redis):
    from sqlalchemy import event as sql_event
    from app.db import engine
    site, _ = make_site("batch.test")
    stamp = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    ids = [seed(site, "/.env", received_at=stamp) for _ in range(100)]
    reads = []
    def record(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith("SELECT"):
            reads.append(statement)
    sql_event.listen(engine, "before_cursor_execute", record)
    try:
        assert process_batch(site, ids, isolated_redis) == 100
    finally:
        sql_event.remove(engine, "before_cursor_execute", record)
    assert len(reads) < 10
    with SessionLocal() as db:
        incident = db.scalar(select(Incident).where(Incident.site_id == site))
        assert incident.event_count == 100
        assert len(db.scalars(select(Alert).where(Alert.site_id == site)).all()) == 1
        assert db.get(HourBucket, (site, stamp.replace(minute=0))).count == 100
    assert process_batch(site, ids, isolated_redis) == 0


def test_failed_batch_rolls_back_and_retry_preserves_counts(isolated_redis, monkeypatch):
    import app.worker as worker
    site, _ = make_site("retry-batch.test")
    ids = [seed(site, "/.env") for _ in range(3)]
    original = worker.evaluate
    calls = 0
    def fail_mid_batch(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected job failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(worker, "evaluate", fail_mid_batch)
    with pytest.raises(RuntimeError, match="injected job failure"):
        process_batch(site, ids, isolated_redis)
    with SessionLocal() as db:
        assert all(db.get(Event, (item, site)).processed_at is None for item in ids)
        assert db.scalar(select(Incident).where(Incident.site_id == site)) is None
    monkeypatch.setattr(worker, "evaluate", original)
    assert process_batch(site, ids, isolated_redis) == 3
    with SessionLocal() as db:
        assert db.scalar(select(Incident).where(Incident.site_id == site)).event_count == 3
