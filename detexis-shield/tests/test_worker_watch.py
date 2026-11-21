from redis.exceptions import ConnectionError

from app.worker_watch import watch_registration


class Ticks:
    def __init__(self, steps):
        self.steps = iter(steps)
    def wait(self, interval):
        assert interval == 30
        try:
            callback = next(self.steps)
        except StopIteration:
            return True
        callback()
        return False


def test_expired_registration_recreated_as_heartbeat_only_requests_one_warm_restart(isolated_redis):
    key = "rq:worker:resumed"
    isolated_redis.hset(key, mapping={"last_heartbeat":"timestamp"})
    isolated_redis.expire(key, 480)
    restarts = []
    watch_registration(Ticks([lambda:None]*4), isolated_redis, key, lambda: restarts.append(True))
    assert restarts == [True]


def test_transient_failure_resets_after_native_registration_recovers(isolated_redis):
    key = "rq:worker:transient"
    def recover():
        isolated_redis.hset(key, mapping={"state":"idle", "queues":"shield"})
        isolated_redis.expire(key, 480)
    stop = Ticks([lambda:None, lambda:None, recover, lambda:isolated_redis.delete(key), lambda:None])
    restarts = []
    watch_registration(stop, isolated_redis, key, lambda: restarts.append(True))
    assert not restarts


def test_repeated_redis_errors_request_restart_but_stopping_watcher_does_not():
    class Unavailable:
        def pipeline(self):
            raise ConnectionError()
    restarts = []
    watch_registration(Ticks([]), Unavailable(), "worker", lambda:restarts.append(True))
    assert not restarts
    watch_registration(Ticks([lambda:None]*3), Unavailable(), "worker", lambda:restarts.append(True))
    assert restarts == [True]
