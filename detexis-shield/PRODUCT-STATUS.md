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

## Validation checkpoint

227 local tests passed with one real-service CI test skipped locally after the
incident inbox implementation. Focused owner/key/scan/dashboard/retention
checks passed. JavaScript syntax checks passed. CI at `a7a7240` passed both jobs,
including PostgreSQL migration and Redis processing. The updated Docker stack
started successfully after the demo database backup. A real browser verified
signup, adding a website, opening its owner dashboard, sign-out and sign-in with
the saved website still present. The mobile workspace was inspected at a
390-pixel viewport. Test accounts and `.example` sites are synthetic.

## Required before inviting real users

- Measure new dashboard and account routes. Finish accessibility and error-state review.
- Account recovery and clear sensor installation diagnostics. The owner chose
  in-app alerts first; email verification, delivery and email-based resets need a
  configured sender and will be documented rather than silently simulated.
- Complete real-service and browser acceptance for the new incident inbox.
- Deployment configuration validation, backup restore rehearsal, session/key
  abuse review, operational monitoring and public privacy/retention guidance.
- Persistent hosting within the user's zero-paid-services budget. A temporary
  computer-hosted Cloudflare tunnel is a development demonstration.
- Permissioned site-owner onboarding and observed usage. Synthetic requests and
  test accounts must never be counted as actual customer adoption.

The existing benchmark proves the documented local rules-only workload only.
Representative ML data/evaluation, deployment-specific performance and live
notification delivery remain separate acceptance work.
