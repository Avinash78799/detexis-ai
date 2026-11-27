"""Preload job modules once, retaining RQ's fork isolation and timeouts on Linux."""
import os
import signal
from threading import Event, Thread

from rq import Queue, Worker

from . import scan_jobs, worker  # noqa: F401: imports are inherited by each fork.
from .db import engine
from .redis_store import get_redis
from .worker_health import REGISTRATION_FILE
from .worker_watch import watch_registration


def main():
    # A fork must never reuse a database connection opened by its parent.
    os.register_at_fork(after_in_child=lambda: engine.dispose(close=False))
    connection = get_redis()
    worker = Worker([Queue("shield", connection=connection)], connection=connection)
    # Keep RQ's unique worker name; a restart must not reuse a stale registration.
    REGISTRATION_FILE.write_text(worker.key)
    stop = Event()
    watcher = Thread(target=watch_registration,
                     args=(stop, connection, worker.key, lambda: os.kill(os.getpid(), signal.SIGTERM)),
                     daemon=True, name="worker-registration-watch")
    watcher.start()
    try:
        # RQ handles SIGTERM as a warm stop: finish an active job first. Compose's
        # unless-stopped policy then starts a fresh uniquely registered worker.
        worker.work()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
