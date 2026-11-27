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

    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Site, Incident, IncidentAction, Alert, Event
    from app.maintenance import purge
    from app.worker import process_batch
    from test_pipeline import seed
    from test_smoke import make_site
    sites = [make_site('retention-busy.test')[0], make_site('retention-idle.test')[0]]
    old = datetime.now(timezone.utc) - timedelta(days=40)
    incident_ids = []
    for site_id in sites:
        event_id = seed(site_id, '/.env', received_at=old)
        process_batch(site_id, [event_id], fake)
        with SessionLocal() as db:
            incident = db.scalar(select(Incident).where(Incident.site_id == site_id))
            incident_ids.append(incident.id)
            db.add(IncidentAction(incident_id=incident.id, previous_status='open',
                                  status='acknowledged', note='Busy site history'))
            db.commit()
    with SessionLocal() as busy:
        # Same site lock held by real processing and owner triage.
        busy.scalar(select(Site).where(Site.id == sites[0]).with_for_update(key_share=True))
        purge(30)
        with SessionLocal() as check:
            assert check.get(Incident, incident_ids[0]) is not None, 'Cleanup erased a busy site'
            assert check.get(Incident, incident_ids[1]) is None, 'Idle site cleanup was blocked'
            assert len(check.scalars(select(IncidentAction).where(IncidentAction.incident_id == incident_ids[0])).all()) == 1
        # Processing can extend an incident while owning the site lock.
        busy.get(Incident, incident_ids[0]).last_seen = datetime.now(timezone.utc)
        busy.commit()
    purge(30)
    with SessionLocal() as check:
        assert check.get(Incident, incident_ids[0]) is not None
        assert len(check.scalars(select(Alert).where(Alert.incident_id == incident_ids[0])).all()) == 1
        assert len(check.scalars(select(IncidentAction).where(IncidentAction.incident_id == incident_ids[0])).all()) == 1
        check.get(Incident, incident_ids[0]).last_seen = old
        check.commit()
    purge(30)
    with SessionLocal() as check:
        assert check.get(Incident, incident_ids[0]) is None
        assert not check.scalars(select(Alert).where(Alert.incident_id == incident_ids[0])).all()
        assert not check.scalars(select(IncidentAction).where(IncidentAction.incident_id == incident_ids[0])).all()
finally:
    fake.close()
'''
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
