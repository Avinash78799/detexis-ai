# Self-service account removal

Signed-in owners can open **Delete account and monitoring data** near the bottom
of their workspace. The form requires their current password and typing `DELETE`.
The API takes its target exclusively from the authenticated session, never from
a submitted account/site ID. HTTPS Origin and CSRF checks apply; three attempts
per owner per minute are allowed. No operator approval is required in the product.

`POST /app/api/account/delete` removes the owner's live account, sessions, sites,
sensor-key verifiers, events, incidents, alert records, review notes, hourly
baselines, scan results and open/resolved sensor-health history in one database
transaction. Keys and sessions cease working after commit. The interface clears
displayed sensor/recovery secrets only after a successful 204 response.

An owner with no websites can also delete their account. Foreign-owned websites
and records are retained. If older history on another website references the
removed account as its actor, only that actor reference is cleared; its review
record remains. Normal owner triage cannot create such foreign-site references.

## Concurrency and errors

The root owner lock serializes removal with new-site creation, login, password
changes and recovery. Removal uses PostgreSQL `FOR NO KEY UPDATE`, allowing an
in-flight review's actor foreign-key check to complete while removal waits for
that website. Sites are locked in ID order before deleting their children. This
serializes against workers, triage and site/key management. Existing scan and
alert-delivery transactions can finish before removal obtains their row locks.

PostgreSQL lock waits are capped at three seconds and individual statements at
ten seconds. A database error rolls back the transaction. Connection/response
loss can make the outcome uncertain; the interface asks the owner to refresh
before retrying and never automatically retries deletion. No total-time guarantee
is made for large workspaces; a timed-out or busy removal must be checked again.

Late ingest inserts or heartbeat updates whose site disappears after key
validation return 401. Already queued event jobs contain IDs and skip a removed
site; they cannot recreate it. New domain scans cannot be requested afterward.

## Data that is outside the transaction

Owners should uninstall their sensor first. The host website is not deleted and
telemetry delivery continues to fail open if it still uses a removed key.
Removal covers the live PostgreSQL records. Existing backups, hosting/operational
logs and previously delivered external notifications need the operator's separate
retention/removal process. Existing Redis short-term windows and throttle counters
expire normally; queued/failed job metadata is not a backup-erasure mechanism.
Operators must not claim that live deletion immediately erases every copy.

## Verification scope

Tests cover fully populated owner removal, another tenant's preserved data,
all-session/key invalidation, a spoofed target ID, wrong password, Origin/CSRF,
required confirmation, attempt limits, empty accounts and transactional rollback.
PostgreSQL service tests exercise actual foreign keys and the in-flight actor,
ingest and heartbeat races. The disposable TLS smoke checks account removal and
subsequent key/session/login rejection over certificate-verified HTTPS.

JavaScript tests exercise submitted credentials before input disabling, success
cleanup, failure preserving the workspace, password error messages and uncertain
server outcomes. These are programmatic DOM tests, not rendered browser or
assistive-technology acceptance. Actual local activation and production data
deletion are separate; no real owner account is deleted by these tests.
