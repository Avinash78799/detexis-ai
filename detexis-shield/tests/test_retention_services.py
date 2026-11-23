"""Run retention graph/rollback assertions with real PostgreSQL foreign keys."""
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(not os.getenv("INTEGRATION_DATABASE_URL"), reason="PostgreSQL unavailable locally")
def test_retention_postgres_foreign_keys_and_transaction_rollback():
    env = {**os.environ, "DATABASE_URL": os.environ["INTEGRATION_DATABASE_URL"]}
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        env=env, capture_output=True, text=True, timeout=60)
    assert migration.returncode == 0, migration.stderr
    script = '''
import sys
sys.path[:0] = ['backend', 'sensor-sdk', 'tests']
import fakeredis
from test_retention import test_retention_removes_expired_incident_history_and_preserves_recent_tenants
fake = fakeredis.FakeRedis()
try:
    for interrupt in [False, True]:
        test_retention_removes_expired_incident_history_and_preserves_recent_tenants(fake, interrupt)
finally:
    fake.close()
'''
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
