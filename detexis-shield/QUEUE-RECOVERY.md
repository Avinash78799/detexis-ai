# Pending-event and duplicate-delivery rehearsal

On 18 November 2026, a new isolated database was restored from the completed
four-site fixture's private host-copy backup. Complete-row fingerprints matched
the original 300,004-event source. A fresh unpublished Redis service and the
retained application image ran on the fixture's internal Docker control network.
The owner database was untouched; original fixture rows matched afterward.

`tools/check_restored_queue.py` exercises actual FastAPI ASGI ingestion, real
PostgreSQL/Redis and the normal `rq.worker.Worker` with forked jobs and timeouts.
It uses the same database fork protection as `app.run_worker`. It does not run
maintenance or external notification delivery. External HTTP/TLS, service cutover,
crash-mid-transaction, scanner and ML acceptance are outside this check.

## Result

Four synthetic sites each submitted 100 events through `/v1/events` with fresh
test-only sensor keys. Every batch returned 202 with 100 accepted events and
successful enqueue. Erasing only the dedicated Redis database lost four jobs;
the 400 committed pending PostgreSQL rows remained unchanged.

Two `recover_pending` calls before processing each rediscovered 400 rows and
produced eight jobs, intentionally including duplicates. Normal RQ workers
drained them. Four further jobs replayed those same IDs. Finally, retrying all
400 events through ingestion reported duplicates without enqueueing new work.

| State | Before traffic | After API acceptance | After recovery and retries |
| --- | ---: | ---: | ---: |
| Stored events | 300,004 | 300,404 | 300,404 |
| Pending events | 0 | 400 | 0 |
| Incidents | 1,536 | 1,536 | 1,540 |
| Incident event-count sum | 60,000 | 60,000 | 60,080 |
| Alert records | 1,536 | 1,536 | 1,540 |
| Hourly baseline count sum | 300,004 | 300,004 | 300,404 |

Each tenant had exactly 20 findings among 100 new events, with expected rule
fingerprints. Complete-row digests of incidents, alerts and hourly buckets were
unchanged by duplicate job delivery. Final pending/queued/started/failed counts
were zero; recovery returned zero. All rehearsal containers were stopped and
private reports/databases retained.

Application image: `sha256:1da9dccd198c3ce586f15a70ce02ec0715f07d30ebde5f37e03525c8b5c491be`.
Measured checker SHA256: `d2bd55091f269991acd806ab0f7c4214418d4462f90dd5a963bab562c4eea3df`.
Private report: `outputs/queue-replay-9e6def0fff87/report.json`, SHA256
`3f3f093aaab313a2f984483bdb5a041055474133d94f7064b09028791312a0c5`.

The earlier `outputs/queue-replay-7bcb0f68ce0a/report.json` is a retained setup
failure: Redis tried `chown` after capabilities were dropped. The successful
fixture started Redis directly as UID/GID 10001 with a matching tmpfs. No replay
assertions were reached in that failed setup attempt.

## Repeat on an isolated copy

Use `BACKUP-RESTORE.md` to restore a stopped synthetic four-site `.example`
fixture at schema 0009 into a **new** `shield_restore_*_replay` database. Preserve
source fingerprints. Never repoint or reset a live database.

Create fresh `shield-replay-redis-<hex>` Redis on that fixture's internal control
network, with no host ports or persistence. Use a non-root UID and matching-UID
tmpfs when dropping capabilities. Do not use computer-hosting Redis or an
existing queue: the checker intentionally calls `FLUSHDB` on this test service.

Prepare a private env file: `DATABASE_URL` for the new replay database on host
`db`, `REDIS_URL=redis://shield-replay-redis-<hex>:6379/0`, `PYTHONPATH=/srv`,
empty `SHIELD_MODEL_DIR` and `SHIELD_ALERT_TARGETS={}`. Keep the fixture's saved
database password private and unchanged. Target guards reject ordinary database
names, other database hosts and Redis names.

Mount the checker read-only into the retained verified application image and
run `python /check_restored_queue.py` on that internal network. Use a read-only
root filesystem, writable `/tmp` tmpfs, no host ports, all capabilities dropped
and `no-new-privileges`. Capture JSON privately; stop only rehearsal containers
afterward, preserving databases and reports.

## Limits

Maintenance normally retries pending database events every minute. Recovery may
enqueue duplicate jobs before previous jobs finish; this checks idempotency,
not queue-growth limits during a prolonged outage. Redis loss resets throttle
counters and short-term request/login windows. Pending recovery cannot recreate
those windows or guarantee identical behavioral findings. External delivery,
live database switching and off-device disaster recovery remain separate gates.
