"""Linux Gunicorn loopback comparison using the existing SDK socket test."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from benchmark_sensor_sockets import collector, loaded_sdk_info, paired_clients, request_profiles, summary
from detexis_shield import ShieldWSGIMiddleware
from profile_wsgi_sensor import plain_app


sensor = None
REQUEST_LINE_LIMIT = 8190  # Synthetic long-query comparison only.


def application():
    """Gunicorn calls the factory in its worker, after fork."""
    global sensor
    backend = os.getenv("BENCHMARK_COLLECTOR")
    if backend:
        sensor = ShieldWSGIMiddleware(plain_app, backend, "synthetic-gunicorn-key",
                                      "synthetic-gunicorn-salt", flush_interval=.2)

    def route(environ, start_response):
        target = sensor if sensor is not None and environ["PATH_INFO"] == "/observed" else plain_app
        return target(environ, start_response)

    return route


def worker_exit(_server, _worker):
    if sensor is not None:
        sensor.client.close()
        Path(os.environ["BENCHMARK_WORKER_REPORT"]).write_text(str(sensor.client.dropped), encoding="ascii")


def run_profiles(backend, counts, samples, clients, threads):
    with TemporaryDirectory(prefix="shield-gunicorn-") as temporary, socket.socket() as listener:
        worker_report = Path(temporary) / "dropped.txt"
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        environment = dict(os.environ)
        for name in ("GUNICORN_CMD_ARGS", "BENCHMARK_COLLECTOR", "BENCHMARK_WORKER_REPORT"):
            environment.pop(name, None)
        if backend is not None:
            environment.update(BENCHMARK_COLLECTOR=backend, BENCHMARK_WORKER_REPORT=str(worker_report))
        process = subprocess.Popen([
            sys.executable, "-m", "gunicorn", "--config", "python:benchmark_gunicorn_sensor",
            "--bind", f"fd://{listener.fileno()}", "--workers", "1", "--worker-class", "gthread",
            "--threads", str(threads), "--limit-request-line", str(REQUEST_LINE_LIMIT),
            "--log-level", "warning", "benchmark_gunicorn_sensor:application()",
        ], cwd=Path(__file__).resolve().parent, env=environment, pass_fds=(listener.fileno(),))
        listener.close()
        try:
            with httpx.Client(base_url=origin, trust_env=False, timeout=1) as http:
                for _ in range(30):
                    if process.poll() is not None:
                        raise RuntimeError("Gunicorn worker exited before the test")
                    try:
                        if http.get("/plain").status_code == 200:
                            break
                    except httpx.TransportError:
                        time.sleep(.1)
                else:
                    raise RuntimeError("Gunicorn benchmark did not become ready")

            results = {}
            for name, query in request_profiles(include_nested=True).items():
                pairs = paired_clients(origin, query, samples, clients)
                per_client = [summary(client[2]) for client in pairs]
                pooled = summary([sample for client in pairs for sample in client[2]])
                passed = all(item["median_ms"] < 5 and item["p95_ms"] < 10 for item in [pooled, *per_client])
                results[name] = {"per_client": per_client, "pooled": pooled,
                                 "target_passed": passed if backend is not None else None}
            expected = (samples + 20) * clients * len(results)
            if counts is not None and counts["online"]:
                deadline = time.monotonic() + 10
                while counts["events"] < expected and time.monotonic() < deadline:
                    time.sleep(.05)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise RuntimeError("Gunicorn did not stop cleanly") from None
        if backend is None:
            return {"collector": "no_sensor_calibration", "profiles": results}
        dropped = int(worker_report.read_text(encoding="ascii"))
        delivered = counts["events"]
        if counts["redaction_failures"] or delivered != (expected if counts["online"] else 0):
            raise RuntimeError("Unexpected delivery or redaction accounting")
        if dropped != expected - delivered:
            raise RuntimeError("Unexpected drop accounting")
        return {"collector": "online" if counts["online"] else "connection_refused", "profiles": results,
                "expected": expected, "delivered": delivered, "dropped": dropped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=200)
    args = parser.parse_args()
    if not 100 <= args.samples <= 1000 or args.output.exists():
        parser.error("Use 100–1000 samples and a new report path")
    sdk = loaded_sdk_info(Path(__file__).resolve().parents[1])
    cases = [run_profiles(None, None, args.samples, 4, 4)]
    for online in (True, False):
        with collector(online) as (url, counts):
            counts["online"] = online
            cases.append(run_profiles(url, counts, args.samples, 4, 4))
    report = {"scope": "Synthetic loopback, one Gunicorn gthread worker, four threads and four clients",
              "sdk": sdk, "gunicorn": version("gunicorn"), "request_line_limit": REQUEST_LINE_LIMIT,
              "samples_per_client": args.samples, "cases": cases}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    raise SystemExit(0 if all(p["target_passed"] for case in cases[1:] for p in case["profiles"].values()) else 1)


if __name__ == "__main__":
    main()
