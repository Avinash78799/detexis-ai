# Local validation results

## Latest full run: 2 November 2026

Source `a60fb76`, migration `0008`. The [runtime-fingerprinted report](load-test-compatible-lock.json)
passed the 500 events/s, ten-minute rules-only workload and the ten-second p95
processing-lag gate. One RQ worker processed one site's uniform `GET /benchmark`
traffic with one IP hash and the request-flood rule active. PostgreSQL cache was
512 MB; WAL compression was enabled. Fsync, synchronous commits and five-minute
checkpoints remained enabled. Runtime versions and the worker's SHA-256 are in
the report; the hash matched the checked-in source.

| Measurement | Result |
| --- | ---: |
| Events sent / accepted / processed | 300,000 / 300,000 / 300,000 |
| Actual accept rate | 500.078 events/s |
| HTTP errors / transport errors / failed RQ jobs | 0 / 0 / 0 |
| Ingest batch latency median / p95 | 62.991 / 137.454 ms |
| Receipt-to-processing lag median / p95 | 0.106 / 2.198 s |
| Pending events at load end | 3,000 |
| Drain time / pending after drain | 8.953 s / 0 |

Three additional setup events are excluded from the 300,000-event generated
workload. CI at this source passed 238 tests, including real PostgreSQL/Redis
ingestion concurrent with processing, duplicate-worker exclusion and account
recovery races. The separate ML software smoke job passed.

The preceding 102.931, 41.036, 128.005 and 29.005-second p95 misses are retained
with their reports and investigation in [PROCESSING-LATENCY.md](PROCESSING-LATENCY.md).
The fixes address new-tenant query estimates, transactional result writes,
redundant index/write pressure and a site lock that blocked ingestion's foreign
key checks. None of the failed runs is presented as a passing latency result.

These are local development measurements, not a production SLA or a real-data
false-positive rate. Mixed traffic, ML-enabled processing and the actual
deployment host still need measurements. Dashboard freshness additionally
includes SDK batching and polling. Synthetic fixtures are not customer adoption.

## Historical 1 November run

Measured 1 November 2026. Source commit: `f112cd5`. These are development
measurements; a deployment needs its own workload and resource measurements.

### Ten-minute load test

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

That implementation also batched PostgreSQL ORM updates and recorded HTTP
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
