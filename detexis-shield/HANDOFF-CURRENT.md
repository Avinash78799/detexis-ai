# Detexis Shield: continuation handoff

Snapshot: 23 November 2026. This is a working handoff, not a completion claim.
The owner lifted the earlier project deadline; continue the full product scope.
Their ChatGPT subscription may expire tomorrow, so keep this handoff usable
without an assistant. No more multi-gigabyte dataset downloads are required.

## Working implementation

Repository: https://github.com/Avinash78799/detexis-ai
Branch: `codex/shield-sensor-foundation`; existing PR 1 remains unmerged.
Last application commit: `0b0d7dd570e1a869a4bdd9114fb4f7bc61fc802e`.
Its four CI jobs passed in run `45179094796`. Consult Git history for later
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

The active API image is
`sha256:66f8412327bbfb667757a5b5853bafeba91ec941355e29311446da221fffa4bb`.
Maintenance retains
`sha256:317b5a92a5406702af6a670b8295ac52b69ac66aae5b8f2603811119d18de563`.
Workers retain their compatible earlier image. Do not publish local images:
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
  activation reports and `compose.issued-key-ui-active.private.json` with its
  corresponding rollback file. These files are outside the Git checkout.
- The owner's recovery code, site salts and sensor keys in their own private
  storage. Do not add them to this document, source control or screenshots.

Latest activation backup: `shield-20261123T125836Z-33aafb97.dump` in the private
`outputs/computer-backups` directory. It has local activation evidence, not an
off-device disaster recovery claim. Read `BACKUP-RESTORE.md` before restoring.

## Remaining work, in order

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
