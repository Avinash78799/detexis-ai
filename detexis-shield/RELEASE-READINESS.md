# Release readiness: 18 November 2026

The complete product goal is **not achieved**. Implemented code, local tests and
temporary demonstrations do not prove a continuously operated public service.
The percentage previously discussed was an effort estimate, not a release gate.

| Requirement | Current evidence | Remaining proof |
| --- | --- | --- |
| Keep pace with changing threats | ClamAV signature updates and stale-definition refusal; versioned rule release 2026.11.14.1, owner coverage inventory, source fingerprints, CI release gate, SQL-comment/evasion regressions and empty-instance rollback; see `RULE-RELEASES.md` | Activate/observe dependency updates; advisory relevance checks, representative FPR evaluation, rendered coverage-page review and traffic/job rollback scenarios |
| Replace legacy predictions with evidence-based analysis | Authenticated request/file browser flows, desktop/mobile checks, six real-engine harmless fixtures including archive-limit review; 335 CI Python / 12 Node tests; see `ANALYSIS-UI-REVIEW.md` | Broader file compatibility, failure-state browser checks and resource/abuse load; harmless fixtures do not prove real-malware recall/FPR |
| Connect the existing Detexis deployment | Lightweight root entry, preserved archive/data, HTTPS-origin validation, ownership proof and migration tests | Vercel preview, configured live Shield origin and verified production rollout; legacy accounts/history are intentionally separate |
| ASGI/Flask sensor, bounded/retried fail-open delivery, redaction/features/config/heartbeat | SDK source, sensor/Flask/retry tests, API-stop acceptance | Persistent-host socket/concurrent overhead and actual deployment configuration |
| <5 ms median / <10 ms p95 added latency | ASGI reports; fingerprinted Flask paired report passes both profiles | Loopback TCP ASGI passes and two production-Windows-WSGI comparisons pass; Werkzeug failures retained in `SOCKET-OVERHEAD.md`. Concurrent/deployed workloads remain unverified |
| Ingest/Redis/RQ, tenant-key boundary, idempotency, migrations | CI PostgreSQL/Redis checks and concurrency/isolation tests | Actual-host acceptance and abuse/load review |
| Twelve mapped rules, honeytokens, incidents/correlation/baselines | 72 positive/negative rule cases plus pipeline/baseline/triage tests | Representative false-positive review and permissioned traffic |
| Accounts, owner workspace, key/site management, recovery | Account/recovery/isolation tests and prior browser flows | Current HTTPS recovery submission and signed-in error-state browser acceptance |
| Understandable responsive UI | Prior desktop/mobile workspace review; current public-page review | Full keyboard/assistive-technology and authenticated browser checks |
| In-app alerts | Inbox/evidence/audited decisions verified | Real-site operational use; external delivery intentionally deferred until sender setup |
| Verified-domain isolated scanner and scheduled rescans | Scanner tests, isolation configuration and local network checks | Permissioned verified-domain scan on final host; no unverified scan is authorized |
| ML judged by FPR, time/session split and cross-dataset test | Logistic/XGBoost/SHAP software checks; hardened/scalable calibration | Compatible provenance-reviewed datasets, real benign traffic, independent evaluation; ML remains disabled |
| 500 events/s for ten minutes | Four-site two-worker rules-only run passes at 500.248 events/s, 4.200-second processing p95, 205.093-ms worst owner HTTP p95 and no final backlog. Equivalent single-worker failure retained (`MULTITENANT-PERFORMANCE.md`); single-site evidence in `MIXED-LOAD.md` | Concurrent-browser, broader traffic/abuse and ML-enabled measurements; sequential socket overhead is separate evidence in `SOCKET-OVERHEAD.md` |
| Durable deployment and operations | Compose/TLS definitions, worker/maintenance health probes; host-copy restore matches 300,004 synthetic events, 1,536 incidents/alerts and seeded open/resumed health history, with complete-row/schema/sequence comparisons (`BACKUP-RESTORE.md`) | Persistent HTTPS origin, off-host backup restore, application cutover/pending replay, populated scans/triage actions, monitoring destination, operator contact/privacy/removal process |
| Zero cost and no card | Owner chose computer hosting; no cloud account is required; see `COMPUTER-HOSTING.md` | Working Docker engine, stable reachable HTTPS access for remote sensors, availability and backup arrangements |
| Five to ten real sites and honest resume/demo | Onboarding runbook; synthetic fixtures clearly labeled | Owner permission, installation, observed usage, actual N and demo video |

## Local update checked on 17 November

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
