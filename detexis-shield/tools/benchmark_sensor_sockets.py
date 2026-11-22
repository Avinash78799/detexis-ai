"""Paired loopback TCP sensor cost with a real sender, online and offline.

Uses ephemeral loopback listeners only. Collector accepts synthetic telemetry;
it is not Shield ingest and does not exercise its database or worker pipeline.
"""
import argparse
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import platform
import socket
import statistics
import threading
import time

import httpx
import uvicorn
from detexis_shield import ShieldMiddleware, ShieldWSGIMiddleware

MEASUREMENT_VERSION = 2


def summary(values):
    ordered = sorted(values)
    return {"median_ms":statistics.median(values), "p95_ms":ordered[math.ceil(len(values)*.95)-1]}


@contextmanager
def collector(online):
    stats = {"events":0,"redaction_failures":0}
    lock = threading.Lock()
    if not online:
        # Reserve a port without listening: a refused connection, with no risk
        # of accidentally addressing another application's loopback service.
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            yield "http://127.0.0.1:"+str(reserved.getsockname()[1]), stats
        return

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(2)

        def reply(self, value, status=200):
            raw = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.reply({"honeytokens":[],"mode":"monitor"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 1024*1024:
                return self.reply({}, 413)
            rows = json.loads(self.rfile.read(length) or b"{}").get("events", [])
            with lock:
                stats["events"] += len(rows)
                stats["redaction_failures"] += sum("synthetic-secret" in row.get("query_redacted", "") for row in rows)
            self.reply({"accepted":len(rows)}, 202)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:"+str(server.server_port), stats
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@contextmanager
def host(framework, sensor, wsgi_server="werkzeug", wsgi_threads=4):
    if framework == "asgi":
        async def app(scope, receive, send):
            await send({"type":"http.response.start","status":200,"headers":[(b"content-length",b"2")]})
            await send({"type":"http.response.body","body":b"ok"})
        observed = sensor(app)
        async def dispatch(scope, receive, send):
            target = observed if scope["path"] == "/observed" else app
            await target(scope, receive, send)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(dispatch, lifespan="off", access_log=False, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets":[listener]}, daemon=True)
        thread.start()
        def stop():
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()
            if thread.is_alive():
                raise RuntimeError("Benchmark ASGI server did not stop")
    else:
        def app(environ, start_response):
            start_response("200 OK", [("Content-Length","2")])
            return [b"ok"]
        observed = sensor(app)
        def dispatch(environ, start_response):
            return (observed if environ["PATH_INFO"] == "/observed" else app)(environ, start_response)
        if wsgi_server == "waitress":
            from waitress import create_server
            server = create_server(dispatch, host="127.0.0.1", port=0, threads=wsgi_threads,
                                   map={}, asyncore_loop_timeout=.1)
            port = server.socket.getsockname()[1]
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            def stop():
                server.close()
                server.task_dispatcher.shutdown()
                for channel in list(server._map.values()):
                    channel.close()
                thread.join(timeout=5)
                if thread.is_alive():
                    raise RuntimeError("Benchmark WSGI server did not stop")
        else:
            from werkzeug.serving import make_server, WSGIRequestHandler
            class QuietHandler(WSGIRequestHandler):
                def log(self, *args, **kwargs):
                    pass
            server = make_server("127.0.0.1", 0, dispatch, threaded=True, request_handler=QuietHandler)
            port = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def stop():
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3, trust_env=False) as client:
            for _ in range(100):
                try:
                    if client.get("/plain").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(.02)
            else:
                raise RuntimeError("Benchmark host not ready")
        yield f"http://127.0.0.1:{port}", observed
    finally:
        stop()
        observed.client.close()


def paired_clients(origin, query, samples, concurrency):
    barrier = threading.Barrier(concurrency)
    def run_client(_):
        before, after, added = [], [], []
        with httpx.Client(base_url=origin, timeout=5, trust_env=False) as client:
            # URL parsing in the load generator is not host-side SDK work.
            # Prepare equivalent immutable GETs before timing or synchronization.
            requests = [client.build_request('GET', path+'?'+query) for path in ['/plain','/observed']]
            def request(prepared):
                started = time.perf_counter_ns()
                response = client.send(prepared)
                if response.status_code != 200 or response.content != b"ok":
                    raise RuntimeError("Host response changed")
                return (time.perf_counter_ns()-started)/1_000_000
            barrier.wait(timeout=10)
            for n in range(samples+20):
                order = [0,1] if n%2 == 0 else [1,0]
                pair = {i:request(requests[i]) for i in order}
                if n >= 20:
                    before.append(pair[0]); after.append(pair[1]); added.append(pair[1]-pair[0])
        return before, after, added
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        clients = list(pool.map(run_client, range(concurrency)))
    return clients


def measure(framework, online, samples, wsgi_server="werkzeug", concurrency=1, wsgi_threads=4):
    cls = ShieldMiddleware if framework == "asgi" else ShieldWSGIMiddleware
    profiles = {"normal":"q=notebook&password=synthetic-secret", "large":"q="+"%3C%3E%27%22"*512+"&password=synthetic-secret"}
    with collector(online) as (backend, counts):
        def wrap(app):
            return cls(app, backend, "synthetic-benchmark-key", "synthetic-benchmark-salt", flush_interval=.2)
        results = {}
        with host(framework, wrap, wsgi_server, wsgi_threads) as (origin, observed):
            for name, query in profiles.items():
                clients = paired_clients(origin, query, samples, concurrency)
                before, after, added = [[value for client in clients for value in client[i]] for i in range(3)]
                delta = summary(added)
                per_client = [summary(client[2]) for client in clients]
                results[name] = {"samples":samples*concurrency,"samples_per_client":samples,
                                 "baseline":summary(before),"with_sensor":summary(after),
                                 "paired_added_latency":delta,"per_client_added_latency":per_client,
                                 "target_passed":all(p["median_ms"] < 5 and p["p95_ms"] < 10 for p in [delta,*per_client])}
            expected = (samples+20)*len(profiles)*concurrency
            if online:
                deadline = time.monotonic()+5
                while counts["events"] < expected and time.monotonic() < deadline:
                    time.sleep(.05)
            sender = {"expected_synthetic_events":expected, **counts, "dropped_before_close":observed.client.dropped,
                      "buffered_before_close":observed.client.q.qsize()}
            if online and (counts["events"] != expected or counts["redaction_failures"]):
                raise RuntimeError("Online telemetry completion or redaction check failed")
        sender["dropped_after_close"] = observed.client.dropped
    return {"framework":framework,"host_server":"uvicorn" if framework == "asgi" else wsgi_server,
            "wsgi_threads":wsgi_threads if framework == "wsgi" and wsgi_server == "waitress" else None,
            "concurrent_clients":concurrency,"collector":"online" if online else "connection_refused", "profiles":results,"sender":sender}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=400)
    parser.add_argument("--concurrency", type=int, default=1, help="Independent paired clients; samples apply per client")
    parser.add_argument("--output", type=Path, default=Path("sensor-socket-benchmark.json"))
    parser.add_argument("--framework", choices=["both","asgi","wsgi"], default="both")
    parser.add_argument("--wsgi-server", choices=["werkzeug","waitress"], default="werkzeug")
    parser.add_argument("--wsgi-threads", type=int, default=4, help="Waitress worker threads; recorded in each Waitress case")
    args = parser.parse_args()
    if not 100 <= args.samples <= 1000:
        parser.error("samples must be between 100 and 1000")
    if not 1 <= args.concurrency <= 16:
        parser.error("concurrency must be between 1 and 16")
    if not 1 <= args.wsgi_threads <= 64:
        parser.error("wsgi-threads must be between 1 and 64")
    if args.output.exists():
        parser.error("Refusing to overwrite an existing report")
    frameworks = ("asgi","wsgi") if args.framework == "both" else (args.framework,)
    cases = [measure(framework, online, args.samples, args.wsgi_server, args.concurrency, args.wsgi_threads) for framework in frameworks for online in (True,False)]
    root = Path(__file__).resolve().parents[1]
    report = {"measurement_version":MEASUREMENT_VERSION,
              "request_preparation":"GET URLs/headers built once per client/path before timing; send through complete body read is timed",
              "checked_at":datetime.now(timezone.utc).isoformat(),"python":platform.python_version(),
              "source_sha256":{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(), *sorted((root/'sensor-sdk/detexis_shield').glob('*.py'))]},
              "cases":cases,"targets_passed":all(p["target_passed"] for c in cases for p in c["profiles"].values()),
              "scope":"Alternating loopback TCP pairs per independent client, one shared host process and real background sender. Clients start each profile together; shared-host contention can affect both paired paths. Aggregated and every-client latency gates apply. Server choice, Waitress thread count and concurrency are recorded. Synthetic collector only; no actual ingest/Redis/DB, remote TLS, production capacity or representative traffic claim. Offline telemetry loss is expected and counted."}
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    if not report["targets_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
