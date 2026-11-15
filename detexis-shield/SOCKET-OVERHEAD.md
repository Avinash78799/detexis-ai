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
