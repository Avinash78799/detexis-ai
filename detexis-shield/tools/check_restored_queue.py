"""Container-only pending-event recovery acceptance on a disposable restored DB.

Requires a fresh, unpublished shield-replay-redis-* service on an internal
network, and a shield_restore_*_replay database. Never targets computer hosting.
Uses actual FastAPI ASGI ingestion, PostgreSQL, Redis and native RQ fork workers;
does not test external HTTP/TLS or run maintenance/notification delivery.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import uuid
from urllib.parse import urlsplit

from sqlalchemy import select, text
from sqlalchemy.engine import make_url


def validate_targets(database_url, redis_url):
    database = make_url(database_url)
    redis = urlsplit(redis_url)
    if database.drivername != "postgresql+psycopg2" or database.host != "db":
        raise ValueError("Only the isolated fixture database host is allowed")
    if not re.fullmatch(r"shield_restore_[a-z0-9_]+_replay", database.database or ""):
        raise ValueError("Only a disposable restored replay database is allowed")
    if redis.scheme != "redis" or not re.fullmatch(r"shield-replay-redis-[a-f0-9]+", redis.hostname or ""):
        raise ValueError("Only a dedicated disposable Redis service is allowed")
    if redis.port != 6379 or redis.path != "/0" or redis.username or redis.password or redis.query or redis.fragment:
        raise ValueError("Unexpected Redis target options")


def main():
    validate_targets(os.environ["DATABASE_URL"], os.environ["REDIS_URL"])
    from fastapi.testclient import TestClient
    from rq import Queue, Worker
    from rq.registry import FailedJobRegistry, StartedJobRegistry
    from app.auth import new_api_key
    from app.db import SessionLocal, engine
    from app.main import app
    from app.models import ApiKey, Event, Site
    from app.redis_store import get_redis
    from app.rule_manifest import RULES_SHA256
    from app.worker import enqueue_batch, recover_pending

    redis = get_redis()
    if redis.dbsize() != 0:
        raise RuntimeError("Redis must be newly created and empty")
    queue = Queue("shield", connection=redis)
    def snapshot():
        with engine.connect() as c:
            return {"events": c.execute(text("SELECT count(*) FROM events")).scalar_one(),
                    "pending": c.execute(text("SELECT count(*) FROM events WHERE processed_at IS NULL")).scalar_one(),
                    "incidents": c.execute(text("SELECT count(*) FROM incidents")).scalar_one(),
                    "incident_events": c.execute(text("SELECT coalesce(sum(event_count),0) FROM incidents")).scalar_one(),
                    "alerts": c.execute(text("SELECT count(*) FROM alerts")).scalar_one(),
                    "hour_count": c.execute(text("SELECT coalesce(sum(count),0) FROM hour_buckets")).scalar_one()}

    def business_digest():
        hashes = {}
        with engine.connect() as c:
            for table in ["incidents", "alerts", "hour_buckets"]:
                digest = hashlib.sha256()
                for row in c.execution_options(stream_results=True).execute(text(
                        f'SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text COLLATE "C"')):
                    digest.update(row[0].encode() + b"\n")
                hashes[table] = digest.hexdigest()
        return hashes

    def drain():
        # Same fork/timeout worker class and DB fork protection as the normal runner.
        worker = Worker([queue], connection=redis)
        worker.work(burst=True, logging_level="WARNING")
        if queue.count or StartedJobRegistry("shield", connection=redis).count or FailedJobRegistry("shield", connection=redis).count:
            raise RuntimeError("Queue did not drain cleanly")

    baseline = snapshot()
    if baseline["events"] < 1 or baseline["pending"] != 0:
        raise RuntimeError("Expected a populated, fully processed restored fixture")
    with SessionLocal() as db:
        sites = db.execute(select(Site.id, Site.domain).order_by(Site.id)).all()
        if len(sites) != 4 or any(not site.domain.endswith(".example") for site in sites):
            raise RuntimeError("Expected exactly four synthetic .example sites")
        keys = {}
        for site_id, _domain in sites:
            raw, prefix, key_hash = new_api_key()
            db.add(ApiKey(site_id=site_id, prefix=prefix, key_hash=key_hash))
            keys[site_id] = raw
        db.commit()
    payloads = {}
    for site_id, _domain in sites:
        client_hash = hashlib.sha256(("queue-restore-" + str(uuid.uuid4())).encode()).hexdigest()
        payloads[site_id] = [{"event_id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc).isoformat(),
                              "ip_hash": client_hash, "method": "GET", "path": "/.env" if i % 5 == 0 else "/restore-benign",
                              "status": 404 if i % 5 == 0 else 200, "latency_ms": 1} for i in range(100)]
    with TestClient(app) as client:
        for site_id, _domain in sites:
            response = client.post("/v1/events", headers={"X-API-Key": keys[site_id]}, json={"events": payloads[site_id]})
            if response.status_code != 202 or response.json() != {"accepted": 100, "duplicates": 0, "queued": True}:
                raise RuntimeError("Expected durable API acceptance and initial enqueue")
        accepted = snapshot()
        if accepted["events"] != baseline["events"] + 400 or accepted["pending"] != 400 or queue.count != 4:
            raise RuntimeError("Expected 400 pending rows and four queued batches")
        # This Redis service is dedicated to this rehearsal, never an existing stack.
        redis.flushdb()
        if queue.count != 0 or snapshot() != accepted:
            raise RuntimeError("Queue loss must not change durable database rows")
        recovered = [recover_pending(redis=redis), recover_pending(redis=redis)]
        if recovered != [400, 400] or queue.count != 8:
            raise RuntimeError("Both recovery passes must discover the committed pending rows")
        engine.dispose()
        os.register_at_fork(after_in_child=lambda: engine.dispose(close=False))
        drain()
        processed = snapshot()
        if processed["pending"] or processed["events"] != accepted["events"]:
            raise RuntimeError("Recovered rows did not finish processing")
        if processed["incident_events"] - baseline["incident_events"] != 80 or processed["hour_count"] - baseline["hour_count"] != 400:
            raise RuntimeError("Recovery duplicated incident or baseline counters")
        if processed["alerts"] - baseline["alerts"] != processed["incidents"] - baseline["incidents"]:
            raise RuntimeError("Expected one alert record per new incident")
        with SessionLocal() as db:
            for site_id, _domain in sites:
                ids = [row["event_id"] for row in payloads[site_id]]
                rows = db.scalars(select(Event).where(Event.site_id == site_id, Event.event_id.in_(ids))).all()
                if len(rows) != 100 or sum(bool(row.findings) for row in rows) != 20:
                    raise RuntimeError("Unexpected tenant-scoped findings")
                if any(row.features.get("rules_source_sha256") != RULES_SHA256 for row in rows):
                    raise RuntimeError("Recovered events lack the expected rule fingerprint")
        before_replay = business_digest()
        for site_id, _domain in sites:
            enqueue_batch(site_id, [row["event_id"] for row in payloads[site_id]], redis)
        drain()
        if snapshot() != processed or business_digest() != before_replay or recover_pending(redis=redis) != 0:
            raise RuntimeError("Duplicate RQ delivery changed committed business state")
        for site_id, _domain in sites:
            response = client.post("/v1/events", headers={"X-API-Key": keys[site_id]}, json={"events": payloads[site_id]})
            if response.status_code != 202 or response.json() != {"accepted": 0, "duplicates": 100, "queued": True}:
                raise RuntimeError("HTTP retry was not idempotent")
        if snapshot() != processed or queue.count:
            raise RuntimeError("HTTP retry changed durable or queue state")
    print(json.dumps({"passed": True, "baseline": baseline, "after_accept": accepted, "after_recovery": processed,
                      "recovery_passes": recovered, "lost_jobs": 4, "recovered_jobs_including_duplicates": 8,
                      "duplicate_delivery_jobs": 4, "http_duplicate_events": 400, "final_queue": 0,
                      "failed_jobs": 0, "rules_source_sha256": RULES_SHA256,
                      "business_digests_after_duplicate_delivery": before_replay,
                      "worker_class": "rq.worker.Worker", "scope": "ASGI ingest; native RQ fork workers; real PostgreSQL/Redis. No external HTTP/TLS, alerts, scanner or ML."}))


if __name__ == "__main__":
    main()
