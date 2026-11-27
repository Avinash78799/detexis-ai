from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
from rq import Queue
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Scan, Site
from app.scan_jobs import run_scan, schedule_rescans
from test_smoke import make_site


def test_scheduler_keeps_one_old_pending_scan_and_one_queue_job(isolated_redis):
    site, _ = make_site("scheduled-pending.example.test")
    with SessionLocal() as db:
        db.get(Site, site).verified_at = datetime.now(timezone.utc)-timedelta(days=3)
        row = Scan(site_id=site, created_at=datetime.now(timezone.utc)-timedelta(days=2))
        db.add(row)
        db.commit()
        scan_id = row.id
    for _ in range(3):
        schedule_rescans(isolated_redis)
    with SessionLocal() as db:
        rows = db.scalars(select(Scan).where(Scan.site_id == site)).all()
        assert [row.id for row in rows] == [scan_id]
    queue = Queue("shield", connection=isolated_redis)
    jobs = [job for job in queue.get_jobs() if job.args == (scan_id,)]
    assert len(jobs) == 1 and jobs[0].args == (scan_id,)


def test_pending_scan_requeues_after_complete_redis_loss(isolated_redis):
    site, _ = make_site("scheduled-recovery.example.test")
    with SessionLocal() as db:
        db.get(Site, site).verified_at = datetime.now(timezone.utc)
        db.commit()
    schedule_rescans(isolated_redis)
    queue = Queue("shield", connection=isolated_redis)
    before = {job.args for job in queue.get_jobs()}
    isolated_redis.flushdb()  # Only the test fixture's synthetic Redis.
    schedule_rescans(isolated_redis)
    assert {job.args for job in queue.get_jobs()} == before


def test_stale_scans_close_without_external_requests(isolated_redis, monkeypatch):
    now = datetime.now(timezone.utc)
    stale_ids = []
    for reason, verified_at in (
        ("revoked", None),
        ("expired", now-timedelta(days=8)),
        ("reverified", now-timedelta(minutes=1)),
    ):
        site_id, _ = make_site(f"stale-scan-{reason}.example.test")
        with SessionLocal() as db:
            db.get(Site, site_id).verified_at = verified_at
            scan = Scan(site_id=site_id, created_at=now-timedelta(hours=1))
            db.add(scan)
            db.commit()
            stale_ids.append(scan.id)

    scanner_client = Mock(side_effect=AssertionError("A stale scan must not contact the scanner"))
    monkeypatch.setattr("app.scan_jobs.httpx.Client", scanner_client)
    run_scan(stale_ids[-1])
    schedule_rescans(isolated_redis)
    with SessionLocal() as db:
        assert [db.get(Scan, scan_id).status for scan_id in stale_ids] == ["unverified"] * 3
    assert all(job.args[0] not in stale_ids for job in Queue("shield", connection=isolated_redis).get_jobs())
    scanner_client.assert_not_called()


def test_manual_scan_ignores_stale_requests_but_retains_cooldown():
    now = datetime.now(timezone.utc)
    site_id, key = make_site("scan-cooldown-after-verification.example.test")
    with SessionLocal() as db:
        db.get(Site, site_id).verified_at = now-timedelta(minutes=1)
        previous = Scan(site_id=site_id, created_at=now-timedelta(minutes=2), status="complete")
        stale = Scan(site_id=site_id, created_at=now-timedelta(minutes=3))
        db.add_all([previous, stale])
        db.commit()
        previous_id, stale_id = previous.id, stale.id
    with TestClient(app) as client:
        headers = {"X-API-Key": key}
        assert client.post("/v1/scans", headers=headers).status_code == 429
        with SessionLocal() as db:
            db.get(Scan, previous_id).created_at = now-timedelta(hours=2)
            db.commit()
        fresh = client.post("/v1/scans", headers=headers)
        assert fresh.status_code == 202 and fresh.json()["scan_id"] != stale_id
        assert client.post("/v1/scans", headers=headers).json() == fresh.json()
