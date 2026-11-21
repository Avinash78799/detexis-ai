"""Container-only removal acceptance on a disposable, populated synthetic restore.

Never targets computer hosting. Authenticated ASGI requests exercise the real
PostgreSQL transaction and a dedicated Redis throttle. No worker/delivery runs.
"""
from datetime import datetime, timedelta, timezone
import hashlib
from http.cookies import SimpleCookie
import json
import os
import re
import secrets
import time
from urllib.parse import urlsplit

from sqlalchemy import select, text, func
from sqlalchemy.engine import make_url


def validate_targets(database_url, redis_url):
    database, redis = make_url(database_url), urlsplit(redis_url)
    if (database.drivername != 'postgresql+psycopg2' or database.host != 'db'
            or database.port not in (None, 5432) or database.username != 'detexis' or database.query):
        raise ValueError('Only the isolated fixture database host is allowed')
    if not re.fullmatch(r'shield_restore_[a-f0-9]{12}_removal', database.database or ''):
        raise ValueError('Only a disposable restored removal database is allowed')
    if (redis.scheme != 'redis' or not re.fullmatch(r'shield-removal-redis-[a-f0-9]{12}', redis.hostname or '')
            or redis.port != 6379 or redis.path != '/0' or redis.username or redis.password
            or redis.query or redis.fragment):
        raise ValueError('Only a dedicated disposable Redis service is allowed')


