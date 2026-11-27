import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.alerts import send_pending
from app.db import SessionLocal
from app.models import Alert
from app.worker import process_batch
from test_pipeline import seed
from test_smoke import make_site


def test_unconfigured_backlog_cannot_starve_configured_delivery(isolated_redis, monkeypatch):
    sites = [make_site(f"outbox-fairness-{index}.test")[0] for index in range(4)]
    for index, site in enumerate(sites):
        process_batch(site, [seed(site, "/.env")], isolated_redis)
        with SessionLocal() as db:
            alert = db.scalar(select(Alert).where(Alert.site_id == site))
            alert.created_at = datetime.now(timezone.utc) - timedelta(days=40-index)
            db.commit()
    calls = []
    monkeypatch.setenv("SHIELD_ALERT_TARGETS", json.dumps({sites[-1]: {"email": "synthetic@example.test"}}))
    monkeypatch.setattr("app.alerts.deliver", lambda *args: calls.append(args))
    assert send_pending(limit=1) == 1
    assert len(calls) == 1 and calls[0][1] == "synthetic@example.test"
    assert send_pending(limit=1) == 0
    with SessionLocal() as db:
        sent = db.scalar(select(Alert).where(Alert.site_id == sites[-1]))
        assert sent.status == "sent" and sent.attempts == 1
        for site in sites[:-1]:
            row = db.scalar(select(Alert).where(Alert.site_id == site))
            assert row.attempts == 0 and row.delivered == []


def test_later_configuration_reactivates_unconfigured_alert(isolated_redis, monkeypatch):
    site, _ = make_site("outbox-enable-later.test")
    process_batch(site, [seed(site, "/.env")], isolated_redis)
    monkeypatch.setenv("SHIELD_ALERT_TARGETS", "{}")
    monkeypatch.setattr("app.alerts.deliver", lambda *args: None)
    assert send_pending(limit=10000) == 0
    with SessionLocal() as db:
        row = db.scalar(select(Alert).where(Alert.site_id == site))
        assert row.status == "unconfigured" and row.attempts == 0
    monkeypatch.setenv("SHIELD_ALERT_TARGETS", json.dumps({site: {"email": "synthetic@example.test"}}))
    assert send_pending(limit=1) == 1
    assert send_pending(limit=1) == 0


def test_partial_delivery_retries_only_failed_channel(isolated_redis, monkeypatch):
    site, _ = make_site("outbox-partial.test")
    process_batch(site, [seed(site, "/.env")], isolated_redis)
    monkeypatch.setenv("SHIELD_ALERT_TARGETS", json.dumps({site: {
        "email": "synthetic@example.test", "slack": "synthetic-destination"}}))
    calls = []

    def delivery(channel, destination, message):
        calls.append(channel)
        if channel == "slack" and calls.count("slack") == 1:
            raise RuntimeError("Synthetic delivery failure")

    monkeypatch.setattr("app.alerts.deliver", delivery)
    assert send_pending(limit=1) == 0
    with SessionLocal() as db:
        row = db.scalar(select(Alert).where(Alert.site_id == site))
        assert row.delivered == ["email"] and row.attempts == 1 and row.status == "pending"
    assert send_pending(limit=1) == 1
    assert send_pending(limit=1) == 0
    assert calls.count("email") == 1 and calls.count("slack") == 2
