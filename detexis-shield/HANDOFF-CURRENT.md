# Detexis Shield: continuation handoff

Snapshot: 23 November 2026. This is a working handoff, not a completion claim.
The owner lifted the earlier project deadline; continue the full product scope.
Their ChatGPT subscription may expire tomorrow, so keep this handoff usable
without an assistant. No more multi-gigabyte dataset downloads are required.

## Working implementation

Repository: https://github.com/Avinash78799/detexis-ai
Branch: `codex/shield-sensor-foundation`; existing PR 1 remains unmerged.
Last activated application change: `2ff36c6638f839760488230a31ca59c4facf4b37`.
Its four CI jobs passed in run `45183119112`. Consult Git history for later
documentation-only checkpoints.

Local address: https://localhost:8443/app
Docker project: `detexis-shield-computer`. The API, PostgreSQL, Redis, three
workers, maintenance, scanner dispatcher/service configuration and local TLS
proxy are implemented. Optional ClamAV supports bounded on-demand file checks.
The sensor supports persistent FastAPI/Starlette and Flask applications.

Accounts, site/key onboarding, owner isolation, request rules, honeytokens,
incidents/review history, in-app alerts, baselines, verified-domain scanning and
request/file analysis are implemented. See `RELEASE-READINESS.md` for evidence
and limits rather than treating this feature list as production certification.
ML remains disabled pending valid evaluation. External email is unconfigured by
owner choice. Support contact: shield.org787@gmail.com.

The API, three workers and maintenance now run image
`sha256:03e15921e869d2d1b51cb46153889d51218ff7916f12324a04e7488847ce5f7a`,
with actual installed SDK 0.1.1. The isolated scanner retains
`sha256:3b1d266a2a15f153c0ca399a93958cdd79bfbf14c138ce0dddd6c30ef6fbb7a6`. Do not publish local images:
cached image configuration can contain private environment values.

## Start and verify

Start Docker Desktop. Existing restart policies normally resume saved containers.
From `detexis-shield`, using the project's Python environment:

```powershell
python tools/computer.py status
```

Check https://localhost:8443/ready for `{"ok":true}` without bypassing certificate
warnings, then open `/app`. Python certificate trust is separate from browser
trust; follow `LOCAL-HTTPS.md` for the reviewed public-CA bundle. Existing local
trust was installed by the owner; do not replace it or disable verification.

Use `COMPUTER-HOSTING.md` and `LOCAL-HTTPS.md` to diagnose stopped services.
`computer.py start --local-https` builds/recreates from the checkout; it is an
update operation, not merely a way to resume saved containers. Back up first.
Do not blindly replace the saved configuration or use destructive volume commands.

## Preserve privately

- `.computer.env`, the original database credentials and Docker data volumes.
- The local TLS CA volume and the reviewed public root certificate. Keep the
  private key private; a public certificate alone cannot restore the CA.
- The workspace's private `outputs` folder, particularly `computer-backups`,
  activation reports and `compose.sdk-011-active.private.json` with its
  corresponding rollback file. These files are outside the Git checkout.
- The owner's recovery code, site salts and sensor keys in their own private
  storage. Do not add them to this document, source control or screenshots.

Latest activation backup: `shield-20261123T132344Z-c72ab636.dump` in the private
`outputs/computer-backups` directory. It has local activation evidence, not an
off-device disaster recovery claim. Read `BACKUP-RESTORE.md` before restoring.

## Remaining work, in order

New SDK 0.1.1 performance evidence: two attested four-client Windows loopback
runs passed every client's median <5 ms/p95 <10 ms for normal, large and nested
query profiles, online/refused collectors. Worst p95s were 6.948 and 5.705 ms.
All 2,640 events per online case arrived without seeded-secret matches or drops.
See `sdk-011-socket-check.json` and `SOCKET-OVERHEAD.md`. The harness checks actual
loaded package bytes/version; no-sensor calibration is diagnostic only. Tool CI
is pending. Remote/TLS/Linux/long-lived checks and the post-upgrade backend
capacity experiment remain open.

Activated SDK privacy change: source package version 0.1.1 recognizes nested secret
query names (`credentials[password]`, `auth.token`, indexed bracket forms) in
redaction/shared features. Fifty-seven focused checks passed, including the two
middleware examples. All four CI jobs passed for source commit
`0a64d7c9d05c8b4c02ef444b22dcb29c000d75c0` (run 45182577169). The guide now pins
that commit. The built 0.1.1 wheel passed a fresh target installation and six-file
source comparison (`sdk-wheel-check.json`); the wheel is in the private
`outputs/sdk-0.1.1-release` directory. Runtime activation passed in all five API/worker/maintenance containers, with
package version 0.1.1 and all six installed source files verified. Other package
versions and environments were preserved. Existing customer sensors still need
their own upgrade/restart; copying backend app files alone is insufficient. No historical data
was scrubbed, and this is not comprehensive PII detection. ML stays disabled.

