"""Exercise deletion with actual PostgreSQL foreign keys and row locks in CI."""
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(not os.getenv("INTEGRATION_DATABASE_URL"), reason="PostgreSQL/Redis unavailable locally")
def test_account_removal_postgres_transactions_and_inflight_requests():
    env = {**os.environ, "DATABASE_URL": os.environ["INTEGRATION_DATABASE_URL"],
           "REDIS_URL": os.environ["INTEGRATION_REDIS_URL"]}
    migrated = subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
                              env=env, capture_output=True, text=True)
    assert migrated.returncode == 0, migrated.stderr
    script = '''
import sys,uuid
sys.path[:0]=['backend','tests']
from concurrent.futures import ThreadPoolExecutor
from threading import Event as Signal
from fastapi import Depends,Header
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import SessionLocal,get_db
from app.models import Site,IncidentAction
from app.redis_store import get_redis
from test_accounts import register
from test_smoke import event
from test_account_removal import populated_owner,BODY,test_account_removal_erases_owned_history_sessions_and_keys_only
import app.accounts as accounts
import app.main as main_module
from app.auth import current_site

redis=get_redis()
test_account_removal_erases_owned_history_sessions_and_keys_only(redis)
# A deletion waiting for a site must not block an in-flight actor FK check.
with TestClient(app,base_url='https://testserver') as owner:
    headers,created,user_id,incident_id=populated_owner(owner,redis)
    locked_user=Signal()
    original=accounts.locked_owner
    def observed(*args,**kwargs):
        user=original(*args,**kwargs)
        if kwargs.get('no_key_update'):locked_user.set()
        return user
    accounts.locked_owner=observed
    try:
        with SessionLocal() as held,ThreadPoolExecutor(max_workers=1) as pool:
            held.scalar(select(Site).where(Site.id==created['id']).with_for_update())
            future=pool.submit(owner.post,'/app/api/account/delete',headers=headers,json=BODY)
            try:
                assert locked_user.wait(3),'deletion did not lock its owner'
                held.add(IncidentAction(incident_id=incident_id,actor_id=user_id,previous_status='acknowledged',status='acknowledged',note='In-flight owner action'))
                held.commit()
            finally:held.rollback()
            response=future.result(timeout=6)
            assert response.status_code==204,response.text
    finally:accounts.locked_owner=original

# Authentication can finish before deletion; a late insert must return 401, not 500.
with TestClient(app,base_url='https://testserver') as owner:
    headers=register(owner,'race-ingest-'+uuid.uuid4().hex)
    site=owner.post('/app/api/sites',headers=headers,json={'domain':'race-ingest.example'}).json()
    entered,released=Signal(),Signal()
    original=main_module.insert_ignore
    def paused(*args,**kwargs):
        entered.set()
        assert released.wait(6),'ingest gate timed out'
        return original(*args,**kwargs)
    main_module.insert_ignore=paused
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(owner.post,'/v1/events',headers={'X-API-Key':site['api_key']},json={'events':[event()]})
            try:
                assert entered.wait(3)
                response=owner.post('/app/api/account/delete',headers=headers,json=BODY)
                assert response.status_code==204,response.text
            finally:released.set()
            assert future.result(timeout=6).status_code==401
    finally:main_module.insert_ignore=original

# A heartbeat whose key was validated before removal must also finish cleanly.
with TestClient(app,base_url='https://testserver') as owner:
    headers=register(owner,'race-heartbeat-'+uuid.uuid4().hex)
    site=owner.post('/app/api/sites',headers=headers,json={'domain':'race-heartbeat.example'}).json()
    entered,released=Signal(),Signal()
    def paused_site(x_api_key: str | None=Header(None),db=Depends(get_db)):
        site=current_site(x_api_key,db)
        entered.set()
        assert released.wait(6),'heartbeat gate timed out'
        return site
    app.dependency_overrides[current_site]=paused_site
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(owner.post,'/v1/heartbeat',headers={'X-API-Key':site['api_key']})
            try:
                assert entered.wait(3)
                response=owner.post('/app/api/account/delete',headers=headers,json=BODY)
                assert response.status_code==204,response.text
            finally:released.set()
            assert future.result(timeout=6).status_code==401
    finally:app.dependency_overrides.pop(current_site,None)
'''
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
