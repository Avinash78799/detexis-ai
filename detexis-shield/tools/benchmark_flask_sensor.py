"""Paired in-process Flask overhead; backend deliberately unavailable on loopback.

Run with Flask and the SDK installed. This measures test-client response-body
completion, not production sockets, concurrency or telemetry delivery reliability.
"""
import argparse
import hashlib
import inspect
import json
import math
import statistics
import time
from importlib.metadata import version
from pathlib import Path

from flask import Flask
from detexis_shield import ShieldWSGIMiddleware


def summary(values):
    ordered = sorted(values)
    return {"median_ms": statistics.median(values), "p95_ms": ordered[math.ceil(len(values) * .95) - 1]}


def application(name):
    app = Flask(name)

    @app.get("/")
    def home():
        return {"ok": True}

    return app


def measure(samples=1000):
    if not 100 <= samples <= 2000:
        raise ValueError("use 100 to 2000 samples to stay below the sender's 5000-event buffer")
    baseline = application("baseline")
    observed = application("observed")
    sensor = ShieldWSGIMiddleware(observed.wsgi_app, "http://127.0.0.1:9",
                                  "synthetic-benchmark-key", "synthetic-benchmark-salt")
    observed.wsgi_app = sensor
    results = {}

    def request(client, path):
        started = time.perf_counter()
        response = client.get(path)
        try:
            assert response.status_code == 200 and response.get_json() == {"ok": True}
        finally:
            response.close()  # Includes WSGI telemetry completion.
        return (time.perf_counter() - started) * 1000

    try:
        plain, monitored = baseline.test_client(), observed.test_client()
        for name, path in [("normal_query", "/?q=notebook&page=1"),
                           ("large_query", "/?q=" + "%3C%3E%27%22" * 512)]:
            for _ in range(100):
                request(plain, path)
                request(monitored, path)
            before, after, differences = [], [], []
            for index in range(samples):
                if index % 2:
                    added = request(monitored, path)
                    original = request(plain, path)
                else:
                    original = request(plain, path)
                    added = request(monitored, path)
                before.append(original)
                after.append(added)
                differences.append(added - original)
            overhead = summary(differences)
            results[name] = {"samples": samples, "baseline": summary(before),
                             "with_sensor": summary(after), "paired_added_latency": overhead,
                             "target_passed": overhead["median_ms"] < 5 and overhead["p95_ms"] < 10}
    finally:
        sensor.client.close()
    return {"scope": "paired Flask test-client; real sender; unavailable loopback backend; no production sockets",
            "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "wsgi_source_sha256": hashlib.sha256(Path(inspect.getfile(ShieldWSGIMiddleware)).read_bytes()).hexdigest(),
            "versions": {name: version(name) for name in ("Flask", "Werkzeug", "httpx", "detexis-shield")},
            "warmups_per_profile": 100, "profiles": results,
            "acceptance_passed": all(row["target_passed"] for row in results.values()),
            "note": "Paired differences are not clamped; negative samples remain. All responses completed; telemetry may drop by design."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(args.samples)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["acceptance_passed"] else 1)
