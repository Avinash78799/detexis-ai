"""Outbox eligibility and locking query exercised on real PostgreSQL."""
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(not os.getenv("INTEGRATION_DATABASE_URL"), reason="PostgreSQL unavailable locally")
def test_postgres_alert_backlog_and_retry():
    env = {**os.environ, "DATABASE_URL": os.environ["INTEGRATION_DATABASE_URL"]}
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        env=env, capture_output=True, text=True, timeout=60)
    assert migration.returncode == 0, migration.stderr
    script = '''
import sys
sys.path[:0] = ['backend', 'sensor-sdk', 'tests']
import fakeredis, pytest
from test_alert_outbox import (test_unconfigured_backlog_cannot_starve_configured_delivery,
    test_later_configuration_reactivates_unconfigured_alert,
    test_partial_delivery_retries_only_failed_channel)
fake = fakeredis.FakeRedis()
try:
    for check in [test_unconfigured_backlog_cannot_starve_configured_delivery,
                  test_later_configuration_reactivates_unconfigured_alert,
                  test_partial_delivery_retries_only_failed_channel]:
        with pytest.MonkeyPatch.context() as patch:
            check(fake, patch)
finally:
    fake.close()
'''
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
