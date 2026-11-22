# Sensor socket-overhead investigation

15 November 2026: `sensor-socket-benchmark.json` is a completed **failed**
performance gate, not a production overhead certification. The SDK was unchanged.
The harness alternates plain and instrumented requests over actual loopback TCP,
400 measured pairs per profile with 20 warmups, using a real background sender.
The two profiles exercise ordinary and long queries. It measures both an online
synthetic collector and a reserved non-listening loopback port.

| Harness | Backend | Normal added median / p95 | Large added median / p95 |
| --- | --- | --- | --- |
| Uvicorn ASGI | Online | 0.121 / 0.360 ms | 0.805 / 1.610 ms |
| Uvicorn ASGI | Refused | 0.094 / 0.251 ms | 0.786 / 1.985 ms |
| Werkzeug threaded WSGI | Online | 0.331 / **13.162 ms** | 1.242 / **18.900 ms** |
| Werkzeug threaded WSGI | Refused | 0.204 / 8.563 ms | 1.096 / **15.942 ms** |

The unchanged targets are median <5 ms and p95 <10 ms for each case. All ASGI
cases passed; three WSGI cases failed. Baseline WSGI p95 ranged from 14 to 31 ms,
so end-to-end variability is substantial. This does not isolate a regression
inside middleware. A production-server comparison and profiling are required;
do not dismiss the failure or change the target to make it pass.

Each online collector received all 840 expected events (including warmups), with
zero drops and zero occurrences of the seeded secret in redacted query values.
Offline host responses all completed; all 840 events per case were eventually
counted as dropped after close. A disconnected sender is allowed to lose events.
This fixture checks one named query secret, not comprehensive privacy coverage.

Source fingerprints identify the benchmark and SDK files. This is sequential,
single-process, local TCP evidence on Windows. It does not exercise actual Shield
ingest/DB/worker delivery, internet TLS, concurrent traffic, Linux hosting,
streaming workloads or a production latency guarantee. ASGI telemetry runs after
the response body is sent, so client completion can precede telemetry completion.
Online event totals are checked separately before shutting down the sender.

```powershell
$env:NO_PROXY='127.0.0.1'
python tools/benchmark_sensor_sockets.py --samples 400
```

Only ephemeral loopback listeners and synthetic traffic are used. No public URL,
real website, private API key, persistent account or malware is involved.

## Production WSGI comparison

Waitress 3.0.2, four worker threads, passed all four unchanged targets in two
independent 400-pair runs with the same SDK sources. The first run's added
median/p95 was 0.112/0.651 ms (normal online), 0.634/2.477 ms (large online),
0.139/0.641 ms (normal refused), and 0.907/3.017 ms (large refused). The repeat's
largest added p95 was 3.455 ms. Each online run received all 840 expected events,
with zero drops and zero seeded-secret occurrences. Offline responses completed
and every expected event was counted as dropped after shutdown.

Raw reports: `sensor-socket-waitress.json` and
`sensor-socket-waitress-repeat.json`. The earlier failed Werkzeug result remains
unchanged. This comparison changes the host-server harness, not SDK code. It
supports this tested server configuration; it does not identify every source of
Werkzeug timing variation or establish concurrent/deployed Flask performance.

```powershell
python -m pip install waitress==3.0.2
$env:NO_PROXY='127.0.0.1'
python tools/benchmark_sensor_sockets.py --framework wsgi --wsgi-server waitress --samples 400 --output sensor-socket-waitress.json
```

For a real Flask host, use an appropriate production server rather than the
Flask development server. On Windows, a module exporting `app` can be served
locally using `waitress-serve --listen=127.0.0.1:8080 --threads=4 your_module:app`
after wrapping `app.wsgi_app` with the SDK. Replace `your_module` with the actual
module name. The server dependency is optional for sensor users; it is pinned in
development requirements for this benchmark, not added to the sensor package.
TLS, process supervision and actual workload sizing remain deployment work.

