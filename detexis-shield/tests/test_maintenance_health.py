from types import SimpleNamespace

import pytest

from app import maintenance, maintenance_health, redis_store


def test_only_successful_complete_cycles_refresh_health(isolated_redis, monkeypatch):
    redis = isolated_redis
    monkeypatch.setattr(redis_store, "get_redis", lambda: redis)
    monkeypatch.setattr(maintenance, "tick", lambda: 7)
    assert not maintenance_health.healthy(redis)
    maintenance.run_once()
    assert maintenance_health.healthy(redis)
    assert 0 < redis.ttl(maintenance_health.progress_key()) <= 180
    assert maintenance_health.reported_retention_days(redis) == 7
    assert 0 < redis.ttl(maintenance_health.RETENTION_STATUS_KEY) <= 180

    def fail():
        raise RuntimeError("retention unavailable")

    monkeypatch.setattr(maintenance, "tick", fail)
    redis.delete(maintenance_health.progress_key())
    with pytest.raises(RuntimeError):
        maintenance.run_once()
    assert not maintenance_health.healthy(redis)
    assert maintenance_health.reported_retention_days(redis) == 7


def test_health_is_scoped_to_container_and_expires(isolated_redis, monkeypatch):
    monkeypatch.setattr(maintenance_health.socket, "gethostname", lambda: "maintenance-one")
    maintenance_health.record_success(isolated_redis, 30)
    monkeypatch.setattr(maintenance_health.socket, "gethostname", lambda: "maintenance-two")
    assert not maintenance_health.healthy(isolated_redis)
    monkeypatch.setattr(maintenance_health.socket, "gethostname", lambda: "maintenance-one")
    isolated_redis.expire(maintenance_health.progress_key(), -1)
    assert not maintenance_health.healthy(isolated_redis)
    isolated_redis.expire(maintenance_health.RETENTION_STATUS_KEY, -1)
    assert maintenance_health.reported_retention_days(isolated_redis) is None


def test_recovery_runs_between_full_cycles_and_retries_on_failure(monkeypatch, caplog):
    class EndLoop(Exception):
        pass

    now = 0
    full_cycles, recovery_passes = [], []

    def sleep(seconds):
        nonlocal now
        now += seconds
        if now > 65:
            raise EndLoop

    def recover():
        recovery_passes.append(now)
        if now == 5:
            raise RuntimeError("Temporary queue failure")

    monkeypatch.setattr(maintenance, "time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))
    monkeypatch.setattr(maintenance, "run_once", lambda: full_cycles.append(now))
    monkeypatch.setattr(maintenance, "recover_events", recover)
    with pytest.raises(EndLoop):
        maintenance.run_forever()
    assert full_cycles == [0, 60]
    assert recovery_passes == [*range(5, 60, 5), 65]
    assert "Event recovery failed" in caplog.text
