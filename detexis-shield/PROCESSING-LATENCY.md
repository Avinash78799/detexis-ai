# Processing latency release gate

Shield needs to deliver incidents promptly as well as accept events. The local
rules-only acceptance command now requires p95 receipt-to-processing lag of at
most **10 seconds**, in addition to its capacity/error/drain checks. This is an
engineering release target, not a promised production service-level agreement.

```sh
python tools/validate_stack.py --rate 500 --seconds 600 --max-processing-p95-seconds 10
```

## Latest ten-minute run, 2 November 2026

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

## Investigation in progress

In an isolated rolled-back fixture, PostgreSQL estimated a newly created tenant
had one event despite 10,000 inserted events. Fetching a worker batch of 100 IDs
used `ix_events_site_ts`, scanned all 10,000 tenant rows and filtered out 9,900.
Removing the receipt-time ordering did not fix that plan. Replacing the batch
with 100 individual point lookups was worse: the same mistaken estimate caused
repeated broad scans. Neither attempted rewrite was shipped.

A further measured candidate keeps the site identity in a scalar init-plan
parameter so PostgreSQL uses average site selectivity rather than the stale
new-tenant literal estimate. It selected the composite primary key and removed
no unrelated rows in the fixture, but increased planning work. This candidate
is **not yet implemented or validated under the full load test**. Query-plan
observations alone do not prove the cause or solution for end-to-end delay.

Next work must verify a fix for new, growing tenants and repeat the full test,
including tenant isolation, duplicate processing and the latency target.
