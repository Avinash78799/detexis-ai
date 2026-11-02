# Processing latency release gate

Shield needs to deliver incidents promptly as well as accept events. The local
rules-only acceptance command now requires p95 receipt-to-processing lag of at
most **10 seconds**, in addition to its capacity/error/drain checks. This is an
engineering release target, not a promised production service-level agreement.

```sh
python tools/validate_stack.py --rate 500 --seconds 600 --max-processing-p95-seconds 10
```

## Baseline miss, 2 November 2026

`load-test-after-connection-index.json` preserves the original report from the
run before the stricter latency gate was added. It accepted 300,000 events in
599.906 seconds with no transport/HTTP errors, failed RQ jobs, pending events or
queued jobs at completion. The outage/fail-open check passed. However:

- Processing lag: median **25.652 s**, p95 **102.931 s**.
- Peak sampled backlog: **48,300 events**.
- Batch ingest response latency: median **102.496 ms**, p95 **1,232.795 ms**.

The report's original `acceptance_passed: true` means its older capacity gate
passed. **This run fails the new 10-second processing-latency release target.**
Do not present it as proof of prompt real-time detection or a production SLA.
The earlier faster report is retained as historical evidence, not substituted
for the latest result.

Environment: local Docker Desktop, PostgreSQL 16, Redis 7, one RQ worker, rules
only, existing synthetic history of roughly 900,000 events before this run.
Documentation/package building, tests and browser checks also ran on the host
during this run; cache state and host load were not controlled. These conditions
limit comparisons and do not establish that one index alone caused the delay.

## Query and write-path investigation

In an isolated rolled-back fixture, PostgreSQL estimated a newly created tenant
had one event despite 10,000 inserted events. Fetching a worker batch of 100 IDs
used `ix_events_site_ts`, scanned all 10,000 tenant rows and filtered out 9,900.
Removing the receipt-time ordering did not fix that plan. Replacing the batch
with 100 individual point lookups was worse: the same mistaken estimate caused
repeated broad scans. Neither attempted rewrite was shipped.

A measured change keeps the site identity in a scalar init-plan
parameter so PostgreSQL uses average site selectivity rather than the stale
new-tenant literal estimate. It selected the composite primary key and removed
no unrelated rows in the fixture, but increased planning work. This SELECT-only
change was implemented and tested under the full load. Its report,
`load-test-worker-estimates.json`, still failed: p95 processing lag was 41.036 s,
one 100-event batch had a RemoteProtocolError, and 299,900 events were accepted.
Median processing lag was 0.424 s and the queue drained. The API container showed
no restart or OOM event; the single connection failure's cause was not established.
Neither the transport miss nor the long tail is discarded from the evidence.

A direct 2,000-event/20-batch worker profile then took 2.627 s, including 1.552 s
in batched ORM UPDATE execution. A rolled-back PostgreSQL fixture confirmed that
an individual event UPDATE also scanned 10,000 tenant rows and filtered 9,999.
Using the scalar site parameter selected the primary key instead: observed UPDATE
execution changed from 4.662 ms to 0.172 ms in that fixture.

The write path now accumulates computed features/findings/processed timestamps and
executes a bound batch UPDATE with both tenant and event keys. It uses the same
PostgreSQL site parameter strategy. The site's existing row lock still serializes
processing, and event results, incidents and baselines commit in one transaction.
Event ORM objects are read as inputs; result writes use the table-level statement
so ORM-generated literal-site UPDATEs cannot reintroduce the measured plan issue.

The repeated direct profile took 1.379 s, including 0.361 s in the event UPDATE
batch. These small local profiles do not include RQ fork/queue overhead and are
not throughput acceptance results. The Docker base tag also resolved to a newer
image on rebuild; cache and runtime differences limit causal comparisons.

Regression checks cover tenant-colliding event IDs, duplicate jobs and a failure
injected after event SQL executes: rollback leaves events pending and no incident,
and retry records each event once. The full load run must independently prove
the latency target. New reports record actual worker source SHA-256, Python,
package/PostgreSQL/Redis versions, migration and whether a model was enabled.
Different tenant distributions and production hosts require fresh measurements.

## Sustained write pressure

The bulk-write full run, `load-test-bulk-results.json`, also failed the release
gate: all 300,000 events were accepted, but 53,300 remained pending at load end.
They drained in 119.594 s; median/p95 processing lag was 10.261/128.005 s. There
were no transport errors or failed jobs. Fast direct profiles did not establish
sustained whole-stack performance. A live read-plan check used the primary key
both with and without the pending-state predicate, so that check did not justify
another SELECT rewrite.

The database then had approximately 1.8 million synthetic events and about 1 GB
of event indexes, including a 205 MB duplicate receipt-time index and a 108 MB
processed-time index retaining completed history. Its cache was 128 MB, WAL
compression was off, and background-writer allowance was 100 pages per round.
These observations motivated storage/write changes; they do not alone prove
that any single setting caused the long-tail delay.

Migration `0008` removes the duplicate receipt-time index and replaces the full
processed-time index with a partial recovery index on receipt time, including
site/event IDs, for `processed_at IS NULL` only. Completed history is excluded.
With no pending work it occupied 8 KB locally, replacing about 313 MB of old
indexes. The connection covering index retains the removed receipt-time prefix.
PostgreSQL operations run concurrently; SQLite uses its supported partial index.
An isolated restored PostgreSQL database passed upgrade/downgrade/upgrade while
preserving all 899,915 events. SQLite's schema roundtrip also passed.

Compose now defaults to a configurable 512 MB database cache
(`POSTGRES_SHARED_BUFFERS`), WAL compression, and a background-writer allowance
of 1,000 pages per round. The full stack must fit the actual host's RAM; the cache
is not a total memory cap. Five-minute checkpoints, fsync and synchronous commits
remain enabled and are recorded in reports. The next full acceptance run must
prove this configuration; it is not accepted based on index sizes or profiling.

PostgreSQL documents the tradeoffs for [partial indexes](https://www.postgresql.org/docs/16/indexes-partial.html),
[cache/background writer settings](https://www.postgresql.org/docs/16/runtime-config-resource.html)
and [WAL compression](https://www.postgresql.org/docs/16/runtime-config-wal.html).
