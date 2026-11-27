# Concurrent tenant HTTPS benchmark

`tools/benchmark_multitenant.py` measures four synthetic owners/sites with
concurrent ingestion and authenticated owner HTTP reads through local Caddy TLS.
PostgreSQL, Redis, RQ and maintenance run normally. It does not automate a
browser, contact a monitored website, scan a domain or deliver external alerts.
It does not measure ML, SDK overhead, browser rendering or real-user adoption.

The workload distributes a total 500 events/s equally across four sites. Each
site receives the existing 80% benign-shaped, 10% honeytoken and 10% SQL-comment
profile, with 128 synthetic client hashes. Four owner clients cycle through site
lists, inboxes, sensor-health feeds, connection diagnostics, dashboards and feed
HTML, waiting 0.5 seconds after each response. Cold connections remain included.
Every owner has a distinct secure session; credentials exist in memory only.

The runner refuses arbitrary project names, public/wildcard proxy bindings,
nonempty databases and nonempty queues. It requires a fresh `shield-perf-*`
project, both loopback bindings on port 18443, explicit disposable confirmation,
and the exported public CA. It never installs trust or disables verification.
Use base + local-TLS + multitenant Compose files, never the computer-hosting
overlay. The per-run private environment file needs a fresh PostgreSQL password
and `SHIELD_PERF_IMAGE` pointing to the verified cached application image.

Before load, the same event ID is submitted in all four tenants, twice per
tenant, with a spoofed foreign site ID. Owner feeds must contain their own probe
path and no foreign probe. Cross-owner dashboard/feed/key reads must return 404.
During load, owner lists/inboxes/health feeds must contain only owned records.
After processing, foreign incident reads and triage must return 404. These are
specific runtime checks, not proof against every possible isolation defect.

Pass gates are unchanged between pilots and longer runs: no HTTP errors or
incorrect counts, aggregate accepted rate at least 99% of target, per-tenant
ingest and owner-read p95 at most 1000 ms, processing p95 at most ten seconds,
correct rule-source fingerprints, and zero pending/queued/started/failed jobs
after bounded draining. Database counts include one setup probe per site.
Reports include cold-request, maximum and per-route latency, immutable image IDs,
rule provenance, runner hash and checkpoints. Failed results are retained.

## 17 November pilot and connection fix

The original ten-second IPv4-only pilot accepted and processed all 5,000 load
events, but failed the owner-read gate: worst per-owner p95 **2215.454 ms**.
Worst ingest p95 was 292.467 ms and processing p95 5.904 s. All 5,004 rows
(including probes) were present with no wrong rule fingerprint or final backlog.
The failed report remains `outputs/multitenant-pilot-10s.json` in the task
workspace. It is not a passing result.

Four concurrent fresh `localhost` readiness connections then took 2111–2123 ms,
while reused requests took 34–62 ms. Adding an IPv6 loopback listener alongside
IPv4 reduced fresh disposable-proxy requests to 50–54 ms, retaining TLS checks.
Raw-IP HTTPS failed this diagnostic; use the documented localhost origin.
After applying the same binding fix to computer hosting, four fresh readiness
requests took 174–221 ms while the independent load fixture was running. The
existing certificate fingerprint remained unchanged. Neither diagnostic proves
application or browser performance under arbitrary deployment conditions.

The fresh thirty-second IPv6-loopback pilot passed: **15,000** load events,
**504.202 events/s**, **222** concurrent owner HTTP reads, worst per-owner p95
**124.092 ms**, worst ingest p95 **162.408 ms**, and worst processing p95
**3.723 s**. No failed jobs or final backlog remained; all 15,004 stored rows
had the expected rule-source fingerprint. Raw report:
`outputs/multitenant-ipv6-30s.json`. Short-pilot throughput includes batch
scheduling/end effects and must not be substituted for a sustained measurement.

## Single-worker sustained failure

The separate ten-minute run accepted all **300,000** load events, but failed its
120-second drain deadline. At 721.687 seconds from load start, the saved snapshot
had **2,350 pending events**, **62 queued jobs**, one started job and zero failed
jobs. Per-tenant processing p95 was **119.682–119.848 seconds**, far above the
ten-second gate. All 300,004 rows existed and processed rows had the expected
rule fingerprint. This is an overall **failure**, despite successful ingestion.
Raw report: `outputs/multitenant-full-600s.json`. No later drain is substituted
for the missed deadline. The runner now saves ingest timing/rate before draining
so a failed drain cannot omit those fields in future reports.

