import json
import queue
import threading
import time

import httpx


class ShieldClient:
    """Buffers events and ships them in the background.
    Fail-open: a full buffer or a dead backend drops events, never slows or breaks the site."""

    def __init__(self, api_url: str, api_key: str, batch_size: int = 50,
                 flush_interval: float = 3.0, max_buffer: int = 5000):
        if not isinstance(batch_size, int) or not 1 <= batch_size <= 100:
            raise ValueError("batch_size must be between 1 and 100")
        if not isinstance(max_buffer, int) or max_buffer < 1:
            raise ValueError("max_buffer must be positive")
        if flush_interval <= 0:
            raise ValueError("flush_interval must be positive")
        self.api_url = api_url.rstrip("/")
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.q: queue.Queue = queue.Queue(maxsize=max_buffer)
        self.dropped = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, event: dict) -> None:
        try:
            self.q.put_nowait(event)
        except queue.Full:
            self.dropped += 1  # drop, never block

    def _run(self) -> None:
        with httpx.Client(timeout=3.0) as http:
            last = time.monotonic()
            batch: list[dict] = []
            while not self._stop.is_set():
                try:
                    batch.append(self.q.get(timeout=0.5))
                except queue.Empty:
                    pass
                due = time.monotonic() - last >= self.flush_interval
                if batch and (len(batch) >= self.batch_size or due):
                    self._send(http, batch)
                    batch, last = [], time.monotonic()
            if batch:
                self._send(http, batch)

    def _send(self, http: httpx.Client, batch: list[dict]) -> None:
        try:
            response = http.post(f"{self.api_url}/v1/events", headers=self.headers,
                                 content=json.dumps({"events": batch}, default=str))
            response.raise_for_status()
        except Exception:
            self.dropped += len(batch)  # TODO(you): small retry with backoff

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
