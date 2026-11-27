"""Probe this container's RQ registration, including its native heartbeat expiry."""
from pathlib import Path

from .redis_store import get_redis

REGISTRATION_FILE = Path("/tmp/shield-worker-registration")


def healthy(redis, key):
    with redis.pipeline() as pipe:
        pipe.hgetall(key)
        pipe.ttl(key)
        fields, ttl = pipe.execute()
    return (ttl > 0 and not fields.get(b"death")
            and fields.get(b"state") in (b"idle", b"busy")
            and fields.get(b"queues") == b"shield")


if __name__ == "__main__":
    try:
        ok = healthy(get_redis(), REGISTRATION_FILE.read_text().strip())
    except Exception:
        ok = False
    raise SystemExit(0 if ok else 1)
