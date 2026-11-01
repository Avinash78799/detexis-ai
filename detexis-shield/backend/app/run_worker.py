"""Preload job modules once, retaining RQ's fork isolation and timeouts on Linux."""
import os

from rq import Queue, Worker

from . import scan_jobs, worker  # noqa: F401: imports are inherited by each fork.
from .db import engine
from .redis_store import get_redis


def main():
    # A fork must never reuse a database connection opened by its parent.
    os.register_at_fork(after_in_child=lambda: engine.dispose(close=False))
    connection = get_redis()
    Worker([Queue("shield", connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
