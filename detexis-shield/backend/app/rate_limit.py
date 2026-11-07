"""Atomic, per-site request/event budgets in a Redis fixed window."""
import math
import os

from fastapi import HTTPException
from redis.exceptions import RedisError

SCRIPT = """
local requests = redis.call('INCR', KEYS[1])
if redis.call('TTL', KEYS[1]) < 0 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local events = redis.call('INCRBY', KEYS[2], ARGV[2])
if redis.call('TTL', KEYS[2]) < 0 then redis.call('EXPIRE', KEYS[2], ARGV[1]) end
return {requests, events, math.max(redis.call('TTL', KEYS[1]), redis.call('TTL', KEYS[2]))}
"""


def enforce_limit(redis, site_id: str, count: int):
    try:
        requests, events, ttl = redis.eval(SCRIPT, 2, f"dxs:limit:{{{site_id}}}:requests",
                                           f"dxs:limit:{{{site_id}}}:events", 60, count)
    except RedisError:
        raise HTTPException(503, "ingest temporarily unavailable", headers={"Retry-After": "2"})
    if requests > int(os.getenv("INGEST_REQUESTS_PER_MINUTE", "6000")) or events > int(os.getenv("INGEST_EVENTS_PER_MINUTE", "60000")):
        raise HTTPException(429, "site ingest budget exceeded",
                            headers={"Retry-After": str(max(1, math.ceil(ttl)))})
