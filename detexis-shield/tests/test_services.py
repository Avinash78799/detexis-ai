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
with TestClient(app,base_url="https://testserver") as owner:
    origin={"Origin":"https://testserver"}
    registered=owner.post("/app/api/register",headers=origin,json={"email":str(uuid.uuid4())+"@integration.example","password":"Synthetic-integration-passphrase"})
    assert registered.status_code==201,registered.text
    csrf={**origin,"X-CSRF-Token":registered.json()["csrf_token"]}
    created=owner.post("/app/api/sites",headers=csrf,json={"domain":"owner-integration.example"})
    assert created.status_code==201,created.text
    owner_site=created.json()["id"]
    # The same event ID is valid in two tenants; processing must use both keys.
    owner_item={**item,"path":"/admin-backup"}
    assert owner.post("/v1/events",json={"events":[owner_item]},headers={"X-API-Key":created.json()["api_key"]}).status_code==202
    SimpleWorker([Queue("shield",connection=redis)],connection=redis).work(burst=True)
    listed=owner.get("/app/api/inbox").json()["incidents"]
    assert len(listed)==1 and listed[0]["site_id"]==owner_site
    detail_path="/app/api/incidents/"+listed[0]["id"]
    evidence=owner.get(detail_path)
    assert evidence.status_code==200,evidence.text
    assert evidence.json()["evidence"],evidence.text
    assert evidence.json()["evidence"][0]["path"]=="/admin-backup"
    from app.worker import process_batch
    assert process_batch(owner_site,[owner_item["event_id"]],redis)==0
    with SessionLocal() as db:
        assert db.get(Event,(item["event_id"],site_id)).path=="/.env"
    reviewed=owner.post(detail_path+"/status",headers=csrf,json={"status":"acknowledged","note":"Reviewed in real PostgreSQL/Redis integration"})
    assert reviewed.status_code==200,reviewed.text
    assert owner.get(detail_path).json()["actions"][0]["status"]=="acknowledged"
    from concurrent.futures import ThreadPoolExecutor
    recovery_payload={"email":registered.json()["email"],"password":"Concurrent-reset-test-passphrase","recovery_code":registered.json()["recovery_code"]}
    def recover_once():
        with TestClient(app,base_url="https://testserver") as anonymous:
            return anonymous.post("/app/api/recover",headers=origin,json=recovery_payload).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _:recover_once(),range(2)))
    assert sorted(outcomes)==[200,401],outcomes
    assert owner.get("/app/api/inbox").status_code==401
'''
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
