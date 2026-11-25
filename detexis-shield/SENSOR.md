# Sensor: implemented behavior and roadmap

For sites added in the owner workspace, the sensor key can submit events,
send heartbeats and read sensor configuration. Use the signed-in workspace to
view monitoring history or manage domain verification and scans. Existing
SDK installations keep using the same key.

SDK 0.1.2 adds the optional `outage_retry_window` setting for ASGI and WSGI.
For example, `outage_retry_window=30` lets a failed batch make spaced retries
within 30 seconds of its first send attempt. Existing short retry settings
remain the default. After a retryable failure, the sender retains one batch
and accepts new events into the same bounded queue. It honors `Retry-After`
within the configured window. Permanent errors and `max_retries=0` retain
their existing behavior.

Each process holds at most `max_buffer` queued events plus one batch. A full
queue drops new telemetry, and closing the process discards unsent events.
The retry window can be set up to 120 seconds and does not make the buffer
durable. Size it for the rate and available memory on each application worker.

The installed 0.1.2 wheel passed a Windows loopback rehearsal using a real
ASGI host and a collector returning HTTP 503 for 12 seconds. All 66 host
requests succeeded. A 40-event queue and one in-flight slot retained 41
events, which arrived after recovery with unique IDs and redacted query values.
The other 25 events were counted as overflow drops. This check covers one
host process and a synthetic collector. Private evidence is in
`outputs/sdk-0.1.2-release/outage-runtime.json`.

SDK source release 0.1.1 added masking for bracket/dot secret-name components such
as `credentials[password]` and `auth.token`. The local API, workers and maintenance
were updated to that version for its shared feature and redaction helpers. The
outage setting runs in each instrumented website process. Existing sensors
need the new version, configuration and a process restart to enable it.
Built-wheel installation evidence for 0.1.1 is in `sdk-wheel-check.json`.
Earlier latency reports predate 0.1.1 and
remain scoped to their recorded version. New attested 0.1.1 four-client Windows
loopback runs passed the stated gates; see `sdk-011-socket-check.json` and
`SOCKET-OVERHEAD.md` for measurements and limits. Named-field masking is not comprehensive
PII detection and does not scrub previously stored telemetry.

The sensor is the core of Shield. It records HTTP request/response metadata in a
persistent Python application and sends events to the authenticated ingest API.
It observes requests that reach the wrapped application, not requests served by a
CDN or rejected upstream. Response bodies and WebSocket traffic are not captured.

## What this build includes

| Capability | Current behavior |
| --- | --- |
| FastAPI/Starlette | Pure ASGI middleware |
| Flask | WSGI adapter, including streaming response cleanup |
| Event fields | Method, bounded path/query/user agent, status, latency, daily site-salted IP hash, flags and four URL-derived features |
| Privacy | Named sensitive query values are masked before submission. Bodies, cookies and authorization headers are not collected. Arbitrary secrets in paths, user agents or other query values can still be present. |
| Buffer and batching | Default 5,000 queued events, batches of 50, nominal three-second flush interval; drops when full |
| Retries | Bounded exponential jitter, Retry-After support, and optional longer retry window; retains event IDs for idempotency |
| Fail-open | Request-time telemetry errors are contained; network delivery runs in a background thread |
| Honeytokens | Configured path signals, initially `/.env` and `/admin-backup`; the worker independently checks them |
| Configuration | Polls `/v1/config` every 60 seconds by default; applies validated honeytoken paths and always remains monitor-only |
| Heartbeat | Sends `/v1/heartbeat` roughly every 60 seconds; dashboard shows the last received timestamp |
| Dashboard | Authenticated HTMX feed refreshes every five seconds after events are ingested and processed |
| Detection | Rules with CWE/OWASP tags, optional validated ML artifact, per-site volume baseline and incident correlation |

Background network work can delay batch/config/heartbeat delivery. These intervals
are not hard real-time guarantees. Heartbeats describe the sensor process, not an
independent uptime check of the website. The feed does not yet classify the sensor
as online/offline or send downtime alerts.

