"""Container-local maintenance progress, separate from API dependency readiness."""
import socket

from redis.exceptions import RedisError

from .redis_store import get_redis

MAX_AGE_SECONDS = 180
RETENTION_STATUS_KEY = "shield:maintenance:retention-days"


def progress_key():
    return "shield:maintenance:success:" + socket.gethostname()


def record_success(redis, retention_days):
    with redis.pipeline() as pipe:
        pipe.set(progress_key(), "ok", ex=MAX_AGE_SECONDS)
        pipe.set(RETENTION_STATUS_KEY, retention_days, ex=MAX_AGE_SECONDS)
        pipe.execute()


def reported_retention_days(redis):
    try:
        days = int(redis.get(RETENTION_STATUS_KEY))
    except (TypeError, ValueError, RedisError):
        return None
    return days if days >= 7 else None


def healthy(redis):
    return redis.get(progress_key()) == b"ok"


if __name__ == "__main__":
    try:
        ok = healthy(get_redis())
    except Exception:
        ok = False
    raise SystemExit(0 if ok else 1)
