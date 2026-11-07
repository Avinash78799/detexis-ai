import pytest

from app import maintenance, maintenance_health, redis_store


def test_only_successful_complete_cycles_refresh_health(isolated_redis, monkeypatch):
    redis = isolated_redis
    monkeypatch.setattr(redis_store, "get_redis", lambda: redis)
    monkeypatch.setattr(maintenance, "tick", lambda: None)
    assert not maintenance_health.healthy(redis)
    maintenance.run_once()
    assert maintenance_health.healthy(redis)
    assert 0 < redis.ttl(maintenance_health.progress_key()) <= 180

    def fail():
        raise RuntimeError("retention unavailable")

    monkeypatch.setattr(maintenance, "tick", fail)
    redis.delete(maintenance_health.progress_key())
    with pytest.raises(RuntimeError):
        maintenance.run_once()
    assert not maintenance_health.healthy(redis)


def test_health_is_scoped_to_container_and_expires(isolated_redis, monkeypatch):
    monkeypatch.setattr(maintenance_health.socket, "gethostname", lambda: "maintenance-one")
    maintenance_health.record_success(isolated_redis)
    monkeypatch.setattr(maintenance_health.socket, "gethostname", lambda: "maintenance-two")
    assert not maintenance_health.healthy(isolated_redis)
    monkeypatch.setattr(maintenance_health.socket, "gethostname", lambda: "maintenance-one")
    isolated_redis.expire(maintenance_health.progress_key(), -1)
    assert not maintenance_health.healthy(isolated_redis)
