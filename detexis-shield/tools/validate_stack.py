"""Local-only validation against the dedicated detexis-shield-validation project."""
import argparse
import os
import asyncio
import importlib.util
import json
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-p", "detexis-shield-validation", "-f", str(ROOT / "docker-compose.yml")]
if os.getenv("SHIELD_VALIDATION_COMPOSE"):
    COMPOSE += ["-f", str(Path(os.environ["SHIELD_VALIDATION_COMPOSE"]).resolve())]


def docker(*args):
    result = subprocess.run([*COMPOSE, *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def ready():
    for _ in range(90):
        try:
            if httpx.get("http://127.0.0.1:8000/ready", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("API not ready")


def counters(site_id):
    uuid.UUID(site_id)
    source = """
import sys,json
from sqlalchemy import select,func
from app.db import SessionLocal
from app.models import Event
with SessionLocal() as db:
    total=db.scalar(select(func.count()).select_from(Event).where(Event.site_id==sys.argv[1]))
    pending=db.scalar(select(func.count()).select_from(Event).where(Event.site_id==sys.argv[1],Event.processed_at.is_(None)))
    print(json.dumps({'total':total,'pending':pending}))
"""
    return json.loads(docker("exec", "-T", "api", "python", "-c", source, site_id))


def processing_metrics(site_id):
    uuid.UUID(site_id)
    source = """
import sys,json
from sqlalchemy import text
from app.db import SessionLocal
from app.redis_store import get_redis
from rq import Queue
from rq.registry import FailedJobRegistry
with SessionLocal() as db:
    row=db.execute(text('SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch from (processed_at-received_at))), percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch from (processed_at-received_at))) FROM events WHERE site_id=:site AND processed_at IS NOT NULL'), {'site':sys.argv[1]}).one()
    connection=get_redis()
    print(json.dumps({'lag_median_seconds':row[0], 'lag_p95_seconds':row[1], 'failed_jobs':FailedJobRegistry('shield',connection=connection).count, 'queued_jobs':Queue('shield',connection=connection).count}))
"""
    return json.loads(docker("exec", "-T", "api", "python", "-c", source, site_id))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rate", type=int, default=500)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--output", type=Path, default=Path("load-test-results.json"))
    args = parser.parse_args()
    if args.rate <= 0 or args.seconds <= 0:
        parser.error("rate and seconds must be positive")
    ready()
    created = docker("exec", "-T", "api", "python", "create_site.py", "validation.example")
    key = re.search(r"dxs_[A-Za-z0-9_-]+", created).group()
    site_id = re.search(r"site_id=([a-f0-9-]+)", created).group(1)
    headers = {"X-API-Key": key}
    events = [{"event_id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc).isoformat(),
               "ip_hash": "b" * 64, "method": "GET", "path": path, "status": 200,
               "latency_ms": 1, "query_redacted": query}
              for path, query in [("/home", ""), ("/.env", ""), ("/search", "q=union+select+name")]]
    with httpx.Client(timeout=10, trust_env=False) as http:
        response = http.post("http://127.0.0.1:8000/v1/events", headers=headers, json={"events": events})
        assert response.status_code == 202, response.text
        assert response.json()["accepted"] == 3
        assert http.post("http://127.0.0.1:8000/v1/events", headers=headers, json={"events": events}).json()["accepted"] == 0
        for _ in range(30):
            incidents = http.get("http://127.0.0.1:8000/v1/incidents", headers=headers).json()
            if incidents:
                break
            time.sleep(1)
        assert incidents, "worker did not create an incident"
        assert http.get("http://127.0.0.1:8000/dashboard", auth=("site", key)).status_code == 200
    print("Full-stack ingest, idempotency, RQ incident and authenticated dashboard passed", flush=True)
    docker("stop", "api")
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from detexis_shield import ShieldMiddleware
        app = FastAPI()
        @app.get("/")
        def home():
            return {"ok": True}
        sensor = ShieldMiddleware(app, "http://127.0.0.1:8000", key, "local-validation-salt")
        try:
            with TestClient(sensor) as client:
                assert client.get("/").status_code == 200
        finally:
            sensor.client.close()
    finally:
        docker("start", "api")
    ready()
    print("Host response survived a real backend outage", flush=True)
    spec = importlib.util.spec_from_file_location("load_test", ROOT / "tools/load_test.py")
    load = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(load)
    print(f"Starting {args.rate} events/second for {args.seconds} seconds", flush=True)
    async def measured_load():
        samples = []
        async def monitor():
            while True:
                await asyncio.sleep(60)
                sample = await asyncio.to_thread(counters, site_id)
                samples.append(sample)
                print(f"Load progress: {sample['total']} received, {sample['pending']} pending", flush=True)
        task = asyncio.create_task(monitor())
        try:
            report = await load.run("http://127.0.0.1:8000", key, args.rate, args.seconds)
            report["backlog_samples_each_minute"] = samples
            return report
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    report = asyncio.run(measured_load())
    report["database_at_load_end"] = counters(site_id)
    start = time.monotonic()
    final = report["database_at_load_end"]
    while final["pending"] and time.monotonic() - start < 120:
        time.sleep(2)
        final = counters(site_id)
    report["database_after_drain"] = final
    report["processing_drain_seconds"] = time.monotonic() - start
    report["processing"] = processing_metrics(site_id)
    report["functional_checks"] = {"ingest_idempotency": True, "rq_incident": True, "dashboard_auth": True, "real_backend_outage_fail_open": True}
    report["environment"] = "Local Docker Desktop, PostgreSQL 16, Redis 7, one RQ worker, rules only"
    report["compose_override"] = bool(os.getenv("SHIELD_VALIDATION_COMPOSE"))
    report["acceptance_passed"] = report["accepted"] == args.rate * args.seconds and report["failed"] == 0 and final["pending"] == 0 and report["processing"]["failed_jobs"] == 0 and report["elapsed_seconds"] <= args.seconds * 1.05
    target = args.output
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if not report["acceptance_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
