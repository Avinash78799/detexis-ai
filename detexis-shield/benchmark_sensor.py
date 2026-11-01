"""In-process ASGI overhead benchmark; no live backend or network required."""
import asyncio
import json
import platform
import statistics
import sys
import time
from unittest.mock import patch

import httpx

sys.path.insert(0, "sensor-sdk")
from detexis_shield import ShieldMiddleware


async def app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200})
    await send({"type": "http.response.body", "body": b"ok"})


async def send(message):
    pass


SCOPE = {"type": "http", "method": "GET", "path": "/search",
         "query_string": b"q=hello&password=secret", "client": ("192.0.2.1", 1234),
         "headers": [(b"user-agent", b"benchmark")]}


async def measure(target, count):
    samples = []
    for _ in range(count):
        start = time.perf_counter_ns()
        await target(SCOPE, None, send)
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return samples


def stats(samples):
    return {"median_ms": round(statistics.median(samples), 6),
            "p95_ms": round(sorted(samples)[int(len(samples) * .95) - 1], 6)}


async def main():
    count = 10000
    original_client = httpx.Client

    def offline(request):
        raise httpx.ConnectError("simulated backend outage", request=request)

    # Only the network is simulated. The actual queue and sender thread run.
    with patch("detexis_shield.client.httpx.Client",
               side_effect=lambda **kw: original_client(transport=httpx.MockTransport(offline), **kw)):
        sensor = ShieldMiddleware(app, "http://backend.invalid", "benchmark-key", "benchmark-salt")
        try:
            await measure(app, 500)
            await measure(sensor, 500)
            baseline, instrumented, differences = [], [], []
            for index in range(count):
                # Alternate order to reduce systematic warmup/order bias.
                if index % 2:
                    b = (await measure(sensor, 1))[0]
                    a = (await measure(app, 1))[0]
                else:
                    a = (await measure(app, 1))[0]
                    b = (await measure(sensor, 1))[0]
                baseline.append(a)
                instrumented.append(b)
                differences.append(b - a)
            overhead = stats(differences)
            report = {"python": platform.python_version(), "platform": platform.platform(),
                      "requests_per_variant": count, "backend": "simulated connection failure",
                      "baseline": stats(baseline), "sensor": stats(instrumented),
                      "paired_overhead": overhead,
                      "passes_target": overhead["median_ms"] < 5 and overhead["p95_ms"] < 10,
                      "dropped_snapshot": sensor.client.dropped,
                      "queued_snapshot": sensor.client.q.qsize(),
                      "limits": "In-process ASGI microbenchmark; no socket/server/load or Flask measurement."}
            print(json.dumps(report, indent=2))
        finally:
            sensor.client.close()


if __name__ == "__main__":
    asyncio.run(main())