def main():
    validate_targets(os.environ['DATABASE_URL'], os.environ['REDIS_URL'])
    from fastapi import Response
    from fastapi.testclient import TestClient
    from app.main import app
    from app.accounts import COOKIE, hasher, issue_session
    from app.auth import new_api_key
    from app.db import SessionLocal, engine
    from app.models import (User, Site, ApiKey, Event, Incident, IncidentAction, Scan,
                            SensorHealthAlert, BrowserSession, Alert, HourBucket)
    from app.redis_store import get_redis

    redis = get_redis()
    if redis.dbsize():
        raise RuntimeError('Redis must be fresh and empty')
    clients, headers, keys, owners, site_ids = [], [], [], [], []
    origin = 'https://removal.example'
    password = secrets.token_urlsafe(32)
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.id)).all()
        sites = db.scalars(select(Site).order_by(Site.owner_id)).all()
        if (len(users) != 4 or len(sites) != 4 or len({site.owner_id for site in sites}) != 4
                or any(not re.fullmatch(r'perf-[a-f0-9]{32}@example\.test', user.email) for user in users)
                or {site.domain for site in sites} != {f'tenant-{i}.example' for i in range(4)}):
            raise RuntimeError('Expected exactly four synthetic performance owners/sites')
        event_count = db.scalar(select(func.count()).select_from(Event))
        pending = db.scalar(select(func.count()).select_from(Event).where(Event.processed_at.is_(None)))
        if event_count != 300004 or pending:
            raise RuntimeError('Expected the fully processed populated load-test restore')
        for user in users:
            site = next(site for site in sites if site.owner_id == user.id)
            owners.append(user.id)
            site_ids.append(site.id)
            if len(owners) == 1:
                user.password_hash = hasher.hash(password)
            raw, prefix, verifier = new_api_key()
            db.add(ApiKey(site_id=site.id, prefix=prefix, key_hash=verifier))
            keys.append(raw)
        db.commit()
        now = datetime.now(timezone.utc)
        for user, site_id in zip(users, site_ids):
            incidents = db.scalars(select(Incident).where(Incident.site_id == site_id)).all()
            if not incidents:
                raise RuntimeError('Expected incidents on every fixture site')
            for incident in incidents:
                for _ in range(10):
                    db.add(IncidentAction(incident_id=incident.id, actor_id=user.id,
                                         previous_status='open', status='acknowledged', note='Synthetic removal benchmark note'))
            for index in range(50):
                db.add(Scan(site_id=site_id, status='complete', result={'fixture':True,'note':'x' * 1024}))
                stamp = now - timedelta(minutes=index + 1)
                db.add(SensorHealthAlert(site_id=site_id, opened_at=stamp, heartbeat_at=stamp,
                                         resolved_at=now, resolution='heartbeat_resumed'))
            db.add(SensorHealthAlert(site_id=site_id, opened_at=now, heartbeat_at=now))
        db.commit()
        # Reuse normal session issuance; no existing fixture password is known.
        # Only the target owner's password was reset, in this disposable copy.
        for user in users:
            response = Response()
            issued = issue_session(db, user, response)
            cookie = SimpleCookie()
            cookie.load(response.headers['set-cookie'])
            client = TestClient(app, base_url=origin)
            client.cookies.set(COOKIE, cookie[COOKIE].value, domain='removal.example', path='/')
            clients.append(client)
            headers.append({'Origin':origin, 'X-CSRF-Token':issued['csrf_token']})

    target_owner, target_site = owners[0], site_ids[0]
    predicates = {'users':'t.id != :owner', 'browser_sessions':'t.user_id != :owner',
                  'sites':'t.id != :site', 'incident_actions':'t.incident_id IN (SELECT id FROM incidents WHERE site_id != :site)'}
    for table in ['api_keys','events','incidents','alerts','hour_buckets','scans','sensor_health_alerts']:
        predicates[table] = 't.site_id != :site'

    def other_tenants():
        result = {}
        with engine.connect() as connection:
            for table, predicate in predicates.items():
                rows = connection.execution_options(stream_results=True).execute(text(
                    f'SELECT row_to_json(t)::text FROM {table} t WHERE {predicate} ORDER BY row_to_json(t)::text COLLATE "C"'),
                    {'owner':target_owner, 'site':target_site})
                digest, count = hashlib.sha256(), 0
                for row in rows:
                    digest.update(row[0].encode() + b'\n')
                    count += 1
                result[table] = {'rows':count, 'sha256':digest.hexdigest()}
        return result

    site_models = [ApiKey,Event,Incident,Alert,HourBucket,Scan,SensorHealthAlert]
    with SessionLocal() as db:
        target_counts = {model.__tablename__:db.scalar(select(func.count()).select_from(model).where(model.site_id == target_site))
                         for model in site_models}
        target_counts['incident_actions'] = db.scalar(select(func.count()).select_from(IncidentAction).where(
            IncidentAction.incident_id.in_(select(Incident.id).where(Incident.site_id == target_site))))
    before = other_tenants()
    for client in clients:
        if client.get('/app/api/session').status_code != 200:
            raise RuntimeError('Fixture session could not authenticate')
    started = time.perf_counter()
    response = clients[0].post('/app/api/account/delete', headers=headers[0],
                                json={'password':password, 'confirmation':'DELETE'})
    duration = time.perf_counter() - started
    if response.status_code != 204:
        raise RuntimeError('Populated account removal did not return 204')
    if duration >= 10:
        raise RuntimeError('Observed removal exceeded the ten-second acceptance budget')
    if clients[0].get('/app/api/session').status_code != 401:
        raise RuntimeError('Removed owner session remains usable')
    if clients[0].get('/v1/config', headers={'X-API-Key':keys[0]}).status_code != 401:
        raise RuntimeError('Removed sensor key remains usable')
    with SessionLocal() as db:
        if db.get(User, target_owner) or db.get(Site, target_site):
            raise RuntimeError('Removed owner/site remains')
        if db.scalar(select(func.count()).select_from(BrowserSession).where(BrowserSession.user_id == target_owner)):
            raise RuntimeError('Removed owner still has sessions')
        for model in site_models:
            if db.scalar(select(func.count()).select_from(model).where(model.site_id == target_site)):
                raise RuntimeError('Owned history survived removal')
        if db.scalar(select(func.count()).select_from(IncidentAction).where(IncidentAction.actor_id == target_owner)):
            raise RuntimeError('Owner action references survived removal')
    if other_tenants() != before:
        raise RuntimeError('Another tenant changed')
    for client, key in zip(clients[1:], keys[1:]):
        if client.get('/app/api/sites').status_code != 200 or client.get('/v1/config', headers={'X-API-Key':key}).status_code != 200:
            raise RuntimeError('Another owner lost access')
    for client in clients:
        client.close()
    print(json.dumps({'passed':True, 'removal_seconds':duration, 'target_rows_removed':target_counts,
                      'other_tenant_digests_unchanged':before, 'remaining_owners':3,
                      'removed_session_and_key_rejected':True, 'other_sessions_and_keys_accepted':True,
                      'scope':'One warm restored-copy ASGI request with real PostgreSQL/Redis; restoration, seeding and full-row fingerprinting warmed storage. No external HTTPS, browser timing, concurrent traffic, worker/maintenance activity or production deletion.'}))


if __name__ == '__main__':
    main()