Primary server reference: [Waitress documentation](https://docs.pylonsproject.org/projects/waitress/en/stable/).

## Four-client concurrent check — 22 November

The harness now accepts `--concurrency` (1–16, default 1). Each independent
HTTP client alternates baseline/observed requests, reverses pair order, warms up
20 pairs and records the requested samples per profile. A barrier starts clients
together for each profile. Both pooled and **every-client** median/p95 targets
must pass; a fast client's samples cannot hide a slower client's tail. A focused
regression checks precisely that case. Existing reports cannot be overwritten.

The first four-client, 200-pair-per-client Windows run **failed overall**:

| Host / collector | Normal worst client p95 added | Large-query worst client p95 added | Large-query pooled p95 added |
| --- | ---: | ---: | ---: |
| ASGI / online | 1.741 ms | **10.696 ms** | 9.128 ms |
| ASGI / refused | 1.749 ms | 9.222 ms | 7.864 ms |
| Waitress / online | 2.543 ms | **20.770 ms** | 18.744 ms |
| Waitress / refused | 2.745 ms | **27.728 ms** | 22.398 ms |

All pooled medians stayed below 5 ms. Ordinary-query profiles passed every
client gate, but large queries missed the unchanged 10 ms tail target in three
cases. ASGI online would misleadingly pass if only the pooled p95 were used.
Each online case received all **1,760** expected synthetic events, with zero
seeded-secret occurrences or drops. Each refused-connection case completed host
responses and counted all 1,760 events as dropped after sender close. The SDK
source was unchanged; this is newly measured incomplete performance evidence,
not a fix or a passing concurrency claim.

The host and benchmark clients share one Windows machine, and both paired paths
can experience server scheduling/contention. Waitress used four worker threads
and reported small task queues. This does not identify a unique SDK bottleneck;
CPU profiling and controlled comparisons remain necessary before optimization.
ASGI measurement still ends at client response completion, before telemetry may
finish. The synthetic collector is not the actual ingest/Redis/worker pipeline.

Private report: `outputs/sensor-concurrent-four-20261122.json`.
Report SHA256: `fa17189a6f69ca26622fe1c056a544c56c623db45cba895de3f93d85e32af61f`.
Harness SHA256: `75cadeedcd938fa402a389684d1c5c7ef02adbd4ca373c0f281fded05b6264a7`.
The report includes all SDK hashes, per-client/pooled distributions, expected and
delivered/dropped event counts. No public listener, real account key or domain
scan was used.

```powershell
python tools/benchmark_sensor_sockets.py --framework both --wsgi-server waitress --samples 200 --concurrency 4 --output C:\PRIVATE\new-concurrent-report.json
```

Do not substitute the earlier sequential passes for this failed concurrent gate.

## Percent-decoding optimization: target still missed

Profiling 3,000 large-query redaction/feature calls identified percent-decoding
as the largest measured CPU cost. An ASCII-only fast path batches contiguous
valid escape runs through native hex decoding, splitting field separators before
decoding. Ordinary/Unicode input retains the standard parser. Invalid escapes,
UTF-8 replacement behavior, plus signs, blank/duplicate fields and secret masking
are preserved by differential checks, including 1,000 seeded mixed-encoding cases.
Twenty-eight targeted decoder/feature/ingest tests passed. No feature-schema or
input-size limit was changed. This is a maintained compatibility-sensitive helper;
future Python decoding changes require continued equivalence checks.

The isolated 2,000-call decoding comparison took 1.109 seconds for the standard
parser and 0.315 seconds for the candidate. This is not a socket-latency result.
The subsequent unchanged four-client socket workload **still failed overall**:
large-query worst-client p95 was 9.987 ms (ASGI online), 10.694 ms (ASGI refused),
14.819 ms (Waitress online) and 16.364 ms (Waitress refused). Normal profiles
passed. All expected online events arrived without seeded-secret occurrences;
offline losses were fully counted after shutdown. Uncontrolled host scheduling
means these two runs do not prove an exact causal reduction in socket tails.

The previous failure remains retained. New private report:
`outputs/sensor-concurrent-fastdecode-20261122.json`.
SHA256: `eb221ea45eded650009d6bf0e544d65f0c93bf74269efd5de56485b4ca3784f9`.
Further performance work and repeatable acceptance remain required. No installed
external sensor or published package was automatically updated by this experiment.

## Thread headroom and in-worker diagnostics

The harness now records configurable Waitress thread count (`--wsgi-threads`,
1–64, default four). Parameter validation and forwarding/reporting have fast
regressions; all four benchmark checks passed. ASGI-only runs no longer require
an unused Werkzeug import. These are measurement changes, not SDK changes.

An eight-thread/four-client Windows comparison retained the same 200 samples per
client, two profiles, real sender and latency gates. It **failed**: large-query
worst-client p95 was **16.618 ms online** and **19.637 ms refused**; ordinary-query
profiles passed. Both online delivery and offline loss accounting matched all
1,760 expected events. Increasing threads alone did not establish acceptance;
the four-thread recommendation has not been replaced by an eight-thread claim.
Private report: `outputs/sensor-concurrent-eight-threads-20261122.json`.
SHA256: `676c71e214bad4f1d686d27aaf7bfbe71d0e0661f17ac6ba8e63deadc1d2acf2`.

A separate instrumented four-thread Windows run timed `_record` during four-client
socket traffic (100 measured pairs plus 20 warmup pairs per client/profile).
Across 480 recordings per profile/case, large-query recording wall p95 was
**1.096 ms online** and **0.878 ms refused**. Added timing instrumentation and
warmup calls are included. Thread CPU medians/p95 were zero at this scale, so
those timer fields are not useful CPU evidence. This diagnostic shows a gap
between measured recording work and socket tails; it does not replace the
end-to-end overhead gate or identify a unique scheduling/network cause.
Private report: `outputs/sensor-record-diagnostic-20261122.json`.
SHA256: `a0e8206912340c3f89f3746de8caa921c7feb89ffb852a0dc416bb12c4a68244`.

## Linux ASGI concurrent comparison: also incomplete

The same SDK/harness sources ran inside a Linux Docker container with two CPUs,
512 MiB memory, read-only filesystem, temporary `/tmp`, and no external network
or published port. Four clients used loopback inside that container; this is not
a cross-container network benchmark. Python was 3.12.16. Only ASGI ran because
the cached image lacked the optional WSGI servers; no dependencies were fetched.

Normal-query worst-client p95 passed at **4.783 ms online / 4.785 ms refused**.
Large-query worst-client p95 **failed** at **14.159 ms / 16.329 ms**. All 1,760
online events arrived without seeded-secret occurrences; all refused-case events
were counted dropped after close. The two-CPU cap, shared Docker host and Python
version differ from Windows, so neither a Windows-only cause nor universal Linux
performance can be inferred. No smaller sample, pooled-only percentile or relaxed
threshold is substituted for this failure. The temporary container exited.
Private report: `outputs/sensor-concurrent-linux-asgi-20261122.json`.
SHA256: `37f3c325c596a2ebe1118ddf666e87bc9ddd78ef664eda57b10b6d8578b1ed74`.

Further controlled performance work remains required before claiming the
concurrent large-query latency target. Existing default thread count and installed
owner services were not changed by these comparisons.
