# Sensor validation and Flask adapter

Run from the project root:

```sh
python -m pip install -r requirements-dev.txt -e sensor-sdk
python -m pytest -q -p no:cacheprovider
python benchmark_sensor.py
```

## Flask usage

Install Flask in your application environment, then wrap the WSGI app once:

```python
import os
from flask import Flask
from detexis_shield import ShieldWSGIMiddleware

app = Flask(__name__)
sensor = ShieldWSGIMiddleware(
    app.wsgi_app,
    api_url=os.environ["SHIELD_API_URL"],
    api_key=os.environ["SHIELD_API_KEY"],
    site_salt=os.environ["SHIELD_SITE_SALT"],
)
app.wsgi_app = sensor

@app.get("/")
def home():
    return "Hello from the monitored site"
```

Create the client in each serving worker, after any process fork. Call
`sensor.client.close()` on worker shutdown, never on Flask's per-request teardown.
Shutdown cancels backoff and discards/counts unsent events. It does not flush the
whole queue; see [RETRIES.md](RETRIES.md) for the delivery and shutdown contract.

## What changed

- WSGI adapter shares ASGI event construction, redaction and daily IP hashing.
- Response chunks pass through lazily, without buffering or reading request bodies.
- Response cleanup is forwarded, including early close; each response emits at most one event.
- Telemetry exceptions cannot replace successful responses or host application exceptions.
- Invalid buffer/batch settings fail at setup. Batch size cannot exceed the ingest cap.
- HTTP error responses now count the affected events as dropped.

The WSGI adapter follows response iteration and cleanup requirements in
[PEP 3333](https://peps.python.org/pep-3333/). The SDK itself does not require Flask.
The tests exercise both WSGI directly and a real Flask app, including POST body
preservation, streaming, redaction and host exceptions. Use Python 3.12, matching
the Docker image and CI configuration.

## How to explain it

The ASGI sensor wraps the response sender. WSGI uses `start_response` plus a body
iterator, so its adapter captures status there and observes the iterator's end or
close. Both submit the same event format to a bounded queue. Network work happens
in the sender thread. Catching telemetry errors preserves application behavior;
application errors still propagate normally.

Latency covers the whole response, including streaming, rather than only time to
first byte. An exception after headers were sent retains the sent HTTP status.
Only configured honeytoken paths receive a flag; the adapter does not create routes.
Forwarded IP headers are ignored by the sensor. Configure trusted proxies in the
host app if required; otherwise the hash represents the direct peer.

## Validation and remaining work

77 tests passed locally, including feature extraction, Unicode adapter parity,
real Flask integration, retry/shutdown cases and an ingest regression test for a
lost acknowledgement. See benchmark-results.json and benchmark-large-query.json
for the measured microbenchmark. It uses the real buffer and sender thread with
simulated network failure. This establishes local overhead only; server-level
median/p95 and production behavior still need measurement on the deployment host.

Shared request features are implemented; see [FEATURES.md](FEATURES.md). Phase 1
is still incomplete: Redis rate
limiting and Alembic remain. Startup configuration errors are intentionally raised;
runtime fail-open tests do not promise the sensor can never fail under any condition.
Docker Compose now waits for PostgreSQL readiness before starting the API. A full
Docker/PostgreSQL run has not been performed locally; the API tests use SQLite.
