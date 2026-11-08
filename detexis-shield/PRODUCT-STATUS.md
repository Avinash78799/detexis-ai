# Product development checkpoint

The active objective is a self-service product with permissioned real users.
This document records current implementation, not a production certification.

8 November: authenticated `/app/analyze` adds bounded request-rule inspection
and optional isolated ClamAV file-signature scanning. Real benign/EICAR engine
acceptance passed; see `THREAT-ANALYSIS.md` and its fingerprinted runtime report.
The new analysis UI has Node interaction coverage but still needs rendered browser
acceptance. The root Detexis app is prepared as a lightweight entry point; the
old analyzer source is archived and its POST routes explain migration (410).
Vercel production migration is not verified or claimed; see `../MIGRATION.md`.

## Owner workflow implemented

- `/` opens `/app`: account registration/sign-in and owner workspace.
- Argon2id password hashes, expiring/revocable hashed browser sessions, Secure /
  HttpOnly / SameSite cookies, same-origin and CSRF checks, Redis login limits.
- Add a website, receive sensor credentials once, and view installation examples.
- Owner-scoped dashboards/feed, key listing/creation/revocation and domain
  verification/scan actions. Sensor keys remain separate from account sessions.
- Expired session cleanup in maintenance; additive migration `0004` leaves
  pre-existing CLI-created sites unclaimed rather than assigning ownership.
- Configuration scan check details are visible in the dashboard.
- In-app incident inbox across owned websites, bounded evidence, stable cursor
  pagination, acknowledge/resolve/false-positive decisions and action history.
  Another matching event reopens a resolved incident; false-positive review
  remains scoped to that incident and does not automatically train the model.
  Triage changes are rate-limited and all reads/writes enforce owner isolation.
- Offline one-use recovery codes, authenticated code rotation and password changes
  with revocation of old browser sessions. See `ACCOUNT-RECOVERY.md`; email is a
  sign-in identifier until a sender and verification flow are configured.
- Owner-scoped connection diagnostics distinguish active keys, missing/overdue
  heartbeats, request receipt and latest-event processing. They provide next steps
  without exposing request data or claiming that a quiet site is offline.
  See `CONNECTION-DIAGNOSTICS.md` for the query-plan investigation and migration
  `0007`, which adds a covering index for older high-volume sites.
- Public `/app/install` guidance provides a pinned-source SDK command, executable
  FastAPI/Flask examples, secret setup, persistent-process limitations and connection
  checks. `/app/data` describes collection, redaction limits, access, retention,
  operator-managed removal and backup responsibilities before account creation.
- Dashboard update status warns on refresh failures and expired sessions, provides
  manual retry/navigation and records successful update times. Refresh requests
  time out after ten seconds. Node regression coverage exercises failure, recovery
  and retry behavior; fresh browser inspection of these controls remains pending.
- Account and inbox requests share a fifteen-second timeout and actionable
  offline/server/session-expiry errors. Timed-out mutations warn that completion
  is uncertain and are never automatically retried. Node tests cover these paths;
  both templates render with the shared helper loaded first. Browser review of
  these states remains pending.

## Validation checkpoint

On 7 November, the current local suite passed 251 Python tests (one real-service
test skipped locally) and six Node UI failure/recovery tests. The completed
mixed-load report's worker hash matches current source. The earlier checkpoint
history below records separately scoped CI and browser evidence.

240 local tests passed with one real-service test skipped after the maintenance
health and incident-retention race changes; six additional worker-health tests
passed after that checkpoint. Worker and maintenance Docker probes were verified
healthy in the running stack. CI at `a60fb76` passed 238 tests with real PostgreSQL/Redis,
including concurrent ingestion/worker exclusion, incident triage and one-use recovery races;
the separate ML software smoke job also passed. JavaScript syntax checks passed.
The Docker stack rebuilt and started successfully through migration `0008`.
A custom-format database restore into a separate database preserved 899,915
synthetic events and passed the recorded integrity checks in `BACKUP-RESTORE.md`.
A real browser previously verified
signup, adding a website, opening its owner dashboard, sign-out and sign-in with
the saved website still present. The mobile workspace was inspected at a
390-pixel viewport. Test accounts and `.example` sites are synthetic.
Public HTTPS acceptance additionally verified account/site creation, event ingest,
real-worker incident generation, evidence, acknowledgment and audit history.
Browser acceptance verified connection guidance on desktop and at 390 pixels,
mobile incident evidence/history, and saving a resolved decision with its audit
entry. Both inspected mobile pages had no horizontal document overflow.
The pinned-source SDK command built a wheel successfully. Tests execute both
framework examples extracted from the actual guide page and verify redacted
sensor events. The installation guide was inspected at a mobile breakpoint.
The revised signed-in workspace has separate website controls, incident/setup
navigation and a setup checklist; desktop and 390-pixel browser review passed
without horizontal overflow. The public data-handling link/page also worked.

The 7 November ten-minute mixed run accepted and processed 300,000 events at
500.104 events/s, with zero HTTP/transport failures, failed jobs or final backlog.
Processing median/p95 was 0.135/1.608 seconds, passing the ten-second local target.
`mixed-load-batched-600s.json` records runtime/source/settings. `MIXED-LOAD.md`
retains the prior 17.814-second failure; older uniform results and investigations
remain in `PROCESSING-LATENCY.md`.

## Required before inviting real users

- The owner chose computer hosting, removing the cloud-account requirement.
  See `COMPUTER-HOSTING.md` for the isolated instance launcher, HTTPS access,
  restart/availability limits and private backup commands.

- Measure actual deployment and multi-tenant/concurrent-browser performance;
  the passing mixed local workload is rules-only, one site and 128 client hashes.
- Warm sequential owner-route application latency was measured against real
  PostgreSQL/Redis with 10,000 synthetic events; dashboard p95 was 44.087 ms.
  See `OWNER-ROUTE-PERFORMANCE.md` for scope and reproduction. Concurrent/deployed
  browser measurements, accessibility and error-state review remain required.
- Finish recovery browser acceptance. The owner chose
  in-app alerts first; email verification, delivery and email-based resets need a
  configured sender and will be documented rather than silently simulated.
- Deployment configuration validation, off-host backup/restore, session/key
  abuse review, operational monitoring and deployment-specific operator/privacy details.
- Computer-hosted operation within the zero-paid-services budget: a stable
  reachable HTTPS address, power/internet availability and recovery procedures.
- Permissioned site-owner onboarding and observed usage. Synthetic requests and
  test accounts must never be counted as actual customer adoption.

The existing benchmark proves the documented local rules-only workload only.
Representative ML data/evaluation, deployment-specific performance and live
notification delivery remain separate acceptance work.
