# PostgreSQL backup and restore rehearsal

The database is the durable record of sites, accounts, sensor-key verifiers,
events, incidents, scans and alert delivery state. Keep backups private: they
contain password/session/key verifiers and request telemetry. Never commit them.

## Computer instance rehearsal, 25 November 2026

A fresh custom-format backup at migration `0011` was restored into a disposable
PostgreSQL container with networking disabled. All 12 public tables matched the
live source by aggregate row digest, the constraints were valid, and PostgreSQL
confirmed that the workspace attention index survived the restore. The live API
passed trusted HTTPS readiness checks before and after the rehearsal.

The archive was streamed into `pg_restore --exit-on-error --single-transaction`.
The disposable container was removed after verification. This checks recovery
from a backup stored on the same computer. Recovery from an off-device copy and
cutover of the live computer-hosted instance remain untested.

### Synthetic application cutover

On the same schema, an isolated Shield API accepted a synthetic event while
its worker was offline. The source API was stopped, and its PostgreSQL snapshot
was restored into a different database. A replacement API and fresh Redis
then started on the private Docker network. The original owner login, sensor
key, and incident history worked over fixture HTTPS. Retrying the pending
event returned a duplicate, and recovery queued it for a native RQ worker.
The worker finished with no pending events or failed jobs.

The rehearsal used unpublished ports and synthetic data. It did not test
notification delivery, an off-device archive, or switching the live instance.

## Rehearsal performed on 2 November 2026

The local validation database at migration `0006` was dumped using PostgreSQL 16
custom format and restored with `pg_restore --exit-on-error` into a **separate new
database**. The running application's database was not replaced.

| Check | Source | Restored |
| --- | ---: | ---: |
| Sites | 5 | 5 |
| Events | 899,915 | 899,915 |
| Incidents | 13 | 13 |
| Accounts | 1 | 1 |
| Migration | 0006 | 0006 |

The restore completed successfully with indexes and foreign keys. Restored
constraints were validated; checks found zero orphan events and incident actions.
All accounts/traffic in this fixture are synthetic. These are local recovery
checks, not a measured production recovery-time or recovery-point guarantee.

## Computer instance rehearsal, 17 November 2026

After migration 0009, a new 27,126-byte custom-format dump was copied to the
private host backup directory, copied back under a new temporary name, and
restored with `--exit-on-error` into a fresh isolated database. Both user rows
matched an aggregate digest of the source rows. Counts matched for users (2),
sites, keys, events and sensor-health history (all 0). Migration 0009, validated
constraints and the partial unique open-gap index were present in the restore.

The rehearsal database `shield_restore_0009_2dcacbe24bd8` remains isolated; no
application writers or delivery processes were attached. The private report is
`outputs/health-0009-restore.json` in the task workspace. This checks the actual
local account backup and upgraded schema, but cannot establish recovery of
populated heartbeat history or an off-device backup. No production recovery-time
or recovery-point objective was measured.

## Populated schema-0009 fixture, 18 November 2026

The stopped four-tenant capacity fixture was restored from a private host-copy
dump into `shield_restore_20261118t112014z_7793e543`. Complete-row SHA256 digests
matched for all twelve public tables, including **300,004 events, 1,536 incidents,
1,536 alert records, four owners, four sites, four sensor-key verifiers and four
browser sessions**. The four hourly baseline buckets also matched. Constraints,
index definitions and sequence positions matched; no invalid constraint/index
remained. Incident actions, scans and sensor-health history were initially empty,
so that first round trip does not establish populated recovery for those tables.

Only the isolated copy then received one open and one resumed heartbeat record
per site. A second host-copy dump/restore into a new `_health` database preserved
all rows, including **eight health records: four open, four resumed**. Original
benchmark rows were checked unchanged. Application/worker/delivery processes
were never attached, and the fixture database was stopped after the rehearsal.
Both restored databases, dumps and the private report remain retained.

Dump sizes were 12,199,168 and 12,226,481 bytes. The `pg_restore` commands took
20.656 and 11.531 seconds respectively; these exclude backup/copy/verification
and are **not service recovery-time guarantees**. Report:
`outputs/populated-restore-20261118/shield_restore_20261118t112014z_7793e543.json`,
SHA256 `5bf9b1f993fee509b71b1282a68dac107b988290f745b092392cecdeec366292`.
The owner database was untouched. Off-device recovery, application cutover and
populated scan/triage-action recovery remain unverified. A subsequent isolated
pending-event/duplicate-delivery rehearsal passed; see `QUEUE-RECOVERY.md` for
its ASGI/RQ scope and Redis-loss limitations.

