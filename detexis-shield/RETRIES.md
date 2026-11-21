# Bounded delivery retries

The sensor retries on its sender thread, never on a website request's execution
path. The default is one attempt plus two retries; set `max_retries=0` to disable
retries, or choose an integer up to five through either middleware's constructor.

Retryable outcomes are connection/network errors, timeouts, remote protocol errors,
and HTTP 408, 429, 500, 502, 503 or 504. Other responses, including authentication
and validation errors, are discarded without retries. Redirects are not followed.

The same serialized batch and event IDs are reused on every attempt. This lets
the ingest API deduplicate a retry even if the original batch committed and its
acknowledgement was lost. It does not guarantee delivery: the queue is in memory
and the retry budget can run out.

Backoff uses full jitter: a random delay between zero and an exponentially growing
ceiling, starting at 0.25 seconds and capped at two seconds. Valid `Retry-After`
seconds or dates impose a minimum wait. If that minimum exceeds two seconds, the
batch is discarded instead of retrying too early or tying up the sender longer.
Malformed values use the ordinary jittered delay. See
[RFC 9110, Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.3).
The retryable exception classes follow [HTTPX's exception hierarchy](https://www.python-httpx.org/exceptions/).

Shutdown cancels backoff, prevents additional attempts, and discards/counts pending
queued and partial batches when the sender exits. New submissions after shutdown
are counted as discarded. `close()` waits up to five seconds for the worker; it
cannot cancel an HTTP call already in progress. The HTTPX timeout remains three
seconds per I/O operation, not a total batch deadline. See
[HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/).

`dropped` counts locally discarded events whose acceptance was not confirmed, once
per batch rather than once per failed attempt. A timed-out request may already
have committed on the backend. Counts are synchronized across request and sender
threads. After a shutdown join timeout, final accounting completes when the
sender exits. A sender startup failure also discards the queue and stops accepting
new events, keeping the host application running.

Tests cover retry budgets, capped waits, permanent errors, `Retry-After`, real
worker shutdown, and a committed batch followed by a lost acknowledgement.