A sampled pending-batch read used the composite primary key and returned 50
rows in 0.811 ms. This one read plan does not establish the cost of the complete
worker transaction or prove a unique bottleneck. A fresh two-worker comparison
uses the same image, payload mix, 50-event batches and latency gates. The runner
checks the requested replica count, healthy starts, disabled ML configuration,
and each replica's immutable image; successful completion also requires healthy
workers with no restart-count increase. No two-worker result is inferred from
the single-worker measurement.

## Two-worker sustained comparison: 18 November

The fresh two-worker run **passed every gate** with the same payload profile,
batch size, four-site split and thresholds. It accepted **300,000 load events**
over 599.703 seconds: **500.248 events/s**. All 300,004 rows, including probes,
were stored and processed. Across 4,216 concurrent authenticated owner HTTP
reads, the worst tenant p95 was **205.093 ms**. Worst ingest-batch p95 was
**346.266 ms**; worst per-tenant processing p95 was **4.200091 seconds**.
Final pending events, queued/started/failed jobs and incorrect rule fingerprints
were all zero. Both workers finished healthy with zero restarts. The tenant
boundary, duplicate-event, foreign incident read and triage checks passed.

Docker Desktop reported eight CPUs and 3.744 GiB memory; other computer services
were present. The workers retained normal RQ child-process execution and timeouts.
The API/workers used immutable image
`sha256:1da9dccd198c3ce586f15a70ce02ec0715f07d30ebde5f37e03525c8b5c491be`.
ML and scanner traffic were absent. This is one synthetic HTTP/backend workload
on this host, not browser rendering, broad threat accuracy or universal capacity.

Raw private-workspace report: `outputs/multitenant-two-workers-600s-run2.json`.
Report SHA256: `063a2c92c0d096dcb5c588811272633ee6b260979348893539671f54fb8bcadf`.
Runner SHA256: `f39c62e65ee57749b42195587f3f01473a506735e501a4967da7150897a97084`.
The earlier `multitenant-two-workers-600s.json` is a retained **setup failure**:
Docker claimed requested bindings but had published no actual listener, so no
test accounts were created. Recreating only that empty fixture's proxy restored
both loopbacks. The runner and Windows helper now check actual published ports
in addition to requested bindings; neither bypasses TLS verification.

The completed fixture was stopped with its volumes and reports retained.
Computer hosting now declares and runs two healthy workers with zero restarts.
Its retained worker image is `sha256:cc657eaf75dd5a7505ba38b1f5c3c2eebd5171b3b1c9fae682b84556927ca43d`;
it predates the template/CSS update in the comparison image. CA-verified `/ready`
and `/app` returned 200, while unauthenticated `/app/api/sites` returned 401.
These read-only checks are separate from the disposable load comparison; no
load was sent into the owner's account database. Increasing replicas permits different sites to
process concurrently; the existing per-site database lock still serializes
incident/baseline transactions within each site.

## Current rule release: two-worker failure on 21 November

The version 3 application image
`sha256:0429c84028226462eb9af3c67aff0e0dba81bd4b49d1c931e5ac6b6537595ac9`
accepted all **300,000** load events over 599.734 seconds (**500.222 events/s**),
but **failed** the unchanged ten-second processing-p95 gate. Per-site processing
p95 was **33.055–33.119 seconds**. Worst ingest p95 was **421.451 ms** and worst
owner-read p95 **267.641 ms** across 4,052 owner HTTP reads. The final snapshot
contained all 300,004 rows with correct rule fingerprints and zero pending,
queued, started or failed jobs. Eventual draining does not make this a pass.

The runner stopped at the first processing-latency assertion; subsequent final
isolation/worker-health assertions did not all execute. Both workers had zero
restart counts when inspected afterward. The isolated fixture was stopped;
its database volumes and original failure report remain retained.

Private report: `outputs/shield-perf-v3-20261121/benchmark.json`.
SHA256: `51a8ce031fe7ce11567f638b22377c109b61d7a14e12b50f6c76bcb57f99080d`.
The runner hash matches the earlier successful version 2 comparison. This result
supersedes any inference that version 2's passing capacity transfers to the
current release. At this failure checkpoint, computer hosting still ran two
workers and its current capacity target was unproven.

An alternating same-host rule-only replay of the exact ten-event mixed profile
measured median cost of 0.01123 ms/event for version 2 and 0.01129 ms/event for
version 3. It excludes database work, queue waiting and RQ child-process overhead.
Retained job logs showed median execution time increasing from 0.1204 to 0.1345
seconds, and p95 from 0.2186 to 0.2932 seconds. These observations do not identify
a unique cause: co-resident host load was uncontrolled and the failed run did
not capture resource samples during load. A fresh three-worker comparison with
queue/resource observation was the next experiment; latency gates stayed fixed.

