import pytest

from app.worker_health import healthy


@pytest.mark.parametrize("state", ["idle", "busy"])
def test_registered_worker_is_healthy(isolated_redis, state):
    redis = isolated_redis
    key = "rq:worker:own"
    redis.hset(key, mapping={"state": state, "queues": "shield"})
    redis.expire(key, 480)
    assert healthy(redis, key)
    assert not healthy(redis, "rq:worker:other")
    redis.expire(key, -1)
    assert not healthy(redis, key)


@pytest.mark.parametrize("fields", [
    {"state": "suspended", "queues": "shield"},
    {"state": "idle", "queues": "other"},
    {"state": "busy", "queues": "shield", "death": "timestamp"},
])
def test_nonserving_registration_is_unhealthy(isolated_redis, fields):
    isolated_redis.hset("rq:worker:own", mapping=fields)
    isolated_redis.expire("rq:worker:own", 480)
    assert not healthy(isolated_redis, "rq:worker:own")


def test_registration_without_heartbeat_expiry_is_unhealthy(isolated_redis):
    isolated_redis.hset("rq:worker:own", mapping={"state": "idle", "queues": "shield"})
    assert not healthy(isolated_redis, "rq:worker:own")
