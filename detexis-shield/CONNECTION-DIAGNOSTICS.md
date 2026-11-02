# Sensor setup diagnostics

In your workspace, choose **Check sensor connection** beside a website. The
check requires an owner session and only reads that owner's site. It returns no
API-key values, request paths, query strings or customer IP hashes.

- **Active key:** at least one unrevoked key exists; this does not prove that the
  application installed that key. Replace/reconfigure revoked keys separately.
- **Heartbeat:** waiting before the first heartbeat, reporting within three
  minutes, or overdue afterward. The SDK normally sends one every minute.
- **Request processing:** no events yet, latest received event pending (up to one
  minute), delayed, or processed. This describes the latest event only, not the
  entire queue. A quiet website is not automatically offline; a processed normal
  request need not create an incident.

The browser shows concrete troubleshooting steps and receipt/heartbeat times.
The check is manual, so it does not add continuous polling load to every website
card. Domain ownership verification remains a separate prerequisite for scans.

## Database performance investigation

On 2 November 2026, the local PostgreSQL 16 validation fixture contained five
sites with 1, 6, 299,903, 300,003 and 300,003 synthetic events. `EXPLAIN (ANALYZE,
BUFFERS)` of the latest-event query found that the planner sometimes preferred
the global `received_at` index despite an existing `(site_id, received_at)` index.
For older high-volume sites it filtered 300,010 and 599,913 unrelated rows;
observed execution times were 1,891.932 ms and 2,867.241 ms.

Migration `0007` adds `(site_id, received_at) INCLUDE (processed_at)`. The same
queries then used `ix_events_site_connection` with a backward index-only scan
and a site condition. Observed execution times for those two sites were 0.165 ms
and 0.078 ms; all five observed executions ranged from 0.017 to 0.225 ms. These
are single local database-plan observations, not end-to-end route percentiles or
a production latency guarantee. Cache state was not controlled. Additional index
storage/write cost must be included in subsequent ingestion load tests.

The PostgreSQL migration builds the index concurrently. Run only one migrator.
If an interrupted build leaves an invalid index, inspect `pg_index.indisvalid`
and remove that specific invalid index before retrying the failed migration;
do not stamp the migration as successful. SQLite uses a normal index for local
functional testing. The older received-time index is retained for compatibility
with existing queries; index consolidation requires its own measured review.

Functional tests cover tenant isolation, no-event/revoked-key/stale states,
receipt-time ordering despite sensor clock skew, and omission of request values.
Browser acceptance covered desktop and a 390-pixel mobile viewport without
horizontal document overflow. Synthetic incident evidence and saving a review
decision were also verified through the UI.
