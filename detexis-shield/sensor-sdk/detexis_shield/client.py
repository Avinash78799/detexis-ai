import json
import math
import queue
import random
import threading
import time
from email.utils import parsedate_to_datetime

import httpx


RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MAX_RETRY_DELAY = 2.0


def retry_after_seconds(value: str) -> float:
    """Support Retry-After's integer seconds or HTTP date; ignore invalid values."""
    try:
        value = value.strip()
        if value.isascii() and value.isdigit():
            return float(value)
        date = parsedate_to_datetime(value)
        if date.tzinfo is not None:
            return max(0.0, date.timestamp() - time.time())
    except (ValueError, TypeError, OverflowError):
        pass
    return 0.0


class ShieldClient:
    """Buffers events and ships them in the background.
    Fail-open: submissions do not wait for network I/O or available queue capacity.
    Events may be discarded when the backend is unavailable or the buffer is full.
    """

    def __init__(self, api_url: str, api_key: str, batch_size: int = 50,
                 flush_interval: float = 3.0, max_buffer: int = 5000,
                 max_retries: int = 2):
        if not isinstance(batch_size, int) or not 1 <= batch_size <= 100:
            raise ValueError("batch_size must be between 1 and 100")
        if not isinstance(max_buffer, int) or max_buffer < 1:
            raise ValueError("max_buffer must be positive")
        if not math.isfinite(flush_interval) or flush_interval <= 0:
            raise ValueError("flush_interval must be finite and positive")
        if type(max_retries) is not int or not 0 <= max_retries <= 5:
            raise ValueError("max_retries must be an integer between 0 and 5")
        self.api_url = api_url.rstrip("/")
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.q: queue.Queue = queue.Queue(maxsize=max_buffer)
        self._dropped = 0
        self._state_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, event: dict) -> None:
        with self._state_lock:
            if self._stop.is_set():
                self._dropped += 1
                return
            try:
                self.q.put_nowait(event)
            except queue.Full:
                self._dropped += 1  # drop, never wait for buffer space

    @property
    def dropped(self) -> int:
        with self._state_lock:
            return self._dropped

    def _drop(self, count: int) -> None:
        with self._state_lock:
            self._dropped += count

    def _run(self) -> None:
        batch: list[dict] = []
        try:
            with httpx.Client(timeout=3.0) as http:
                last = time.monotonic()
                while not self._stop.is_set():
                    try:
                        batch.append(self.q.get(timeout=0.5))
                    except queue.Empty:
                        pass
                    if self._stop.is_set():
                        break
                    due = time.monotonic() - last >= self.flush_interval
                    if batch and (len(batch) >= self.batch_size or due):
                        self._send(http, batch)
                        batch, last = [], time.monotonic()
        except Exception:
            pass  # A sender failure must not escape into the host application.
        finally:
            with self._state_lock:
                self._stop.set()
                self._dropped += len(batch)
                while True:
                    try:
                        self.q.get_nowait()
                        self._dropped += 1
                    except queue.Empty:
                        break

    def _send(self, http: httpx.Client, batch: list[dict]) -> None:
        try:
            payload = json.dumps({"events": batch}, default=str)
        except Exception:
            self._drop(len(batch))
            return
        for attempt in range(self.max_retries + 1):
            if self._stop.is_set():
                break
            retry_after = 0.0
            try:
                response = http.post(f"{self.api_url}/v1/events", headers=self.headers,
                                     content=payload)
                if 200 <= response.status_code < 300:
                    return
                if response.status_code not in RETRYABLE_STATUS:
                    break
                retry_after = retry_after_seconds(response.headers.get("Retry-After", ""))
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
                pass
            except Exception:
                break  # Invalid URLs, serialization errors, etc. will not heal on retry.
            if attempt == self.max_retries or retry_after > MAX_RETRY_DELAY:
                break
            ceiling = min(MAX_RETRY_DELAY, 0.25 * (2 ** attempt))
            delay = max(retry_after, random.uniform(0, ceiling))
            if self._stop.wait(delay):  # Shutdown interrupts backoff immediately.
                break
        self._drop(len(batch))  # Count loss once, not once per failed attempt.

    def close(self) -> None:
        with self._state_lock:
            self._stop.set()
        self._thread.join(timeout=5)
