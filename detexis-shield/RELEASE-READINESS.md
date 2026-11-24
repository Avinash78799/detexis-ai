# Release readiness: 24 November 2026

The complete product goal is **not achieved**. Implemented code, local tests and
temporary demonstrations do not prove a continuously operated public service.
The percentage previously discussed was an effort estimate, not a release gate.

24 November status check: the worktree was clean at application/tool checkpoint
`398052316dd49a95197141b39dc5c41dc90ef755`; all four jobs in
[Actions run 45236294936](https://github.com/Avinash78799/detexis-ai/actions/runs/45236294936)
passed. Docker's Linux engine pipe was unavailable during the read-only check, so
current service availability could not be verified. Earlier activation/health
records remain historical evidence, not a claim that services are running now.
No service or account was changed by this status check.

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

The request feed now shows pending requests among its 50 visible rows and warns
when any of them has waited over a minute. A dashboard regression checked that a
newer analyzed request no longer hides an older pending request.
[All four CI jobs](https://github.com/Avinash78799/detexis-ai/actions/runs/45354022726)
passed for `e824cb6462f0fabc6d6e621be821d0f77828be75`. The local API update passed
source verification and CA-verified readiness after a database backup. Database
row digests and worker and maintenance containers were preserved. The active
local override is `outputs/compose.dashboard-backlog-active.private.json`.
Private evidence is in `outputs/dashboard-backlog-runtime-20261124.json`.

Dashboard refresh controls now preserve scan details and keyboard focus. Owners
can pause automatic updates and use manual refresh when the feed is idle. The
live status announces errors and state changes, with the update timestamp shown
separately. All 32 JavaScript checks, three dashboard route tests, and
[all four CI jobs](https://github.com/Avinash78799/detexis-ai/actions/runs/45353510532)
passed for `a0903ade977a5714e70749aa5daf82bc1feb7790`. The API-only activation
verified the served script and HTTPS readiness after backup. Full signed-in
browser and assistive technology checks remain open.


The site dashboard now distinguishes an unconnected sensor, a heartbeat without
recent requests, received requests awaiting analysis, delayed processing, and
an analyzed request. The full owner page and feed refresh route passed a
synthetic lifecycle test. Seven focused tests and
[all four CI jobs](https://github.com/Avinash78799/detexis-ai/actions/runs/45322291357)
passed for `81aec2a63b29b58c76a459dcfb85c189c79699b2`. The API-only activation
verified source hashes and local HTTPS readiness after backup. The local
override is `outputs/compose.dashboard-onboarding-active.private.json`.
Signed-in visual and accessibility acceptance remain open.


The validation privacy fix in `faddd53488b15d288830987b407f1ef068a4d08f`
is now active in the local API. Invalid POST requests to ingestion or the
owner API receive HTTP 422 without echoed input. Thirty-three focused tests,
[all four CI jobs](https://github.com/Avinash78799/detexis-ai/actions/runs/45320082507),
and a live CA-verified invalid-login response check passed. The API image is
`sha256:c905f3c08cbcf57f1a8f0d4f302ec6a8d0bcac36d7866dcb4871384b13e7723b`.
Backup `outputs/computer-backups/shield-20261124T034451Z-2689eff7.dump`
and rollback configuration are retained. The active override is
`outputs/compose.validation-privacy-active.private.json`.


On 24 November Docker Desktop resumed and CA-verified local HTTPS readiness
passed. The API now masks recognized sensitive query names before storing new
events, including bracket and dotted names sent by older sensors. SDK 0.1.1
remains the way to mask those fields before transmission. Existing stored
telemetry was untouched. The ingestion regression and 44 focused checks
passed, as did all four CI jobs for `89bf05176fe5ed1747d7e82f716375e87a2a2774`
([run 45317739818](https://github.com/Avinash78799/detexis-ai/actions/runs/45317739818)).
The API now runs image
`sha256:857b022ad0c1eeb47911dd5a05e5e5687ad6dd3bf4b60b2d68731c54a76e7f50`.
Activation preserved SDK 0.1.1 and verified 65 backend source files, all table
digests, and local HTTPS. The private activation report is
`outputs/ingest-redaction-runtime-20261124.json` and the active local override is
`outputs/compose.ingest-redaction-active.private.json`. The ten-minute ingest capacity rerun passed at 500.16 events/s with a
fully drained queue. See `MULTITENANT-PERFORMANCE.md` for scope and latency.


SDK 0.1.1 performance revalidation, 23 November: two four-client Windows loopback
runs passed every-client and pooled median <5 ms/p95 <10 ms for normal, large and
nested-secret profiles, online and refused collectors. Worst-client median/p95
was 0.901/6.948 ms, then 0.715/5.705 ms. Each online case received 2,640 events
with no seeded-secret matches/drops; refused cases accounted for all drops on
shutdown. Actual loaded package version and six SDK hashes matched the verified
wheel across both runs. The harness now refuses loaded-source mismatch before
measurement. Eight harness tests passed. Complete reports, diagnostic calibration
and hashes are in `sdk-011-socket-check.json`; scope is in `SOCKET-OVERHEAD.md`.
Tool CI passed all four jobs in Actions run 45236294936. Remote/TLS, Linux, representative traffic and prolonged
operation remain open; the earlier backend capacity result is not a new
post-SDK-upgrade capacity measurement.

SDK nested-query privacy update activated, 23 November: ten synthetic cases
reproduced unmasked values under names such as `credentials[password]`,
`auth.token` and `users[0][passwd]`. Source package version 0.1.1 now recognizes
whole sensitive-name components separated by brackets or dots; names such as
`password_policy`, `tokenizer` and `cardinality` retain their values. Shared
features use the same name predicate. Fifty-seven focused checks passed, including
both runnable middleware installation examples, repeated/encoded fields, decoder
equivalence and feature consistency after masking. This remains named-field
redaction, not comprehensive personal-data removal. Paths, user agents, field
names and unrecognized fields can still contain private data. No historical
telemetry was altered. Customer sensors gain this protection only after their own
upgrade/restart. No public PyPI release is claimed; ML remains
disabled pending evaluation with the matching preprocessing representation.

Source commit `0a64d7c9d05c8b4c02ef444b22dcb29c000d75c0` passed all four jobs in
[Actions run 45182577169](https://github.com/Avinash78799/detexis-ai/actions/runs/45182577169).
The installation guide now pins that immutable source and explains upgrading and
restarting existing sensors. An initial offline wheel build stopped because the
test environment lacked setuptools; pip's isolated build then succeeded without
modifying the application environment's dependencies. Wheel
`detexis_shield-0.1.1-py3-none-any.whl` has SHA256
`ff18c2246830814cb454888dd9a6b870342c6bbe2a3e9eb34f442ba5f707dac5`.
A fresh disposable target installation verified version 0.1.1, the actual import
location, byte matches for all six package source files, nested masking and
feature consistency. See `sdk-wheel-check.json`; the wheel is retained privately
in `outputs/sdk-0.1.1-release`. Earlier SDK socket benchmarks must not be relabelled
as 0.1.1 results.

Activation commit `2ff36c6638f839760488230a31ca59c4facf4b37` passed all four jobs in
[Actions run 45183119112](https://github.com/Avinash78799/detexis-ai/actions/runs/45183119112).
The verified wheel was installed offline into a candidate image; all other
installed package versions matched the previous services. After idle-queue checks
and backup `outputs/computer-backups/shield-20261123T132344Z-c72ab636.dump`, API,
three workers and maintenance were updated to image
`sha256:03e15921e869d2d1b51cb46153889d51218ff7916f12324a04e7488847ce5f7a`.
All five containers became healthy and verified actual SDK 0.1.1 imports, six SDK
file hashes, nested masking/features and all 65 backend source hashes. Environment,
command and every table row digest were unchanged; the scanner was preserved.
CA-verified HTTPS readiness and the served install pin passed. Previous role
images/configuration are retained for rollback. No customer-sensor installation,
target traffic, migration or ML activation occurred. Private evidence:
`outputs/sdk-011-runtime-20261123.json`.

Logout invalidation-race correction activated, 23 November: a deterministic
test reproduced HTTP 500 if a valid session was removed after authentication but
before logout's second session lookup. Logout now deletes by token hash without
requiring a row to remain, then clears the cookie. Authentication/origin/CSRF
dependencies remain in place. Seven focused account/logout/removal checks passed;
the strengthened final regression also verifies invalid CSRF refusal and another
device's continued access. It models invalidation at the authentication/handler
boundary rather than claiming a threaded PostgreSQL race test. No real account
or session was changed by these tests or activation.

Commit `c52b9787c1afefe20196a2882613c44984dd23fc` passed all four jobs in
[Actions run 45181432928](https://github.com/Avinash78799/detexis-ai/actions/runs/45181432928).
After backup `outputs/computer-backups/shield-20261123T131307Z-f1719007.dump`,
the API alone was updated to image
`sha256:1488283264fd9e9aff72eb5dad40600125d0d135ec638b36c3a3d0aad723fde5`.
All 65 source files matched the tested source; environment and every table row
digest were unchanged. Worker, maintenance and scanner identities were preserved.
API health, CA-verified HTTPS readiness, served UI hashes and unauthenticated
session refusal passed. Cached dependencies were retained; no migration occurred.
Previous-image rollback configuration is saved, and the activation helper now
automatically restores the previous API if post-update verification fails.
Private evidence: `outputs/logout-race-runtime-20261123.json`. Signed-in rendered
logout/recovery acceptance and broader session concurrency remain open.

Scanner destination hardening activated, 23 November: mocked regressions
reproduced acceptance of Azure's `168.63.129.16` platform service address (also
through mapped IPv6), and explicit URL port zero being treated as the default.
The fetch policy now rejects that platform destination before connection and
distinguishes a missing port from zero. Direct/mixed DNS answers and redirect
re-resolution are covered, with public-target/80/443 positive controls. Forty-six
focused scanner/scheduling checks passed. No cloud endpoint or real site was
contacted by these tests. Microsoft documents this special host-node destination
and its port-80 WireServer role in its
[platform IP overview](https://learn.microsoft.com/azure/virtual-network/what-is-ip-address-168-63-129-16).
The restriction is in the scanner's HTTP target policy, not an OS firewall change.
This is not a complete SSRF audit.

Commit `01f23dd4e0b82528523e0bb1f0245058e1a8d8b0` passed all four jobs in
[Actions run 45180186334](https://github.com/Avinash78799/detexis-ai/actions/runs/45180186334).
The first deployment attempt stopped before replacement because Docker could not
find the running scanner's original image metadata. Its read-only container was
preserved as local rollback image
`sha256:019e19bff217ee88dbbfedef9a3d7694bd892e8379ac4b97dea8de75ae4e49ec`.
After backup `outputs/computer-backups/shield-20261123T130655Z-22d1bd88.dump`,
only the scanner was replaced with image
`sha256:3b1d266a2a15f153c0ca399a93958cdd79bfbf14c138ce0dddd6c30ef6fbb7a6`.
All four scanner source files matched. Its environment, UID, command, read-only
filesystem, memory/CPU/PID limits, capabilities, security options, mounts, port
bindings and network memberships were preserved. Installed IP/port policy checks,
the internal scanner API and CA-verified local HTTPS readiness passed without a target
fetch. All table row digests and API/worker/maintenance identities were unchanged.
Cached dependencies were retained. No firewall change, migration or account
mutation occurred. Private evidence: `outputs/scanner-policy-runtime-20261123.json`.

Replacement-key refresh correction activated, 23 November: the previous UI
appended a one-time secret to a website card that could already have been removed
by a refresh. A synthetic regression reproduced the failure. Issued keys now
appear in a stable, hostname-labelled area outside the replaceable website list,
without browser storage or secret-bearing live announcements. Confirmed account
deletion clears the area; an issuance response from an obsolete session cannot
restore it. Thirty frontend tests and five focused Python account/installation
tests passed, followed by nine focused key/deletion checks including the new
late-response case. Signed-in rendered acceptance remains pending.
Browser account/key creation still requires its existing specific
approval; no real account, key or browser session was changed by these tests.

Commit `0b0d7dd570e1a869a4bdd9114fb4f7bc61fc802e` passed all four jobs in
[Actions run 45179094796](https://github.com/Avinash78799/detexis-ai/actions/runs/45179094796).
After backup `outputs/computer-backups/shield-20261123T125836Z-33aafb97.dump`,
the API alone was updated to image
`sha256:66f8412327bbfb667757a5b5853bafeba91ec941355e29311446da221fffa4bb`.
All 65 application/migration files matched source, and the served account script
matched its source hash. The served page includes the stable issued-key area.
Environment and every table row digest were unchanged; worker and maintenance
containers were preserved. API health and CA-verified HTTPS readiness passed.
Cached dependencies were retained; no migration or account mutation occurred.
Private evidence: `outputs/issued-key-ui-runtime-20261123.json`.

Scan scheduling correction activated, 23 November: the prior scheduler
reproduced replacement of an old pending scan and duplicate queue publication.
The source now retains pending records, commits new records before publishing,
and serializes deterministic RQ job publication under the site's processing lock.
Active queued/started/deferred/scheduled jobs are retained; terminal jobs can be
replaced while the database scan remains pending. API requests use the same
publisher. Thirty-seven focused checks passed, covering pending-record retention,
repeat publication, complete synthetic Redis loss, scanner gates and maintenance.
A PostgreSQL simultaneous-publisher check passed in CI. No target scan or
external request was made by these scheduling tests. Partial Redis corruption
(a queued job hash surviving without its queue entry) and crash/timeout recovery
of an active dispatcher remain separate cases.

Commit `702152764dd51c3509ac6e6be6a6ad80ded39734` passed all four jobs in
[Actions run 45176930314](https://github.com/Avinash78799/detexis-ai/actions/runs/45176930314).
Following backup `outputs/computer-backups/shield-20261123T124438Z-0940f166.dump`,
API and maintenance were updated to image
`sha256:317b5a92a5406702af6a670b8295ac52b69ac66aae5b8f2603811119d18de563`.
Both services' 65 application/migration files matched the tested source;
environment/command and every table row digest were unchanged. Workers were
preserved: their dispatcher body and job arguments remain compatible. API and
maintenance health and CA-verified HTTPS readiness passed. Previous role images
remain available for rollback. Cached dependencies were retained. No migration,
account mutation or target scan occurred. Private evidence:
`outputs/scan-scheduling-runtime-20261123.json`.

Alert outbox priority corrected on 23 November: tests first reproduced older
unconfigured rows consuming the entire delivery batch. Configured sites now take
priority; destination-free alerts are marked once and reconsidered when their
site receives configuration. Regressions cover backlog fairness, later channel
configuration and retrying only a failed channel after partial delivery. All
delivery calls in these checks are mocked; no messages were sent. The related
22-test local run and three final outbox checks passed. Commit
`767d80959b19bd87a06d707725e943baed6c96be` passed all four jobs in
[Actions run 45176054278](https://github.com/Avinash78799/detexis-ai/actions/runs/45176054278),
including PostgreSQL execution of the new outbox cases. This does not prove
external provider delivery, broad tenant scheduling fairness or exactly-once
delivery across a process crash after a provider accepts a message.

Maintenance alone was updated after backup
`outputs/computer-backups/shield-20261123T123908Z-76548dd7.dump` to image
`sha256:64fc8f05000f2e84fc3daf5986321440c89b335bcfd2dcc4171d2d1cfb522655`.
All 65 source files matched. Environment/command, all database row digests and
API/worker identities were unchanged; maintenance health and verified HTTPS
readiness passed. Cached dependencies and existing notification settings remain.
Private evidence: `outputs/outbox-priority-runtime-20261123.json`.

Cleanup locking correction activated, 23 November: an isolated PostgreSQL 16
rehearsal reproduced `Cleanup erased a busy site` against the previous source.
Cleanup now obtains the worker/triage Site NO KEY UPDATE lock with SKIP LOCKED,
then deletes each site's expired graph in one transaction. Busy sites are retried
on a subsequent pass; idle sites can still make progress. Completed sites remain
committed if a later site's cleanup fails. Browser-session expiry is independent.
All 21 focused checks passed after the correction; the final eventual-retry
assertion also passed against the isolated database. This is not a busy-tenant
starvation bound or large-history performance result.

Commit `95266a80e1edf216f7a93b8784b6bd49018e242a` passed all four jobs in
[Actions run 45175299409](https://github.com/Avinash78799/detexis-ai/actions/runs/45175299409).
After fresh backup `outputs/computer-backups/shield-20261123T123422Z-b0d60d64.dump`,
maintenance alone was replaced with image
`sha256:a3c52b3dcabcfffe2a75288e3a7683eff96b9f6e127533d4d566d034a9208d50`.
All 65 source files matched the tested source. Environment, command and all table
row digests were unchanged; API/worker container identities were preserved.
Maintenance health and CA-verified HTTPS readiness passed. The prior maintenance
image remains available for rollback. Cached dependencies were retained; no
migration or account mutation occurred. Private evidence:
`outputs/retention-locks-runtime-20261123.json`.

Retention graph/rollback validation on 23 November: commit
`b118cd6c74352f4f29768f1b31ee7e1255d5aed2` passed 20 focused local tests and all
four jobs in [Actions run 45174447772](https://github.com/Avinash78799/detexis-ai/actions/runs/45174447772).
The main job reported 431 passing Python tests with no skips. The new PostgreSQL
check exercises expiry of incidents and their alert/review children, preservation
of recent records for two sites, repeated cleanup, and complete transaction
rollback when interrupted after child deletion. Redis request-window behavior is
simulated in this focused PostgreSQL test. It does not prove concurrent cleanup,
large-history performance or outage behavior. These are test-only changes; no
production service or existing owner data was changed.

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