## Current rule release: three-worker pass on 21 November

The fresh three-worker instance **passed all unchanged gates** using the same
version 3 image, four tenants, payload profile and 500 events/s target. It accepted
**300,000** events over 600.187 seconds (**499.844 events/s**). All 300,004 stored
rows were processed with correct rule fingerprints. Worst processing p95 was
**5.654360 seconds**, worst tenant owner-read p95 **314.106 ms** across **3,928**
reads, and worst ingest p95 **505.908 ms**. No HTTP errors or final pending,
queued, started or failed jobs remained. Duplicate-event/foreign-tenant checks
passed; all three normal RQ workers finished healthy with zero restarts.

Maximum ingest latency was **2,417.997 ms**, despite passing the p95 gate. This
is measured bounded-workload capacity, not flawless latency or capacity for
arbitrary tenants, traffic, ML/scanner activity or browser rendering. The private
harness sampled fixture container resources and queue lengths roughly every
15 seconds; sampling itself adds overhead. Other host activity was uncontrolled,
so the comparison supports this configuration without proving a unique cause
for the earlier two-worker slowdown.

Private report: `outputs/shield-perf-v3-three-20261121/benchmark.json`.
SHA256: `b360c10cd73b257dd41e4e5a5aa0ef1dd76cd5637ebc20593e06ece0bc3bb557`.
Resource samples: `outputs/shield-perf-v3-three-20261121/resources.jsonl`.
The fixture is stopped and its volumes/evidence retained. The failed two-worker
fixture's configurations and timestamped logs were archived privately before
removing only its stopped containers and three empty networks; all four volumes
and the unchanged original failure report remain retained. No global prune ran.

Computer hosting now declares **three workers**. After a fresh private backup,
only the third worker was added; the two existing worker containers, all service
environment values, application image and full database table digests remained
unchanged. All three workers were healthy and CA-verified readiness passed.
The existing two workers each had five historical restarts; the new worker had
zero. Retained logs identify five warm shutdowns after unhealthy registration
checks on each existing worker, matching the recovery mechanism documented in
`WORKER-RECOVERY.md`. Why those registrations became unhealthy is not established;
the isolated fixture's zero-restart result must not be substituted for host history.
Private activation evidence: `outputs/three-worker-runtime-20261121.json`.

## Reproduce on a fresh disposable instance

Prepare a private environment file outside source control, choose a fresh
`shield-perf-*` project, and start only db, redis, api, worker, maintenance and
localproxy using these three Compose files. Use `--no-build --pull never --wait`
with an already verified application image. Export only the proxy's public CA
from `/data/caddy/pki/authorities/local/root.crt`; keep its keys and database
credentials private. Then run:

```powershell
python tools/benchmark_multitenant.py --project shield-perf-YOUR-RUN --ca C:\PRIVATE\perf-ca.crt --output C:\PRIVATE\perf-results.json --seconds 600 --rate 500 --confirm-disposable
```

Project suffixes must be lowercase. Use a new project/database for each run.
To compare two workers, start Compose with `--scale worker=2` and pass
`--workers 2` to the runner. The runner observes configuration; it never scales
or changes the stack itself.

Do not clear an existing database to satisfy the freshness guard. Stop the
specific fixture's containers afterward, preserving its volume/report until
review. Do not stop unrelated applications or remove computer-hosted data.
If Docker's automatic network pool is exhausted, inspect project ownership and
remove only finished disposable fixture containers/networks, preserving their
named database/CA volumes and reports. Never use a global Docker prune. The
original ten-second pilot's containers/networks were removed for this reason;
its volumes, private environment and failed report remain retained.

## 24 November capacity recheck

The 24 November release with server-side redaction sustained 500.16 accepted
events/s across 300,000 synthetic events over 599.813 seconds. Using verified
loopback HTTPS, four synthetic tenants and three workers, worst-tenant p95s
were 419 ms for ingest batches, 322 ms for owner HTTP requests, and 0.438 s
for processing. All queues drained, with zero failed jobs and zero worker
restarts. The initial fixture setup hit Docker's default subnet limit and
sent no traffic. A fresh fixture with explicit private subnets passed and
was stopped. The report is
`outputs/shield-perf-ingest-redaction-20261124-r2/benchmark.json` (SHA256
`399aa36aba98767aa45a90fe9948986175881ec7dd4474ccc55dd9c94b313437`).
This was a rules-only workload with concurrent owner HTTP reads. Browser,
scanner, ML, and real-site performance are still open.
