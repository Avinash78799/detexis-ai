# Product development checkpoint

The active objective is a self-service product with permissioned real users.
This document records current implementation, not a production certification.

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

## Validation checkpoint

234 local tests passed with one real-service test skipped locally after connection
diagnostics. The preceding recovery implementation passed its real-service gate:
CI at `f1ea31e` passed 233 tests with real PostgreSQL/Redis,
including incident evidence/triage and simultaneous one-use recovery attempts;
the separate ML software smoke job also passed. JavaScript syntax checks passed.
The Docker stack rebuilt and started successfully through migration `0006`.
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

## Required before inviting real users

- Measure new dashboard and account routes. Finish accessibility and error-state review.
- Finish recovery browser acceptance and installation guidance for each supported framework. The owner chose
  in-app alerts first; email verification, delivery and email-based resets need a
  configured sender and will be documented rather than silently simulated.
- Deployment configuration validation, off-host backup/restore, session/key
  abuse review, operational monitoring and public privacy/retention guidance.
- Persistent hosting within the user's zero-paid-services budget. A temporary
  computer-hosted Cloudflare tunnel is a development demonstration.
- Permissioned site-owner onboarding and observed usage. Synthetic requests and
  test accounts must never be counted as actual customer adoption.

The existing benchmark proves the documented local rules-only workload only.
Representative ML data/evaluation, deployment-specific performance and live
notification delivery remain separate acceptance work.
