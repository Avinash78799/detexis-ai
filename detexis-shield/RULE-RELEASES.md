# Versioned web-detection releases

Release `2026.11.14.1` is the first source-fingerprinted release record, with
`rules_version=2`. The preceding bundled detector advertised version 1. These
versions identify installed code; they do not establish complete threat coverage.

## Detection change and regressions

The update recognizes the tested block-comment-separated SQL patterns and MySQL
executable-comment examples. It keeps path/query fields separate so a path ending
in `union` and a different field beginning with `select` cannot create an invented
match. SQL-only normalization preserves original HTML evidence and does not join
split keywords. Input parsing remains bounded; comment scanning advances through
the input without repeated backtracking over an unterminated comment suffix.

This remains heuristic inspection, not a SQL parser. A payload's validity depends
on application context and database dialect. Ordinary comment contents are ignored
for SQL matching; executable-comment contents are retained. The new fixtures
reproduced thirteen failures in the old detector, covering eight missed comment
variants, three comment-only examples and two cross-field false positives. They
then passed with the original mapped-rule/pipeline tests. This fixture result is
not representative recall or real-site false-positive-rate measurement.

## Installed-release visibility

- `/app/detection` is an authenticated coverage page with the release ID, bundled
  date, rule families, input limits, fingerprint and known blind spots.
- `/app/api/detection` exposes the same packaged inventory to the owner.
- `/v1/config` retains monitor mode and adds the release ID and source hash; the
  Python sensor's existing configuration parser remains compatible.
- Processed event features include the server's actual rule release and source
  hash, even for no-match events. Matched rule evidence also carries its release.
  These values overwrite any client-supplied feature labels. ML's numeric feature
  schema remains unchanged; training exports reconstruct features from requests.
- Historical events are not relabeled or reprocessed by this upgrade.

The release date means “bundled with this deployment”, not “checked against every
new threat today”. No remote web-rule feed, CRS engine or automatic CVE-to-site
vulnerability determination is implemented by this change.

## Release gate

Each immutable JSON record under `backend/app/rule_releases/` contains its version,
date, canonical rule-source SHA-256, change notes and primary source references.
Canonical hashes normalize CRLF to LF for Windows/Linux agreement.

```powershell
python tools/validate_rule_release.py --previous-ref FULL_PREVIOUS_COMMIT_SHA
python -m pytest tests/test_rules.py tests/test_rule_evasion.py tests/test_rule_manifest.py tests/test_pipeline.py -q
```

The first command checks metadata/version integrity, not detection quality. It
parses old version constants without importing or executing an older revision.
Changed rule source requires a higher integer version. A published record cannot
be rewritten; create a new release and retain old records. CI obtains full history
and applies this check against the PR base or previous push commit, then runs the
complete regression/audit suite. A new-project base without a detector is treated
as an initial release. The first formal manifest does not retrofit records onto
every historical pre-manifest commit.

Rules are reviewed source changes deployed with the service. Do not download
arbitrary regex/code from a threat feed and activate it in the request worker.
The manifest is an integrity receipt, not a cryptographic publisher signature or
an independent security certification. Review legitimate traffic and evasion
cases before activation. Keep monitor-only operation in v1.

## Rollback rehearsal

Retain known-good local images before building a new release. Never run this
controlled check on a live customer instance: it refuses any Site rows, a busy
worker or a nonempty queue.

```powershell
python tools/check_rule_rollback.py --confirm-zero-site-check --capture-baseline PRIVATE_BASELINE_JSON
python tools/computer.py start
python tools/check_rule_rollback.py --confirm-zero-site-check --baseline PRIVATE_BASELINE_JSON --output rule-rollback-check.json
```

The baseline creates explicit retention tags and records their image IDs and rule hashes. Container config digests alone are not reliable executable image references in Docker's containerd store. Retained tags must remain available and unchanged. The check temporarily
recreates API/worker/maintenance from those images with image pulls/builds disabled,
checks consistency/readiness, and restores the current tagged images in a `finally`
step. Datastore volumes are not recreated. It verifies that the migration version
does not change. It does not prove rollback of a database migration, active jobs,
account sessions or live traffic. If the current image cannot be restored, stop
rollout and inspect the displayed logs rather than assuming recovery.

The computer-hosted deployment and controlled rollback passed on 14 November;
`rule-rollback-check.json` records source hashes, local image identities, readiness
and unchanged migration 0008. The original previous image was not retained, so
the baseline was rebuilt from published commit `24ac7df615c4d6180567312558a61b3a0266d953`
and explicitly tagged before the rehearsal. This establishes previous-source
compatibility, not byte-for-byte recovery of the original deployed artifact.
Retain actual known-good images before future upgrades.

`rule-cpu-benchmark.json` records isolated CPU timings for six synthetic profiles
(2,000 iterations each). Its slowest profile had a 1.10 ms p95 on this computer.
This excludes SDK, HTTP, queueing, database and concurrent traffic. Historical
version-1 throughput reports are not performance acceptance for this release.
The version-2 ten-minute local SQL-comment workload passed; see `MIXED-LOAD.md`
for the measured scope and explicit report-recovery limits. Rendered coverage-page
acceptance remains pending; authenticated page/API behavior has automated
regression coverage. Multi-tenant, concurrent-browser and actual sensor overhead
remain separate performance gates.

Primary detection reference: [OWASP SQL injection testing and comment bypasses](https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/07-Input_Validation_Testing/05-Testing_for_SQL_Injection/).
