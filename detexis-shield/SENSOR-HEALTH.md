# Sensor heartbeat-gap signals

This change adds operational signals separate from attack incidents. It is source
implementation and regression work; deployment and rendered-browser acceptance
must be verified before claiming the running instance has the feature.

Maintenance opens a signal when a site that has previously sent a heartbeat has
gone more than three minutes without another, while at least one sensor key is
active. New keys get a three-minute configuration grace before a new signal
opens; this does not close an already-open gap. Existing keys receive a creation
timestamp at migration time, so rollout also has this initial grace. Heartbeats
use backend receipt time, not a client-supplied timestamp. The
existing tenant boundary still comes from the authenticated sensor key.

One unresolved gap per site is enforced by a partial unique database index.
Maintenance uses the Site row mutex and skips rows another process has locked.
Already-open, unchanged gaps are excluded from transition selection, so they do
not starve newly overdue sites. At most 100 transitions are processed per minute;
large backlogs can delay a signal beyond the normal three-to-four-minute window.

A new heartbeat closes the gap as `heartbeat_resumed`; revoking every site key
closes it as `monitoring_disabled`. A later gap creates another history entry.
These are site-level signals: one reporting sensor instance can mask an absent
instance using the same site. A site that has never sent a heartbeat remains in
onboarding and does not generate an outage claim. Quiet request traffic alone
does not trigger a gap.

The authenticated `/app/sensor-health` page and `/app/api/sensor-health` endpoint
show only the owner's sites. Responses are uncached, capped at 100 signals with
open signals first, and indicate truncation. The page has a manual refresh link;
it does not currently poll in the background or send browser push notifications.
No request paths, query values, IP hashes, credentials or bodies are stored in
these signals. Resolved history follows the operator's retention period; open
gaps remain until closed. External email/Slack/Telegram delivery is not added by
this change; the owner chose in-app alerts first.

Missing heartbeats indicate a telemetry gap, not proof of an attack or website
outage. Check the application process, SDK sender, keys, network and Shield
backend. Shield cannot generate or deliver a signal while its own computer,
database or maintenance process is offline. No 24/7 availability promise follows
from this feature.

## Validation and rollout

Regression checks cover grace/never-connected cases, deduplication, resumption,
key revocation, cross-owner isolation, no attack-incident creation, output bounds,
bounded-batch progress and retention. A disposable SQLite migration check upgrades
0008 to 0009, enforces the open-gap invariant and verifies existing Site data after
an explicit test-only downgrade. CI additionally runs real PostgreSQL migration
and concurrent-checker acceptance plus the authenticated health page through the
local HTTPS proxy. Local route tests encountered the restricted Windows event-loop
socket boundary; they must not be described as local passes.

This release needs migration **0009**. Preserve a private database backup before
deployment. For the computer instance, the intended update command after validation
is `python tools/computer.py start --local-https`; it retains the local CA volumes
and never installs certificate trust. `status` now shows optional/stopped services,
and `stop` includes the optional HTTPS proxy without removing any volumes.

The PowerShell wrapper `tools/update_local.ps1 -BackupDirectory YOUR_PRIVATE_FOLDER`
performs the existing database backup command first and starts the local stack
only if it succeeds. Use `-Python` for a specific Python executable. It preserves
CA volumes and never installs trust. Windows CI checks this ordering and ensures
a simulated backup failure prevents startup. A same-computer backup is not an
off-device recovery guarantee.

The previous rollback rehearsal was at migration 0008 and does not prove rollback
of this release. Downgrading 0009 drops heartbeat-gap history. Do not automatically
downgrade a live database. Fresh backup/restore and runtime acceptance are still
required. Existing load reports also predate this maintenance work; concurrent
performance remains a separate release gate.
