"""Profile WSGI request execution and sender accounting without a host server."""

import argparse
import json
import platform
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from benchmark_sensor_sockets import collector, loaded_sdk_info, request_profiles, summary
from detexis_shield import ShieldWSGIMiddleware


def plain_app(_environ, start_response):
    start_response("200 OK", [("Content-Length", "2")])
    return [b"ok"]


def request(application, environ):
    status = []

    def start_response(value, _headers, _exc_info=None):
        status.append(value)

    wall_start = time.perf_counter_ns()
    cpu_start = time.thread_time_ns()
    response = application(environ, start_response)
    try:
        body = b"".join(response)
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()
    cpu = (time.thread_time_ns() - cpu_start) / 1_000_000
    wall = (time.perf_counter_ns() - wall_start) / 1_000_000
    if body != b"ok" or status != ["200 OK"]:
        raise RuntimeError("Unexpected WSGI response")
    return wall, cpu


def compare(sensor, query, samples, clients):
    barrier = threading.Barrier(clients)

    def client(_index):
        environ = {"PATH_INFO": "/fixture", "QUERY_STRING": query,
                   "REQUEST_METHOD": "GET", "REMOTE_ADDR": "192.0.2.20"}
        wall, cpu = [], []
        barrier.wait(timeout=10)
        for index in range(samples + 20):
            if index % 2:
                observed, plain = request(sensor, environ), request(plain_app, environ)
            else:
                plain, observed = request(plain_app, environ), request(sensor, environ)
            if index >= 20:
                wall.append(observed[0] - plain[0])
                cpu.append(observed[1] - plain[1])
        return {"wall_ms": summary(wall), "cpu_ms": summary(cpu)}

    with ThreadPoolExecutor(max_workers=clients) as executor:
        return list(executor.map(client, range(clients)))


def profile(samples, clients):
    profiles = request_profiles(include_nested=True)
    expected = (samples + 20) * clients * len(profiles)
    cases = []
    for online in (True, False):
        with collector(online) as (backend, counts):
            sensor = ShieldWSGIMiddleware(plain_app, backend, "synthetic-profile-key", "synthetic-profile-salt",
                                          flush_interval=.2)
            try:
                results = {name: compare(sensor, query, samples, clients) for name, query in profiles.items()}
                if online:
                    deadline = time.monotonic() + 10
                    while counts["events"] < expected and time.monotonic() < deadline:
                        time.sleep(.05)
            finally:
                sensor.client.close()
            dropped = sensor.client.dropped
        if counts["redaction_failures"] or counts["events"] != (expected if online else 0):
            raise RuntimeError("Unexpected delivery or redaction accounting")
        if dropped != (0 if online else expected):
            raise RuntimeError("Unexpected dropped-event accounting")
        cases.append({"collector": "online" if online else "connection_refused", "profiles": results,
                      "expected": expected, "delivered": counts["events"], "dropped": dropped})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if not 100 <= args.samples <= 1000 or not 1 <= args.concurrency <= 16:
        parser.error("Expected 100–1000 samples and 1–16 concurrent clients")
    if args.output.exists():
        parser.error("Refusing to overwrite an existing report")
    sdk = loaded_sdk_info(Path(__file__).resolve().parents[1])
    cases = profile(args.samples, args.concurrency)
    report = {"scope": "Direct WSGI calls through iterable close; real background sender; no host-server sockets",
              "socket_acceptance": None, "platform": platform.platform(), "sdk": sdk,
              "samples_per_client": args.samples, "clients": args.concurrency, "cases": cases}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)


if __name__ == "__main__":
    main()