## Repeat safely

For a completed **synthetic** performance fixture, an automated rehearsal is
available. Stop all of that fixture's containers first, preserve its volumes,
then run from `detexis-shield`:

```powershell
python tools/rehearse_fixture_restore.py --project shield-perf-your-run --backup-dir C:\PRIVATE\ShieldRestoreChecks --confirm-disposable
```

The helper rejects computer hosting, arbitrary projects, missing/duplicate
database containers and any running fixture container. It starts only the
fixture database, copies a custom dump to the private host directory, copies it
back under a different filename and restores into a newly named database.
Every complete table row is compared through a deterministic SHA256 digest,
alongside constraints, index definitions, sequence positions and validity checks.
The original rows are checked again for changes. No row data or authentication
verifiers are printed. Reports and dumps must remain private.

A second round trip seeds open and resumed heartbeat records **only in the
isolated restored copy**, then backs up/restores that copy into another new
database. Application/delivery processes never attach to either restore. The
fixture database is stopped on exit; databases, dumps and reports are retained.
Failures are recorded without deleting or replacing the source. This checks
host-copy recovery, not off-device durability or application failover. Use the
manual procedure below for real-service recovery planning.

Use the actual database container name shown by `docker compose ps`. These commands
show the validation project used in the rehearsal. Choose a fresh backup filename
and database name each time; `createdb` must fail if that name already exists.
Execute each command successfully before continuing.

```sh
docker exec detexis-shield-validation-db-1 pg_dump -U detexis -d detexis -Fc -f /tmp/shield-backup.dump
docker cp detexis-shield-validation-db-1:/tmp/shield-backup.dump /PRIVATE/BACKUP/DIRECTORY/shield-backup.dump
docker exec detexis-shield-validation-db-1 createdb -U detexis shield_restore_check
docker exec detexis-shield-validation-db-1 pg_restore -U detexis -d shield_restore_check --exit-on-error /tmp/shield-backup.dump
docker exec detexis-shield-validation-db-1 psql -U detexis -d shield_restore_check -c "SELECT version_num FROM alembic_version"
docker exec detexis-shield-validation-db-1 psql -U detexis -d shield_restore_check -c "SELECT count(*) FROM events"
docker exec detexis-shield-validation-db-1 psql -U detexis -d shield_restore_check -c "SELECT conname FROM pg_constraint WHERE NOT convalidated"
```

`/PRIVATE/BACKUP/DIRECTORY` is a placeholder for a private existing directory on
the Docker host. Copy the backup off the container before relying on it. For a
real service, encrypt an additional copy on a different machine or storage
account, restrict filesystem access, schedule backups and rehearse from that
off-host copy. A file in the database container is lost with that container.

For a quiet fixture, compare source and restored counts. On a live service,
concurrent writes/retention can change source counts after the dump's snapshot;
record snapshot-aware evidence instead of treating equality as guaranteed.

Before a real restore, stop application writers, preserve the damaged database
for investigation, restore into a fresh database, check migration/version,
constraints and representative owner-scoped reads, and only then switch every
backend process to that database. Do not aim workers or notification delivery at
the rehearsal database: restored outbox entries could send duplicate messages.
Restore downtime/replay behavior must be tested on the chosen production host.

Redis is not the source of truth for accepted events. Pending database events are
re-enqueued by maintenance. Redis loss also loses throttle counters, queue state
and short-term request windows; hourly baseline history is stored in PostgreSQL.
Explicitly check pending processing and worker readiness during recovery.
Preserve production environment secrets,
TLS configuration and model artifacts separately from the database backup.

The rehearsal database `shield_restore_rehearsal_20261102` was left isolated from
the application for inspection. It is not an automatic failover database.
## Verified local archive transfer and restore, 26 November 2026

The computer backup command staged a 27,771-byte PostgreSQL archive in the
private backup directory. The database container and Windows host reported the
same SHA-256. A separate offline PostgreSQL container restored the archive in
one transaction with `pg_restore --exit-on-error --single-transaction`. The
restored database reported Alembic revision `0011` and zero unvalidated
constraints. The temporary database was removed after verification. This drill
covered a same-computer backup. Off-device recovery remains open.