`payload_len` is the byte length of the stored URL representation, not the request
body size. The other features are `special_char_ratio`, `num_params` and
`path_depth`; see [FEATURES.md](FEATURES.md). The worker recomputes features and
derives site identity from the authenticated API key, never an event payload.

## Install from this repository

The package has not been published to PyPI. From `detexis-shield/`:

```sh
python -m pip install ./sensor-sdk
```

For an existing FastAPI app:

```python
import os
from detexis_shield import ShieldMiddleware

app.add_middleware(
    ShieldMiddleware,
    api_url=os.environ["SHIELD_URL"],
    api_key=os.environ["SHIELD_API_KEY"],
    site_salt=os.environ["SHIELD_SALT"],
    outage_retry_window=30,
)
```

For an existing Flask app:

```python
import os
from detexis_shield import ShieldWSGIMiddleware

app.wsgi_app = ShieldWSGIMiddleware(
    app.wsgi_app,
    api_url=os.environ["SHIELD_URL"],
    api_key=os.environ["SHIELD_API_KEY"],
    site_salt=os.environ["SHIELD_SALT"],
    outage_retry_window=30,
)
```

Use the unique site salt and key printed by `backend/create_site.py`. Behind a
proxy, configure trusted client-IP handling in the host server; the SDK does not
blindly trust forwarded IP headers. Use persistent worker processes; this sensor
has not been validated for Vercel's bounded function lifecycle. Initialize it in
each worker, not in a pre-fork server master that already has background threads.

## Measurements

The recorded Windows/Python 3.12 ASGI in-process measurements use 10,000 requests
per variant and a simulated backend connection failure:

| Profile | Median added time | p95 added time |
| --- | ---: | ---: |
| Normal query | 0.0494 ms | 0.0862 ms |
| Large query | 1.07665 ms | 1.7761 ms |

Both meet the <5 ms median / <10 ms p95 targets in that microbenchmark. These are
not Flask, network/server or production measurements. A separate Flask paired
test-client run on 7 November measured normal-query added median/p95 of
0.090/0.492 ms and large-query added median/p95 of 0.749/2.410 ms. Its real
sender used an unavailable loopback backend and every response completed.
See `flask-overhead-20261107.json` and `tools/benchmark_flask_sensor.py`.
This does not establish deployed-server or concurrent overhead. Automated tests cover
buffer pressure, retries, request exceptions and fail-open behavior; the Docker
validation also checks a host response while the real ingest API is stopped.

## Loopback TCP measurements

On 15 November the real-socket ASGI cases met the <5 ms median / <10 ms p95
added-latency targets. A threaded Werkzeug WSGI harness failed three p95 cases;
two subsequent Waitress 3.0.2 runs passed with unchanged SDK code and targets.
`SOCKET-OVERHEAD.md` preserves every result and its limits. These sequential
Windows/loopback measurements are stronger than in-process tests, but do not
establish concurrent, remote-TLS or arbitrary deployed-server performance.

## Not included yet

- Dedicated Django integration/validation and a Node/Express package.
- Reverse-proxy mode, browser JavaScript/CSP script monitoring and auto-hardening.
- Opt-in redacted body capture or response body inspection.
- Fake API-key/DB-record traps and account-aware credential-stuffing detection.
- MITRE mappings and LLM-written incident summaries.
- Browser push and external delivery of sensor-health signals (in-app history is implemented in `SENSOR-HEALTH.md`).
- LLM-app firewall, account-takeover, ASN/device/travel and API-abuse analysis.
- Blocking or an experimental block switch. V1 always monitors and alerts.
- PyPI publication, 24/7 hosted operations and a real-site monitoring trial.

A honeytoken request is a signal for review, not proof of an attacker: authorized
scanners and security tests can also trigger it. ML smoke tests verify software
behavior; a real classifier and false-positive measurements still need reviewed
traffic and compatible datasets.

Heartbeat-gap source update: previously reporting sites now have tenant-scoped
in-app signals and resumption history, checked by maintenance. Migration 0009,
rollout scope and operational limits are in `SENSOR-HEALTH.md`. This is not an
attack verdict or proof that a website is offline.
