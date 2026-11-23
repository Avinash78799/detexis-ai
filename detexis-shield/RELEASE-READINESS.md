# Release readiness: 23 November 2026

The complete product goal is **not achieved**. Implemented code, local tests and
temporary demonstrations do not prove a continuously operated public service.
The percentage previously discussed was an effort estimate, not a release gate.

## Onboarding activation: 23 November

Commit `1498c1a8c31e113817e753c94a90593bbe8bbaa9` passed all four jobs in
[Actions run 45117433756](https://github.com/Avinash78799/detexis-ai/actions/runs/45117433756).
The installation guide now pins the tested SDK source, including the query-decoder
optimization, and explains Python's local CA bundle configuration. Ten focused
installation/decoder tests passed. A credential-free HTTPX request to local HTTPS
readiness passed using public roots plus the reviewed local root; the initial
connection refusal occurred while Docker's engine was stopped and remains a
failed check, followed by the successful check after engine restart.

After backup `outputs/computer-backups/shield-20261123T052449Z-f19bd2ee.dump`, only
the API was replaced with image
`sha256:118e368573dce3ce54e79f94719728573ac4bfd04c889a0ee8ab01c7078abe24`.
All 65 source files matched; environment and database row digests were unchanged.
Worker/maintenance containers were preserved. CA-verified readiness and the served
installation pin/CA guidance passed. Private evidence:
`outputs/onboarding-tls-runtime-20261123.json`. Cached dependencies remain; this
does not automatically upgrade already installed customer SDKs or prove a new
signed-in browser flow. The complete product goal remains open.

## Maintenance correction: 23 November

Seven-day cleanup previously removed the seventh same-hour aggregate during the
current hour, making the anomaly baseline unavailable despite complete history.
Commit `06e896559964748732ee051f1fef1ca44fa31bd7` preserves the complete boundary
hour; raw-event expiry retains its exact cutoff. Six boundary regressions cover
two sites, seven/thirty-day retention and three minute positions. All 18 focused
retention/pipeline/maintenance tests passed, followed by all four jobs in
[Actions run 45112459471](https://github.com/Avinash78799/detexis-ai/actions/runs/45112459471).

The maintenance service alone was updated after fresh private backup
`outputs/computer-backups/shield-20261123T043419Z-a7264fc1.dump`. Its image is
`sha256:135ca30dcea5dec837f96593bb40062808f7ee722587b4443424ec1fcf5cf6e9`;
all 65 application/migration files matched source. Environment and command,
API/worker container identities and all database table row digests were preserved.
Maintenance health and CA-verified HTTPS readiness passed. Cached dependencies
were retained; no migration, owner-account change or public deployment occurred.
Private evidence: `outputs/retention-boundary-runtime-20261123.json`.
This check does not establish cleanup concurrency, long-outage recovery or ML
quality. The smaller-data route remains in `ml/SMALL-DATA-ROUTE.md`; no further
full-day packet downloads are required from the owner.

## Release gates

| Requirement | Current evidence | Remaining proof |
| --- | --- | --- |
| Keep pace with changing threats | ClamAV signature updates/stale-definition refusal; locally active rule release 2026.11.21.1, owner coverage inventory, source fingerprints, CI release gate, SQL/evasion and assignment-boundary regressions; see `RULE-RELEASES.md` | Activate/observe dependency updates; advisory relevance checks, independent FPR evaluation, rendered coverage-page review and traffic/job rollback scenarios |
| Replace legacy predictions with evidence-based analysis | Authenticated request/file browser flows, desktop/mobile checks, six real-engine harmless fixtures including archive-limit review; 335 CI Python / 12 Node tests; see `ANALYSIS-UI-REVIEW.md` | Broader file compatibility, failure-state browser checks and resource/abuse load; harmless fixtures do not prove real-malware recall/FPR |
| Connect the existing Detexis deployment | Lightweight root entry, preserved archive/data, HTTPS-origin validation, ownership proof and migration tests | Vercel preview, configured live Shield origin and verified production rollout; legacy accounts/history are intentionally separate |
| ASGI/Flask sensor, bounded/retried fail-open delivery, redaction/features/config/heartbeat | SDK source, sensor/Flask/retry tests, API-stop acceptance | Persistent-host socket/concurrent overhead and actual deployment configuration |
| <5 ms median / <10 ms p95 added latency | Sequential reports plus two calibrated four-client Windows version-2 prepared-GET runs passed all per-client gates: worst median 0.696 ms and p95 3.245 ms; online delivery/redaction and offline loss accounting passed (`concurrent-sensor-check.json`). Earlier version-1 failures and no-sensor noise remain retained (`SOCKET-OVERHEAD.md`) | Remote/TLS and representative deployed workloads, version-2 Linux comparison and long-lived operation; request preparation is explicitly outside the version-2 timing interval |
| Ingest/Redis/RQ, tenant-key boundary, idempotency, migrations | CI PostgreSQL/Redis checks and concurrency/isolation tests | Actual-host acceptance and abuse/load review |
| Twelve mapped rules, honeytokens, incidents/correlation/baselines | 72 positive/negative rule cases plus pipeline/baseline/triage tests | Representative false-positive review and permissioned traffic |
| Accounts, owner workspace, key/site management, recovery/removal | PostgreSQL race/HTTPS CI and backup-first local activation; one isolated warm removal erased 75,001 events, 384 incidents and 3,840 actions in 0.219 s while other tenants' row digests/access stayed intact (`ACCOUNT-REMOVAL.md`) | Current HTTPS recovery submission, rendered removal/error-state/accessibility acceptance, larger/concurrent removal measurements |
| Understandable responsive UI | Prior desktop/mobile workspace review; current public-page review; failed website-list loading preserves the signed-in workspace, one-time recovery code and stale cards with an explicit refresh action (JavaScript regression tests) | Full keyboard/assistive-technology, Chrome-specific and refresh/error-state browser checks; the local embedded-browser synthetic registration, coverage navigation and three request-inspector submissions passed on 21 November (`ANALYSIS-UI-REVIEW.md`) |
| In-app alerts | Inbox/evidence/audited decisions verified | Real-site operational use; external delivery intentionally deferred until sender setup |
| Verified-domain isolated scanner and scheduled rescans | Scanner tests, isolation configuration and local network checks | Permissioned verified-domain scan on final host; no unverified scan is authorized |
| ML judged by FPR, time/session split and cross-dataset test | Logistic/XGBoost/SHAP checks; calibration; complete CSIC audits; CIC structure/CSV audits, generated-flow archive transfer/CRC/schema checks (2,830,743 labeled rows plus 288,602 counted blank records), and paired 54,713-frame development-corpus replay: old rules 140 matches, corrected rules zero (`ml/CIC-DOWNLOAD-AUDIT.md`) | Compatible request-level attack/benign samples with validated time/session metadata and labels through the smaller-data route (`ml/SMALL-DATA-ROUTE.md`), independent real benign traffic and ML evaluation; more full-day captures are no longer requested from the owner; corrected-corpus rule counts are not independent ML evidence; ML remains disabled |
| 500 events/s for ten minutes | Current version 3 passed with three workers: 499.844 events/s for 600.187 seconds, processing p95 5.654 seconds, owner-read p95 314.106 ms and zero final backlog. Three workers are active locally; earlier two-worker and single-worker failures remain retained (`MULTITENANT-PERFORMANCE.md`) | Concurrent-browser, broader traffic/abuse and ML-enabled measurements; investigate historical local worker restarts; sequential socket overhead is separate evidence in `SOCKET-OVERHEAD.md` |
| Durable deployment and operations | Compose/TLS definitions, worker/maintenance health probes; isolated active-job registration-loss rehearsal completed once before one warm restart in 122.844 seconds (`WORKER-RECOVERY.md`); populated host-copy recovery (`BACKUP-RESTORE.md`); 400 committed pending events recovered after queue loss, with duplicate RQ/HTTP delivery preserving counters/outbox (`QUEUE-RECOVERY.md`) | Persistent HTTPS origin, off-host backup restore, live application cutover, prolonged-outage queue growth, populated scans/triage actions, monitoring destination, operator contact/privacy/removal process |
| Zero cost and no card | Owner chose computer hosting; no cloud account is required; see `COMPUTER-HOSTING.md` | Working Docker engine, stable reachable HTTPS access for remote sensors, availability and backup arrangements |
| Five to ten real sites and honest resume/demo | Onboarding runbook; synthetic fixtures clearly labeled | Owner permission, installation, observed usage, actual N and demo video |

## Local workspace update checked on 21 November

Commit `86149bd52fe3f7d515a1d80fe62e50ee95fb6501` passed all four jobs in
Actions run `44518911644`. Its workspace-list recovery change is now installed
in local API image `sha256:6fb15266266b704e31e1e64b1ab6c16b28292f7e4c6b6f7953cfad14b81ffd8b`.
The existing Docker engine/services were stopped when inspected. They were resumed
using their saved configuration; the API was updated after a fresh private backup
and a candidate-source comparison. All database table row digests remained equal,
including both existing accounts. Cached dependencies were retained.

Read-only, CA-verified HTTPS checks passed for readiness and the new refresh
assets. API, both workers, maintenance, database, Redis and ClamAV became healthy;
the scanner and local proxy were running. The first HTTPS check encountered an
expired cached leaf immediately after proxy start. Caddy's logs then confirmed
renewal under the existing local CA; the subsequent verified check passed without
bypassing TLS or installing trust. Private evidence:
`outputs/workspace-refresh-runtime.json` and backup
`outputs/computer-backups/shield-20261121T043444Z-62d1b687.dump`.
No owner account/session/key was changed by these activation checks. Rendered
signed-in refresh/error-state acceptance remains open.

## Earlier local update checked on 17 November

GitHub Actions run `44046751761` passed all four jobs: 346 Python tests,
JavaScript checks, dependency audit, Windows helpers, local HTTPS account flow
and ML software smoke. This does not establish classifier quality.

The computer instance was backed up before updating API, worker and maintenance
to migration `0009`. The cached candidate's 63 application/migration files matched
the current source; it reused the existing dependency image rather than fetching
new packages. Previous images were preserved. All three updated services became
healthy. Read-only checks confirmed both existing accounts remained, schema/index
creation, CA-verified HTTPS readiness and unauthenticated owner-API refusal.
The owner also reports that Chrome opens the local page without a certificate
warning. Automated signed-in desktop-browser acceptance remains incomplete:
the browser tool stopped because it could not verify the Incognito URL.
The upgraded database was restored from its private host backup into a separate
database: both user rows matched, constraints validated and the partial unique
health index survived. Site/health history was empty; off-device and populated
history recovery are not established. See `BACKUP-RESTORE.md`.

Next independently actionable work includes deployment-config validation, further
local multi-tenant/abuse checks and accessibility review. External inputs needed
are the chosen computer's operating/backup arrangements, a stable HTTPS origin,
operator contact/backup arrangements, and permissioned owners/traffic. Credit-limited
student hosting, sleeping demos and computer-hosted tunnels cannot be represented
as permanent production hosting. Do not invent timestamps, sessions, labels,
classifier quality or monitored-site counts to close these gates.

Later sensor modes and integrations remain explicit roadmap work in `SENSOR.md`;
their presence in planning documents is not proof they were implemented.

Owner steering on 15 November: keep computer hosting local; no new public tunnel
is being opened. The former temporary hostname expired. A loopback-only Caddy HTTPS configuration and CA-verified account/coverage CI
flow now pass. Windows activation and owner-reported trusted-browser setup now work; public availability and permissioned
remote-site trials remain deferred, not completed.
