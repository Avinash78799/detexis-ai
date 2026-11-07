# Release readiness: 7 November 2026

The complete product goal is **not achieved**. Implemented code, local tests and
temporary demonstrations do not prove a continuously operated public service.
The percentage previously discussed was an effort estimate, not a release gate.

| Requirement | Current evidence | Remaining proof |
| --- | --- | --- |
| ASGI/Flask sensor, bounded/retried fail-open delivery, redaction/features/config/heartbeat | SDK source, sensor/Flask/retry tests, API-stop acceptance | Persistent-host socket/concurrent overhead and actual deployment configuration |
| <5 ms median / <10 ms p95 added latency | ASGI reports; fingerprinted Flask paired report passes both profiles | Actual-host measurement; microbenchmarks do not prove production latency |
| Ingest/Redis/RQ, tenant-key boundary, idempotency, migrations | CI PostgreSQL/Redis checks and concurrency/isolation tests | Actual-host acceptance and abuse/load review |
| Twelve mapped rules, honeytokens, incidents/correlation/baselines | 72 positive/negative rule cases plus pipeline/baseline/triage tests | Representative false-positive review and permissioned traffic |
| Accounts, owner workspace, key/site management, recovery | Account/recovery/isolation tests and prior browser flows | Current HTTPS recovery submission and signed-in error-state browser acceptance |
| Understandable responsive UI | Prior desktop/mobile workspace review; current public-page review | Full keyboard/assistive-technology and authenticated browser checks |
| In-app alerts | Inbox/evidence/audited decisions verified | Real-site operational use; external delivery intentionally deferred until sender setup |
| Verified-domain isolated scanner and scheduled rescans | Scanner tests, isolation configuration and local network checks | Permissioned verified-domain scan on final host; no unverified scan is authorized |
| ML judged by FPR, time/session split and cross-dataset test | Logistic/XGBoost/SHAP software checks; hardened/scalable calibration | Compatible provenance-reviewed datasets, real benign traffic, independent evaluation; ML remains disabled |
| 500 events/s for ten minutes | Full mixed local report passes with 1.608-second p95 and zero final backlog | Actual-host, multi-tenant/concurrent-browser and ML-enabled measurements |
| Durable deployment and operations | Compose/TLS definitions, worker/maintenance health probes, local restore rehearsal | Persistent HTTPS origin, off-host backup restore, monitoring destination, operator contact/privacy/removal process |
| Zero cost and no card | Owner chose computer hosting; no cloud account is required; see `COMPUTER-HOSTING.md` | Working Docker engine, stable reachable HTTPS access for remote sensors, availability and backup arrangements |
| Five to ten real sites and honest resume/demo | Onboarding runbook; synthetic fixtures clearly labeled | Owner permission, installation, observed usage, actual N and demo video |

Next independently actionable work includes deployment-config validation, further
local multi-tenant/abuse checks and accessibility review. External inputs needed
are the chosen computer's operating/backup arrangements, a stable HTTPS origin,
operator contact/backup arrangements, and permissioned owners/traffic. Credit-limited
student hosting, sleeping demos and computer-hosted tunnels cannot be represented
as permanent production hosting. Do not invent timestamps, sessions, labels,
classifier quality or monitored-site counts to close these gates.

Later sensor modes and integrations remain explicit roadmap work in `SENSOR.md`;
their presence in planning documents is not proof they were implemented.
