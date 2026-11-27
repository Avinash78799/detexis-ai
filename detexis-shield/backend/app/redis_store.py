import os
from functools import lru_cache

from redis import Redis


@lru_cache
def get_redis():
    return Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                          socket_timeout=1, socket_connect_timeout=1)
