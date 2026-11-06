"""Container-local maintenance progress, separate from API dependency readiness."""
import socket

from .redis_store import get_redis

MAX_AGE_SECONDS = 180


def progress_key():
    return "shield:maintenance:success:" + socket.gethostname()


def record_success(redis):
    redis.set(progress_key(), "ok", ex=MAX_AGE_SECONDS)


def healthy(redis):
    return redis.get(progress_key()) == b"ok"


if __name__ == "__main__":
    try:
        ok = healthy(get_redis())
    except Exception:
        ok = False
    raise SystemExit(0 if ok else 1)
