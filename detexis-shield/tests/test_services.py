"""Real Redis/PostgreSQL integration runs in CI, not silently replaced by mocks."""
import os
import subprocess
import sys
import uuid

import pytest


@pytest.mark.skipif(not os.getenv("INTEGRATION_DATABASE_URL"), reason="PostgreSQL/Redis services not available locally")
def test_real_services_migration_ingest_rq_and_worker(tmp_path):
    env = {**os.environ, "DATABASE_URL": os.environ.get("INTEGRATION_DATABASE_URL", ""),
           "REDIS_URL": os.environ.get("INTEGRATION_REDIS_URL", "")}
    migrate = subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], env=env, capture_output=True, text=True)
    assert migrate.returncode == 0, migrate.stderr
    script = '''
import sys,uuid
sys.path.insert(0,"backend")
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from rq import Queue,SimpleWorker
from app.main import app
from app.db import SessionLocal
from app.models import Site,ApiKey,Incident,Event
from app.auth import new_api_key
from app.redis_store import get_redis
from sqlalchemy import select
raw,prefix,key_hash=new_api_key()
with SessionLocal() as db:
    site=Site(domain="ci.example")
    db.add(site);db.flush();site_id=site.id
    db.add(ApiKey(site_id=site_id,prefix=prefix,key_hash=key_hash));db.commit()
item={"event_id":str(uuid.uuid4()),"ts":datetime.now(timezone.utc).isoformat(),"ip_hash":"a"*64,"method":"GET","path":"/.env","status":404,"latency_ms":1}
with TestClient(app) as client:
    response=client.post("/v1/events",json={"events":[item]},headers={"X-API-Key":raw})
    assert response.status_code==202,response.text
redis=get_redis()
SimpleWorker([Queue("shield",connection=redis)],connection=redis).work(burst=True)
with SessionLocal() as db:
    assert db.get(Event,(item["event_id"],site_id)).processed_at is not None
    assert db.scalar(select(Incident).where(Incident.site_id==site_id)) is not None
'''
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
