# Local validation results

Measured 1 November 2026. Source commit: `f112cd5`. These are development
measurements; a deployment needs its own workload and resource measurements.

## Ten-minute load test

One rules-only RQ worker, one site, one IP hash, `GET /benchmark` in batches of
100, with the request-flood rule active. The generator sent 500 events/second for
600 seconds. Docker Desktop exposed eight CPUs and 4,019,851,264 bytes of memory.
PostgreSQL was 16.15 from the cached `pgvector/pgvector:pg16` image, with only
`plpgsql` enabled; Redis was 7.4.10. CI separately uses official PostgreSQL 16
Alpine and Redis 7 Alpine images. Traffic used loopback HTTP, not internet/TLS.

| Measurement | Final result |
| --- | ---: |
| Events sent / accepted / processed | 300,000 / 300,000 / 300,000 |
| HTTP errors / transport errors / failed RQ jobs | 0 / 0 / 0 |
| Pending events at load end | 0 |
| Ingest batch latency median / p95 | 85.98 / 319.28 ms |
| Receipt-to-processing latency median / p95 | 0.129 / 6.480 s |
| Sampled pending events approximately each minute | 0–100 |

The database has three additional setup events used for the functional checks.
The successful run does not establish a production SLA, representative attack
recall, a real-data false-positive rate or ML-enabled throughput. End-to-end
dashboard freshness additionally includes SDK batching and five-second polling.

### What changed after measuring

The [original run](load-test-before-optimization.json) accepted all events but left
220,700 unprocessed at load end and 201,200 after a two-minute drain window.
Batch-local database caches, pipelined Redis windows and preloaded RQ job modules
removed repeated work. A [first optimized run](load-test-first-optimization.json)
processed all accepted events, but one batch of 100 failed ingestion; its test
did not record enough detail to identify that failure's cause. It remains a
failed acceptance result.

The final implementation also batches PostgreSQL ORM updates and records HTTP
and transport failure categories. Validation rejects an already queued workload
before starting. The [final report](load-test-results.json) records the successful
run. Both earlier reports are retained rather than replaced by the passing result.

## Sensor overhead and functional checks

The ASGI in-process tests recorded added latency of 0.0494 ms median / 0.0862 ms
p95 for a normal query, and 1.07665 / 1.7761 ms for the large-query profile. See
[SENSOR.md](SENSOR.md) and the original JSON reports for method and limits. These
are not Flask or deployed-server overhead measurements.

The Docker test checks duplicate suppression, RQ incident creation, authenticated
dashboard access and a host response while the actual ingest API is stopped.
Scanner-container checks confirmed no datastore DNS access, datastore credentials
or SQLAlchemy dependency. No public-domain scan was performed.

CI passed 223 tests on the preceding worker optimization, including real
PostgreSQL/Redis migration and processing; both jobs also passed at `f112cd5`.
The separate ML job checks logistic/XGBoost loading and SHAP reasons using a
controlled fixture. It is not evidence of real-world ML detection quality.
