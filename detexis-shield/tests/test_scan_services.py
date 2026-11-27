"""PostgreSQL serialization of simultaneous scan publishers; no scans execute."""
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(not os.getenv("INTEGRATION_DATABASE_URL"), reason="PostgreSQL unavailable locally")
def test_postgres_scan_publishers_and_recovery():
    env = {**os.environ, "DATABASE_URL": os.environ["INTEGRATION_DATABASE_URL"]}
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        env=env, capture_output=True, text=True, timeout=60)
    assert migration.returncode == 0, migration.stderr
    script = '''
import sys
sys.path[:0] = ['backend', 'sensor-sdk', 'tests']
from concurrent.futures import ThreadPoolExecutor
import fakeredis
from pytest import MonkeyPatch
from rq import Queue
from app.db import SessionLocal
from app.main import app
from app.models import Scan
from app.redis_store import get_redis
from app.scan_jobs import enqueue_scan
from test_smoke import make_site
from test_scan_scheduling import (test_scheduler_keeps_one_old_pending_scan_and_one_queue_job,
                                  test_pending_scan_requeues_after_complete_redis_loss,
                                  test_stale_scans_close_without_external_requests,
                                  test_manual_scan_ignores_stale_requests_but_retains_cooldown)
from test_scanner import test_rotated_challenge_cannot_be_verified_by_an_in_flight_lookup
fake = fakeredis.FakeRedis()
try:
    for owner_route in (False, True):
        with MonkeyPatch.context() as patch:
            patch.setitem(app.dependency_overrides, get_redis, lambda: fake)
            test_rotated_challenge_cannot_be_verified_by_an_in_flight_lookup(patch, owner_route)
    test_scheduler_keeps_one_old_pending_scan_and_one_queue_job(fake)
    test_pending_scan_requeues_after_complete_redis_loss(fake)
    with MonkeyPatch.context() as patch:
        patch.setitem(app.dependency_overrides, get_redis, lambda: fake)
        test_stale_scans_close_without_external_requests(fake, patch)
        test_manual_scan_ignores_stale_requests_but_retains_cooldown()
    site, _ = make_site('concurrent-scan-publish.example.test')
    with SessionLocal() as db:
        record = Scan(site_id=site)
        db.add(record)
        db.commit()
        identity = record.id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(enqueue_scan, identity, fake) for _ in range(2)]
        assert sorted(task.result(timeout=20) for task in futures) == [False, True]
    jobs = [job for job in Queue('shield', connection=fake).get_jobs() if job.args == (identity,)]
    assert len(jobs) == 1
finally:
    fake.close()
'''
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
