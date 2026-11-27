from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from rq import Queue
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import sessionmaker

from app import worker
from app.auth import new_api_key
from app.db import Base, get_db
from app.main import app
from app.models import ApiKey, Event, HourBucket, Site
from test_smoke import event


def test_concurrent_publishers_cannot_overfill_the_event_queue(isolated_redis, monkeypatch):
    monkeypatch.setattr(worker, "EVENT_QUEUE_HIGH_WATER", 4)
    for item in range(3):
        assert worker.enqueue_batch("site", [str(item)], isolated_redis) is not None
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = list(pool.map(lambda item: worker.enqueue_batch("site", [str(item)], isolated_redis),
                             range(3, 19)))
    queue = Queue("shield", connection=isolated_redis)
    assert sum(job is not None for job in jobs) == 1
    assert queue.count == 4
    assert len(isolated_redis.keys("rq:job:*")) == 4


def test_saturated_queue_keeps_requests_for_later_recovery(isolated_redis, monkeypatch, tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "queue.db").as_posix())
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def use_fixture_db():
        with sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, use_fixture_db)
    monkeypatch.setattr(worker, "SessionLocal", sessions)
    monkeypatch.setattr(worker, "EVENT_QUEUE_HIGH_WATER", 2)
    keys = []
    with sessions() as db:
        for domain in ("queue-a.test", "queue-b.test"):
            site = Site(domain=domain)
            db.add(site)
            db.flush()
            raw, prefix, digest = new_api_key()
            db.add(ApiKey(site_id=site.id, prefix=prefix, key_hash=digest))
            keys.append(raw)
        db.commit()

    queue = Queue("shield", connection=isolated_redis)
    items = [event(f"/fixture-{i}") for i in range(6)]
    try:
        with TestClient(app) as client:
            for i, item in enumerate(items):
                response = client.post("/v1/events", json={"events": [item]},
                                       headers={"X-API-Key": keys[i % 2]})
                assert response.status_code == 202
                assert response.json() == {"accepted": 1, "duplicates": 0, "queued": i < 2}
            for _ in range(20):
                assert worker.recover_pending(redis=isolated_redis) == 0
                assert queue.count == 2
        with sessions() as db:
            assert len(db.scalars(select(Event).where(Event.processed_at.is_(None))).all()) == 6

        def drain():
            for job in queue.jobs:
                assert worker.process_batch(*job.args, redis=isolated_redis) == len(job.args[1])
                job.delete()
            assert queue.count == 0

        drain()
        stamp = datetime.now(timezone.utc)
        cutoff = stamp - timedelta(seconds=15)
        with sessions.begin() as db:
            db.execute(update(Event).where(Event.event_id.in_([item["event_id"] for item in items[2:4]]))
                       .values(received_at=stamp - timedelta(seconds=16)))
            db.execute(update(Event).where(Event.event_id.in_([item["event_id"] for item in items[4:]]))
                       .values(received_at=cutoff))
        assert worker.recover_pending(redis=isolated_redis, received_before=cutoff) == 2
        drain()
        assert worker.recover_pending(redis=isolated_redis, received_before=cutoff) == 0
        assert worker.recover_pending(redis=isolated_redis, received_before=stamp) == 2
        drain()
        assert worker.recover_pending(redis=isolated_redis) == 0
        with sessions() as db:
            assert len(db.scalars(select(Event).where(Event.processed_at.is_not(None))).all()) == 6
            assert sorted(db.scalars(select(func.sum(HourBucket.count)).group_by(HourBucket.site_id))) == [3, 3]
    finally:
        engine.dispose()
