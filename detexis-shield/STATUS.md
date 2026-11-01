# Implementation and acceptance status

Updated 1 November 2026. This file distinguishes code from evidence.

| Phase | Implemented | Remaining acceptance |
| --- | --- | --- |
| 0 | Threat model, key/site boundary, monitor-only contract | Deployment-specific security review |
| 1 | ASGI/WSGI, buffers, retry/backoff, features, config/heartbeat, Redis limits, migrations, fail-open/overhead tests | Persistent-host socket/server latency measurement |
| 2 | RQ + pending-row recovery, 12 mapped heuristics with 72 positive/negative cases, incidents, HTMX feed, alert outbox | Live notification delivery to owner-configured channels |
| 3 | Shared features, temporal/session purge, independent-dataset test, logistic/XGBoost pipeline, FPR bounds, versioned artifacts, SHAP smoke test, fallback | Compatible CSIC/CIC request conversion, real benign traffic, real-data training/evaluation |
| 4 | Seven-day same-hour mean+3σ baseline, recon→exploit, failed-login/flood correlation, dedupe, retention, load tool | 500 events/s for 600s with measured processing lag; actual credential-stuffing correlation needs a privacy-reviewed account identifier |
| 5 | Ownership proof, pinned-IP fetch, DNS/redirect/port checks, size/time caps, isolated scanner config and local network validation, score, daily rescan schedule | Production network validation and verified-domain scan |
| 6 | Tenant/XSS tests, Docker/TLS deployment definitions, real PostgreSQL/Redis CI job | Production credentials/host, backup/restore and deployment smoke test |
| 7 | Onboarding/demo runbook and honest benchmark format | Permissioned 5–10-site trial, real N, recorded demo video and final benchmark table |

Latest local regression validation: 222 tests passed, one separate real-service
CI test skipped locally. The Docker stack passed ingest, duplicate suppression,
RQ incident creation, authenticated dashboard and a real API-outage fail-open
check. The isolated scanner cannot resolve the datastore services and contains
neither datastore credentials nor SQLAlchemy. The latest CI results on the PR
cover the separate PostgreSQL/Redis migration integration test.

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
