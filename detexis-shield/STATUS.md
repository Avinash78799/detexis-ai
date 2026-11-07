# Implementation and acceptance status

Current checkpoint: 7 November 2026. See [PRODUCT-STATUS.md](PRODUCT-STATUS.md)
for current features and [RELEASE-READINESS.md](RELEASE-READINESS.md) for unresolved
release gates. CI run 42345456703 at source `f9dc418` passed. The full mixed local
load gate passed with 300,000 events and 1.608-second processing p95. ASGI and
Flask in-process overhead measurements are recorded in `BENCHMARKS.md`.
These checks do not establish production hosting, real-user adoption or real-data
ML quality. Hosting must require neither payment nor card verification.

## Historical 1 November checkpoint

The phase table and measurements below are retained as historical evidence;
they are not the latest test counts, runtime versions or load results.

| Phase | Implemented | Remaining acceptance |
| --- | --- | --- |
| 0 | Threat model, key/site boundary, monitor-only contract | Deployment-specific security review |
| 1 | ASGI/WSGI, buffers, retry/backoff, features, config/heartbeat, Redis limits, migrations, fail-open/overhead tests | Persistent-host socket/server latency measurement |
| 2 | RQ + pending-row recovery, 12 mapped heuristics with 72 positive/negative cases, incidents, HTMX feed, alert outbox | Live notification delivery to owner-configured channels |
| 3 | Shared features, temporal/session purge, independent-dataset test, logistic/XGBoost pipeline, FPR bounds, versioned artifacts, SHAP smoke test, fallback | Compatible CSIC/CIC request conversion, real benign traffic, real-data training/evaluation |
| 4 | Seven-day same-hour mean+3σ baseline, recon→exploit, failed-login/flood correlation, dedupe, retention, local 500 events/s for 600s with measured processing lag | Production/ML-enabled load tests; actual credential-stuffing correlation needs a privacy-reviewed account identifier |
| 5 | Ownership proof, pinned-IP fetch, DNS/redirect/port checks, size/time caps, isolated scanner config and local network validation, score, daily rescan schedule | Production network validation and verified-domain scan |
| 6 | Tenant/XSS tests, Docker/TLS deployment definitions, real PostgreSQL/Redis CI job | Production credentials/host, backup/restore and deployment smoke test |
| 7 | Onboarding/demo runbook and honest benchmark format | Permissioned 5–10-site trial, real N, recorded demo video and final benchmark table |

Latest local regression validation: 222 tests passed, one separate real-service
CI test skipped locally. The Docker stack passed ingest, duplicate suppression,
RQ incident creation, authenticated dashboard and a real API-outage fail-open
check. The isolated scanner cannot resolve the datastore services and contains
neither datastore credentials nor SQLAlchemy. The latest CI results on the PR
cover the separate PostgreSQL/Redis migration integration test. CI at `f112cd5`
passed both jobs: the PostgreSQL/Redis suite and the ML software smoke test.

The final local rules-only load run passed: all 300,000 events accepted and
processed in a ten-minute run, no HTTP/transport errors, no failed RQ jobs and no
pending events at load end. Median/p95 ingest batch latency was 85.98/319.28 ms;
median/p95 database-receipt-to-processing time was 0.129/6.480 seconds.
This is one loopback run with uniform synthetic traffic and one worker, not a
production or ML throughput claim. See [BENCHMARKS.md](BENCHMARKS.md) and the
complete [report](load-test-results.json), including environment details.

Logistic and XGBoost artifact/runtime checks and three SHAP reasons passed using
a deliberately simple software fixture (`ml-smoke-results.json`). These results
verify the software path, not generalization or a real false-positive rate.

The ASGI microbenchmark files record earlier sensor measurements with the exact
profile/runtime. They are not network/server or sustained throughput results.
No real false-positive rate, monitored-site count or deployment success is claimed.

Baselines require seven recorded same-hour samples; missing telemetry is not
interpreted as zero traffic. A floor of 100 requests/hour reduces low-volume noise.
Rules detect a narrow set of syntactic signals and may miss encoded/contextual
attacks or flag legitimate security tests. Broader false-positive review requires
representative benign traffic and a documented alert budget.
