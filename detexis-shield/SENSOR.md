# Sensor: implemented behavior and roadmap

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
| Retries | Bounded exponential jitter and short Retry-After support; retains event IDs for idempotency |
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
not Flask, network/server or production measurements. Automated tests cover
buffer pressure, retries, request exceptions and fail-open behavior; the Docker
validation also checks a host response while the real ingest API is stopped.

## Not included yet

- Dedicated Django integration/validation and a Node/Express package.
- Reverse-proxy mode, browser JavaScript/CSP script monitoring and auto-hardening.
- Opt-in redacted body capture or response body inspection.
- Fake API-key/DB-record traps and account-aware credential-stuffing detection.
- Offline/downtime alerts, MITRE mappings and LLM-written incident summaries.
- LLM-app firewall, account-takeover, ASN/device/travel and API-abuse analysis.
- Blocking or an experimental block switch. V1 always monitors and alerts.
- PyPI publication, 24/7 hosted operations and a real-site monitoring trial.

A honeytoken request is a signal for review, not proof of an attacker: authorized
scanners and security tests can also trigger it. ML smoke tests verify software
behavior; a real classifier and false-positive measurements still need reviewed
traffic and compatible datasets.
