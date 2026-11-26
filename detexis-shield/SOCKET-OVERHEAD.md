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

## No-sensor calibration: do not attribute all socket tails to the SDK

The next diagnostic dispatched both `/plain` and `/observed` to the **identical
application with no sensor**, no sender and no collector. It retained four
Windows clients, 200 measured pairs, 20 warmup pairs, alternating order and the
same query profiles. Large-query worst-client p95 path differences were
**8.561 ms for ASGI** and **13.322 ms for four-thread Waitress**. Ordinary-query
differences were at most 0.894 and 2.065 ms respectively. With no sensor present,
these are benchmark/host/request-processing differences, not measured SDK cost.
Private report: `outputs/sensor-socket-zero-calibration-20261122.json`.
SHA256: `4462d2a6d263c204d65d09f50edb07b359b9da53e7504db57f21c8c99e99362d`.

The prior sensor runs still missed their numerical acceptance gates and remain
retained. However, a causal claim that the SDK itself added their full 14–28 ms
tails is unsupported by this calibration. The measured `_record` wall time is
separate diagnostic evidence, not a substitute passing result. Do not subtract
percentiles across runs or promote a near-threshold result as established
overhead acceptance. A stable measurement setup and repeated calibrated results
are still needed. No production performance guarantee is made.

The calibration is now reproducible with a dedicated tool. Its report explicitly
sets `sensor_acceptance` to null; exit zero means the diagnostic completed only.
It records both signed path deltas and absolute differences, rejects overwriting
reports, and uses bounded client/sample/thread settings:

```powershell
python tools/calibrate_sensor_sockets.py --framework both --samples 200 --concurrency 4 --output C:\PRIVATE\new-calibration.json
```

The reusable tool's separate four-client/four-thread Waitress verification also
completed, with large-query worst-client signed path-delta p95 **17.560 ms**.
Its `sensor_acceptance` remained null, sample totals were checked, and a repeat
command targeting the same file was refused without altering the report.
Private report: `outputs/sensor-calibration-tool-20261122.json`.
SHA256: `58aa6cf3480bc49c5bb9f16864fe18b6020e4e7207d9bbb2042b538d581a7d56`.

## Measurement version 2: prepared requests and repeated concurrent passes

The earlier timed `client.get(path)` also rebuilt/normalized the large URL in
the Python load generator on every call. Version 2 builds the same two bodyless
GET requests once per client **before timing and the start barrier**, then times
`client.send` through complete response-body read and content validation. It
still includes HTTP transport, host scheduling, middleware and shared-process
contention. It excludes load-generator URL/header construction. This is an
explicit measurement-interval change, not a relaxation of the 5/10-ms gates or
a like-for-like SDK speedup claim. Prior version-1 results remain retained.

Both benchmark and calibration reports record `measurement_version: 2` and the
request-preparation boundary. A regression verifies that construction occurs
only twice per client and outside every timed pair; all five benchmark checks
passed. Payloads, 20-pair warmup, alternating request order, four clients, 200
measured pairs per client, four Waitress threads, real sender and per-client
gates remain unchanged.

The matching no-sensor calibration's large-query worst-client p95 was **0.617 ms
ASGI / 1.593 ms Waitress**. Two subsequent sensor runs **passed all pooled and
every-client gates** for normal/large profiles and online/refused collectors.
Worst-client p95 across all cases was **2.888 ms** in the first and **3.245 ms**
in the repeat. Each online case received all 1,760 expected events with no seeded
secret occurrences or drops; each refused case counted all events as dropped
after sender shutdown. SDK and harness source hashes matched between repeats.

The complete aggregate reports and calibration are reviewable in
[concurrent-sensor-check.json](concurrent-sensor-check.json). Private raw runs:
`outputs/sensor-prepared-concurrent-20261122.json` (SHA256
`f4d71081f5b7f6c24f6bf05867259fc72a9247b118b9143e7b3dced03fc4385e`)
and `outputs/sensor-prepared-concurrent-repeat-20261122.json` (SHA256
`90f4ce6ebac2e6b038f74628d01db468dffb9607feabfb9094c7be45596ebd7d`).
Calibration SHA256:
`a6620c67bad6cc703a3d9b20292fa125b9510606936f5015185b391f91c0e82b`.

This provides calibrated concurrent Windows socket evidence for this synthetic
workload and measurement interval. It does not prove remote/TLS deployment,
arbitrary workload capacity, Linux version-2 behavior, long-lived operation or
absence of all performance faults. ASGI telemetry may still finish after the
client receives the response; delivery totals were checked separately. No real
application or installed sensor was automatically updated by these tests.

## SDK 0.1.1: loaded-package attestation and nested-field profile

23 November: the development benchmark environment was upgraded from the verified
0.1.1 wheel without dependency downloads. The harness now compares the **imported
SDK files** against the checkout before opening listeners and records their hashes
and installed distribution version. Earlier reports recorded checkout hashes;
those alone do not establish which package a Python process imported. Those
historical reports remain retained with their original scope.

