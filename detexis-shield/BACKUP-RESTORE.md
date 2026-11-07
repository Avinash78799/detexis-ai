# PostgreSQL backup and restore rehearsal

The database is the durable record of sites, accounts, sensor-key verifiers,
events, incidents, scans and alert delivery state. Keep backups private: they
contain password/session/key verifiers and request telemetry. Never commit them.

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

## Repeat safely

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
