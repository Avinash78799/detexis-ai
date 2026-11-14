"""Warm-restart a worker whose native RQ registration has stopped being valid.

An expired Redis hash can be recreated with only last_heartbeat after a suspended
computer resumes. The process still exists, but its native registration is broken.
Do not turn that partial hash into a healthy result or forcibly kill an active job.
"""
import logging
from redis.exceptions import RedisError
from .worker_health import healthy


def watch_registration(stop, redis, key, request_restart, *, interval=30, failures=3):
    missed = 0
    while not stop.wait(interval):
        try:
            ok = healthy(redis, key)
        except (RedisError, OSError):
            ok = False
        missed = 0 if ok else missed + 1
        if missed >= failures:
            logging.warning("Worker registration is unhealthy; requesting a warm restart")
            request_restart()
            return
