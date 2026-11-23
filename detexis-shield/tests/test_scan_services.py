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
from rq import Queue
from app.db import SessionLocal
from app.models import Scan
from app.scan_jobs import enqueue_scan
from test_smoke import make_site
from test_scan_scheduling import (test_scheduler_keeps_one_old_pending_scan_and_one_queue_job,
                                  test_pending_scan_requeues_after_complete_redis_loss)
fake = fakeredis.FakeRedis()
try:
    test_scheduler_keeps_one_old_pending_scan_and_one_queue_job(fake)
    test_pending_scan_requeues_after_complete_redis_loss(fake)
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
