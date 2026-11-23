from datetime import datetime, timedelta, timezone

from rq import Queue
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Scan, Site
from app.scan_jobs import schedule_rescans
from test_smoke import make_site


def test_scheduler_keeps_one_old_pending_scan_and_one_queue_job(isolated_redis):
    site, _ = make_site("scheduled-pending.example.test")
    with SessionLocal() as db:
        db.get(Site, site).verified_at = datetime.now(timezone.utc)
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
