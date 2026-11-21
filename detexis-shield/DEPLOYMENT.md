# Running Shield

The current chosen target is the owner's computer. Start with
[COMPUTER-HOSTING.md](COMPUTER-HOSTING.md); obtaining a cloud server is not required.

The existing app at https://detexis.vercel.app/ is Detexis AI. Shield is a separate
long-running service with PostgreSQL, Redis, workers and an isolated scanner. Root
`vercel.json` and `render.yaml` continue to describe the legacy app. No production
service or cloud resource is created by this pull request.

## Local development

Use Python 3.12. From `detexis-shield/`:

```sh
python -m pip install -r requirements-dev.txt -e sensor-sdk
python -m alembic -c backend/alembic.ini upgrade head
cd backend
python create_site.py demo.local
uvicorn app.main:app --port 8000
```

Run Redis separately, or use Docker Compose below. The raw API key is printed once.
Set `DATABASE_URL` and `REDIS_URL` in every backend process consistently. SQLite is
for local tests; PostgreSQL is required for concurrent production worker locking.

## Full local stack

```sh
docker compose up --build -d
docker compose exec api python create_site.py demo.local
docker compose logs -f api worker maintenance scanner
```

Compose binds API/Postgres/Redis only to loopback. The API applies Alembic migrations
before startup; workers wait for readiness. Scanner ports are not published and its
container does not join the datastore network. `GET /ready` checks DB and Redis;
`GET /health` checks the API process. No scanner probe runs without verification.

Set `SHIELD_API_KEY` and the printed salt as `SHIELD_SALT` in a second terminal, install `demo/requirements.txt`, and run
`uvicorn app:app --app-dir demo --port 9000`. Visit the demo and its `/.env` canary.
Open `http://localhost:8000/dashboard`; enter any username and your site key as the
Basic-auth password. Requests are collected, rules run in RQ and the feed refreshes.

### Repeat the local acceptance test

Use the dedicated validation project, with port 8000 free:

```sh
docker compose -p detexis-shield-validation up --build -d --wait
python tools/validate_stack.py
```

This creates a test site, checks ingest/idempotency/incidents/dashboard, briefly
stops this project's API to test fail-open, restarts it, then sends 500 events/s
for ten minutes. It reports ingestion latency, processing latency, minute-by-minute
backlog, failed RQ jobs and a bounded drain check in `load-test-results.json`.
The test sends only to loopback. It leaves test data in the validation volume.
Acceptance also requires p95 receipt-to-processing lag at most ten seconds by
default (`--max-processing-p95-seconds 10`). See `PROCESSING-LATENCY.md`: after
query, write, index and lock fixes, the latest local run passed at 2.198 seconds
p95. Earlier missed targets are retained. Repeat this gate on the deployment host;
event acceptance alone is not prompt incident delivery.
For a short diagnostic use `--seconds 30`; this is not the full acceptance run.
An optional absolute `SHIELD_VALIDATION_COMPOSE` path supplies a local Compose
override. Reports mark whether an override was used. The default worker uses
rules only; ML-enabled throughput needs a separate measurement.

The Linux worker preloads job modules before RQ forks each job, preserving job
isolation and timeouts. Its child resets the SQLAlchemy pool after a fork. Within
a batch, database reads are reused and Redis operations are pipelined; the site
row lock and transaction still protect grouping and duplicate processing.

## Production preparation

Use a Docker host with a domain for the Shield backend. Copy `.env.example` to
`.env`, choose a long random hexadecimal `POSTGRES_PASSWORD`, set `SHIELD_DOMAIN`,
point its DNS to the host, and then run:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Caddy terminates TLS on 80/443. Confirm backups, firewall rules and restore tests.
See [BACKUP-RESTORE.md](BACKUP-RESTORE.md) for the isolated local rehearsal and
the remaining off-host backup requirements.
Retain PostgreSQL data and Caddy state volumes between releases. Do not expose
datastores or the scanner port publicly. The local default database password is
not a production credential. On one host, scanner isolation is a network and
container boundary, not protection against a host-kernel compromise.

The sensor's background thread requires a persistent Python worker. Do not claim
reliable delivery from Vercel functions with this SDK. A serverless adapter is
future work; use the provided persistent demo for initial end-to-end monitoring.
[Vercel documents bounded function lifecycles](https://vercel.com/docs/functions/runtimes).

## Ownership verification, including vercel.app

Create a Shield site for the exact hostname (no scheme/path), then call
`POST /v1/domain/verification` with its `X-API-Key`. The response provides a token,
TXT record and fixed HTTPS URL. Publish either proof and call `POST /v1/domain/verify`.
Verification lasts seven days and attempts have a one-minute cooldown.

For `detexis.vercel.app`, the legacy app includes an optional well-known route.
After that change is deployed, set Vercel's `SHIELD_VERIFICATION_TOKEN` to the
challenge's complete `value` and redeploy. The route returns 404 when unset. This
enables scanning ownership proof; it does not install a serverless sensor.

Request `POST /v1/scans`, then read `GET /v1/scans/{scan_id}`. Scans are limited to
once per hour manually and are scheduled daily while verification remains valid.
DKIM checks need operator-configured selectors in `Site.settings.dkim_selectors`;
unknown selectors are reported as unassessed rather than guessed.

## Alerts, recovery and retention

Set `SHIELD_ALERT_TARGETS` to a JSON map keyed by site ID. Values can contain
`email`, `slack` (official HTTPS webhook) and `telegram` (numeric chat ID). Configure
SMTP or the Telegram bot token through environment variables. No messages are sent
without destinations. Never commit credentials. Delivery is best effort with at
most five maintenance attempts and per-channel progress; an acknowledged-but-lost
delivery may duplicate externally. One outbox record is created per incident.

Maintenance runs each minute, recovers unprocessed events and pending scans,
delivers notifications and purges records after 30 days by default. Change
`RETENTION_DAYS` on that process; minimum seven days preserves baseline history.
Observe failed RQ jobs and alert outbox status. Data retention also requires a
backup-retention policy outside this code.

Maintenance has a separate Docker health check: it becomes healthy only after
all operations in a cycle succeed. A Redis marker scoped to the container expires
after 180 seconds without success; a restart clears the old marker. Startup has
a 180-second grace period. Inspect `docker compose ps` and maintenance logs when
it becomes unhealthy. A healthy API `/ready` checks database/Redis connectivity
only and does not prove background progress. Docker health status alone does not
restart an unhealthy process or notify an operator; external monitoring and a
response procedure still need configuration. This check does not measure worker
queue delay or scanner availability.

The worker has its own Docker probe using its unique RQ registration, written to
`/tmp/shield-worker-registration` on each process start. It accepts only an idle
or busy worker on the `shield` queue with a live expiring registration and no
death marker. Missing files, Redis failures, suspension and expired registrations
fail the check. RQ's default idle heartbeat expiry can take up to 480 seconds to
reveal a stalled process, plus the 30-second probe interval; a busy worker uses
RQ's shorter monitoring heartbeat. Healthy means registered and heartbeating,
not that jobs are succeeding or meeting latency targets. Monitor failed jobs and
pending-event age separately. An unhealthy container still needs operator action.

## Migration from the original ZIP

The Alembic initial migration expects an empty Shield database. It is not a blind
stamp of the old scaffold schema: event identity is now tenant-scoped and tables
have changed. Preserve an existing starter database and import its events into a
fresh migrated database after review. Do not stamp or delete production data.
The legacy app's root database is separate and is not migrated by Shield.