An optional `--include-nested-profile` adds bracket/dotted secret fields while
preserving the original normal/large queries and measurement-version-2 timing
boundary. The no-sensor calibration uses the same profile selector. Eight harness
checks passed, including byte-level drift refusal, stopping before measurement,
per-client gate enforcement, unchanged original profiles and event accounting.

With four clients, 200 measured pairs per client/profile, 20 warmup pairs and four
Waitress threads, both SDK runs passed all pooled and every-client 5/10-ms gates
on ASGI and WSGI, with online and refused collectors. The first run's worst-client
median/p95 was **0.901/6.948 ms**; the repeat was **0.715/5.705 ms**. All three
profiles passed. Every online case received all **2,640** expected synthetic events
with zero seeded-secret occurrences and drops; refused cases counted all 2,640 as
dropped after shutdown. Loaded SDK version 0.1.1, all six package hashes and the
harness hashes matched across the two runs and the verified wheel.

The separate no-sensor calibration's worst client signed path-delta p95 was
**5.070 ms**. Its sensor acceptance is null. It is diagnostic noise evidence,
not a sensor pass or a quantity to subtract from the measured SDK percentiles.

Complete reports and original-file SHA256s are in `sdk-011-socket-check.json`.
Private raw files are `outputs/sdk-011-calibration-20261123.json`,
`outputs/sdk-011-concurrent-20261123.json` and
`outputs/sdk-011-concurrent-repeat-20261123.json`; console/stderr logs are retained.
These results cover synthetic Windows loopback with the stated interval only.
They do not establish remote/TLS latency, Linux behavior, representative traffic,
long-lived reliability, malware/ML quality or backend ingest capacity. The earlier
500-events/s backend experiment has not been repeated after the SDK upgrade.

Reproduce using the intended installed SDK and new output filenames:

```powershell
python tools/calibrate_sensor_sockets.py --framework both --samples 200 --concurrency 4 --include-nested-profile --output C:\PRIVATE\sdk011-calibration.json
python tools/benchmark_sensor_sockets.py --framework both --wsgi-server waitress --samples 200 --concurrency 4 --include-nested-profile --output C:\PRIVATE\sdk011-sockets.json
```

## SDK 0.1.2 in Linux Docker — 26 November 2026

The installed 0.1.2 wheel matched the SDK checkout byte-for-byte. Tests used
prepared-request timing, four concurrent clients, 200 measured pairs per
client/profile, 20 warmups, and the normal, large, and nested-secret profiles.
The container ran on WSL2 without external networking. The comparison used
Uvicorn for ASGI and Waitress 3.0.2 for WSGI.

| Server | Worst added p95, run 1 / run 2 | Profiles passing, run 1 / run 2 | No-sensor worst p95 |
| --- | ---: | ---: | ---: |
| Uvicorn ASGI | 4.594 / 7.725 ms | 6/6 / 6/6 | 2.474 ms |
| Waitress WSGI, four threads | 12.467 / 12.528 ms | 0/6 / 1/6 | 12.712 ms |
| Waitress WSGI, eight threads | 12.010 / 12.399 ms | 3/6 / 1/6 | 11.872 ms |

All client medians were below 5 ms. The unchanged p95 target is below 10 ms
for every client and the pooled result. ASGI passed both runs. Neither Waitress
configuration passed. Identical no-sensor paths also exceeded 10 ms under
Waitress, so these results do not isolate the source of its tail latency.
The calibration is a separate experiment and was not subtracted.

Each online case delivered all 2,640 expected events with no seeded-secret
leaks or drops. With the collector unreachable, host responses completed and
the sender accounted for discarded events at shutdown. The reports cover this
synthetic loopback workload. They do not measure the actual Shield backend,
TLS overhead, or the latency of a customer's application.

Raw run and calibration JSON are under `outputs/linux-sdk-012-b709b5c0` and
`outputs/linux-sdk-012-wsgi8-4baacf03` in the workspace. Use the commands above
with SDK 0.1.2 installed. For the eight-thread comparison, pass
`--framework wsgi --wsgi-threads 8` to both commands.

### Linux WSGI request-path profile

Two additional Linux Docker runs called the WSGI interface directly, including
iterable completion and close, with the same request profiles and four
concurrent clients. The SDK wheel again matched the checkout. These runs kept
the real background sender and measured paired differences in wall time and
request-thread CPU time separately.

| Collector | Worst added wall p95, run 1 / run 2 | Worst added thread CPU p95, run 1 / run 2 |
| --- | ---: | ---: |
| Online | 1.779 / 0.475 ms | 1.134 / 0.473 ms |
| Connection refused | 0.915 / 1.368 ms | 0.912 / 1.319 ms |

Both online cases delivered all 2,640 expected events with no seeded-secret
leaks or drops. Both offline cases completed host responses and accounted for
all 2,640 discarded events. The direct request path did not reproduce the
Waitress socket tail. Its report deliberately leaves socket acceptance unset.

```sh
python tools/profile_wsgi_sensor.py --output wsgi-profile.json
```

Raw reports are in `outputs/linux-sdk-wsgi-profile-160b876e`.