Activated logout fix: logout tolerates its session row disappearing after
authentication. A deterministic regression reproduced HTTP 500 before the fix;
focused tests now pass, preserving CSRF refusal and another device's session.
All four CI jobs and backup-first API-only activation passed. Verified HTTPS
readiness and unauthenticated session refusal passed. This is not full session-race
coverage or rendered sign-out acceptance.

Latest scanner hardening is activated: the scanner explicitly refuses
Azure's `168.63.129.16` platform destination and its mapped IPv6 form, and rejects
explicit port zero instead of defaulting it. Forty-six focused checks passed
using mocked transport/DNS only; all four CI jobs and scanner-only activation
passed. Installed policy and internal-API checks passed without target fetches.
The old scanner image metadata was missing; a snapshot of its running read-only
container is retained as rollback image
`sha256:019e19bff217ee88dbbfedef9a3d7694bd892e8379ac4b97dea8de75ae4e49ec`.

1. Complete signed-in multi-site browser acceptance: key creation/revocation,
   refresh races, incident decisions, recovery/removal, errors, keyboard and
   assistive-technology behavior. The replacement-key refresh race was reproduced
   and corrected in source with a stable, site-labelled credential area; tests
   cover refresh during issuance, multiple sites and a late response after account
   deletion. CI and backup-first local activation passed; signed-in rendered
   acceptance remains pending for that change. Browser confirmation for
   creating two synthetic sites/keys is still unanswered; generic continuation
   is not that approval. Do not alter the owner's credentials or use their account.
2. Extend operational validation: partial Redis corruption, dispatcher crash and
   timeout cases, long outages/backlog growth, larger cleanup/removal workloads,
   off-device restore and live cutover. Existing narrow passing checks do not
   cover all of these. Review retention skip-lock starvation under sustained load.
3. Complete representative deployed sensor/performance and abuse checks. Current
   synthetic capacity and calibrated socket benchmarks are documented, not a
   promise of flawless latency or availability on every host.
4. Follow `ml/SMALL-DATA-ROUTE.md`: preserve existing audited data/provenance,
   obtain independent permissioned benign traffic and compatible labeled request
   data, use time/session separation and cross-dataset evaluation, choose an FPR
   threshold with confidence bounds, and keep ML disabled unless the gates pass.
5. Run an ownership-verified real-domain scanner trial and onboard permissioned
   real sites. No real-user adoption count is established. Record observed usage,
   tune false positives and make an honest demo/benchmark table.
6. Decide public reachability only if the owner changes the local-only hosting
   choice. No public tunnel/domain/card/paid hosting is currently authorized.
   `localhost` cannot be used by a sensor on another computer. Existing Vercel
   rollout and account/history migration are not completed.

Later SDK/framework modes, reverse proxy, JS monitoring and LLM firewall remain
roadmap work in `SENSOR.md`; they are not implemented features.

## Test and evidence map

Run focused changes with `python -m pytest <relevant test files> -q` and use
`node --test (Get-ChildItem tests -Filter '*.test.cjs').FullName` in PowerShell
for the frontend regressions. The GitHub workflow
supplies disposable PostgreSQL/Redis and runs additional integration tests;
local SQLite-only passes cannot substitute for them. Never point integration
tests or their synthetic Redis flushes at the computer instance's live stores.

Read `RELEASE-READINESS.md`, `ANALYSIS-UI-REVIEW.md`, `SOCKET-OVERHEAD.md`,
`MULTITENANT-PERFORMANCE.md`, `WORKER-RECOVERY.md`, `QUEUE-RECOVERY.md`,
`ACCOUNT-REMOVAL.md`, `RULE-RELEASES.md` and `ml/SMALL-DATA-ROUTE.md`.
Recent verified fixes include the hourly-retention boundary, cleanup/site-lock
coordination, outbox starvation and durable scan publication. Their activation
reports include source matching, backups, unchanged data and health checks.

The rough engineering estimate shared with the owner was 3–7 focused developer
days plus at least 1–2 weeks of permissioned real-site observation. This is a
low-confidence planning estimate, not a measured percentage or promise. ML data
availability, discovered defects and real-owner participation can extend it.
