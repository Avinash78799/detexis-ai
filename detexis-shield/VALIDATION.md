# Isolated full-stack performance validation

Run from this directory with the development Python dependencies and sensor SDK
installed. Docker Compose 2.24.4 or later is required for the port override.

```powershell
$env:SHIELD_VALIDATION_PROJECT='detexis-shield-validation-v2'
$env:SHIELD_VALIDATION_COMPOSE=(Join-Path (Get-Location) 'docker-compose.validation.yml')
$env:SHIELD_VALIDATION_URL='http://127.0.0.1:18000'
docker compose -p $env:SHIELD_VALIDATION_PROJECT -f docker-compose.yml -f docker-compose.validation.yml up --build -d --wait
python tools/validate_stack.py --rate 500 --seconds 600 --profile mixed_comments --output mixed-comments-v2-600s.json
```

Use the dedicated project only. The override publishes API port 18000 on
loopback and removes PostgreSQL/Redis host ports. It does not inherit the
computer-hosting credentials or volumes. The runner verifies that its HTTP
origin belongs to that Compose project's API before creating fixtures or
stopping its API for a fail-open check. Do not layer this override onto the
computer-hosted or customer instance.

The runner creates and retains a synthetic site and API key in the test database;
credentials are captured privately by the process and are not printed in its
report. It sends three setup events, checks idempotency, incident creation and
authenticated dashboard access, then checks that an instrumented host responds
while the validation API is stopped. The API is restarted before load begins.
No external website is scanned and no malware engine is enabled by this stack.

`mixed_comments` sends 80% benign-shaped events, 10% sensitive-path probes and
10% SQL-comment-separated UNION SELECT examples, across 128 synthetic IP hashes
for one site. `mixed` retains the previous plain-SQL workload. Neither measures
representative recall or false-positive rate.

A completed acceptance report requires all intended events accepted and stored,
no transport failures, an empty pending/queued backlog, no failed jobs, achieved
duration/rate within the existing 5% tolerance, and processing p95 at most ten
seconds. It also verifies that all processed events carry the measured detector
fingerprint and that the mixed workload's expected SQL detections exist.
HTTP 202 alone is insufficient. Setup events count in the stored total and
processing distribution, but not the reported workload acceptance rate.

Reports are saved atomically at startup, each minute, while draining and at
completion. A `running` or `draining` checkpoint is incomplete and does not prove
that its process is still running. Check the actual process/tool session before
starting another run. Failed or interrupted runs must not be relabeled as passes.

These are local loopback, rules-only, single-site measurements. Docker resources,
database history, other applications and desktop activity affect them. They do
not establish internet/TLS latency, SDK overhead, multi-tenant capacity,
concurrent browser responsiveness, ML capacity, or a production SLA.

After a completed test, stop only this project's containers, retaining its
synthetic database for inspection:

```powershell
docker compose -p $env:SHIELD_VALIDATION_PROJECT -f docker-compose.yml -f docker-compose.validation.yml stop
```

Do not prune shared Docker images or remove unrelated applications or volumes.
