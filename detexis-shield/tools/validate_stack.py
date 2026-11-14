"""Local-only validation against the dedicated detexis-shield-validation project."""
import argparse
import os
import asyncio
import importlib.util
import json
import math
import hashlib
import re
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT = os.getenv("SHIELD_VALIDATION_PROJECT", "detexis-shield-validation")
if not re.fullmatch(r"detexis-shield-validation(?:-[a-z0-9]+)?", PROJECT):
    raise ValueError("Use a dedicated detexis-shield-validation project")
BASE_URL = os.getenv("SHIELD_VALIDATION_URL", "http://127.0.0.1:8000").rstrip("/")
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", str(ROOT / "docker-compose.yml")]
if os.getenv("SHIELD_VALIDATION_COMPOSE"):
    COMPOSE += ["-f", str(Path(os.environ["SHIELD_VALIDATION_COMPOSE"]).resolve())]


def docker(*args):
    result = subprocess.run([*COMPOSE, *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def write_report(target, report):
    """Replace a snapshot atomically so interruptions cannot truncate the prior one."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=target.name, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_target():
    parsed = urlsplit(BASE_URL)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("Validation URL must be a plain HTTP loopback origin")
    expected = "127.0.0.1:" + str(parsed.port or 80)
    if docker("port", "api", "8000").strip() != expected:
        raise ValueError("Validation API port does not match the dedicated Compose project")


def ready():
    for _ in range(90):
        try:
            if httpx.get(BASE_URL + "/ready", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("API not ready")


def runtime_details():
    source = """
import hashlib,json,os,platform
from pathlib import Path
from importlib.metadata import version
from sqlalchemy import text
from app.db import SessionLocal
from app.redis_store import get_redis
from app import worker
from app.rule_manifest import manifest
with SessionLocal() as db:
    database=db.execute(text("SELECT current_setting('server_version')")).scalar()
    migration=db.execute(text('SELECT version_num FROM alembic_version')).scalar()
    settings={name:db.execute(text('SELECT current_setting(:name)'),{'name':name}).scalar()
              for name in ['shared_buffers','wal_compression','bgwriter_lru_maxpages','checkpoint_timeout','fsync','synchronous_commit']}
print(json.dumps({'python':platform.python_version(),'visible_cpus':os.cpu_count(),
    'packages':{name:version(name) for name in ['fastapi','uvicorn','starlette','pydantic','httpx','sqlalchemy','rq','psycopg2-binary']},
    'postgresql':database,'redis':get_redis().info('server')['redis_version'],
    'postgresql_settings':settings,
    'migration':migration,'model_enabled':bool(os.getenv('SHIELD_MODEL_DIR')),
    'detection_release':manifest(),
    'worker_source_sha256':hashlib.sha256(Path(worker.__file__).read_bytes()).hexdigest()}))
"""
    return json.loads(docker("exec", "-T", "worker", "python", "-c", source))


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
    parser.add_argument("--profile", choices=["uniform", "mixed", "mixed_comments"], default="uniform")
    parser.add_argument("--max-processing-p95-seconds", type=float, default=10,
                        help="Local rules-only processing-lag release target (default: 10 seconds)")
    parser.add_argument("--output", type=Path, default=Path("load-test-results.json"))
    args = parser.parse_args()
    if args.rate <= 0 or args.seconds <= 0:
        parser.error("rate and seconds must be positive")
    if not math.isfinite(args.max_processing_p95_seconds) or args.max_processing_p95_seconds <= 0:
        parser.error("max processing p95 must be finite and positive")
    validate_target()
    ready()
    runtime = runtime_details()
    expected_hash = hashlib.sha256((ROOT / "backend/app/rules.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    release = runtime["detection_release"]
    if not release["release_record_verified"] or release["rules_source_sha256"] != expected_hash:
        raise RuntimeError("Running detector differs from the checkout or its release record")
    api_hash = docker("exec", "-T", "api", "python", "-c",
                      "from app.rule_manifest import RULES_SHA256;print(RULES_SHA256)").strip()
    if api_hash != expected_hash:
        raise RuntimeError("API and worker detector sources differ")
    # Pending rows can be zero while duplicate recovery jobs remain in RQ.
    # A new measurement must not include work left over from an earlier run.
    queue_source = "from rq import Queue; from app.redis_store import get_redis; print(Queue('shield',connection=get_redis()).count)"
    if int(docker("exec", "-T", "api", "python", "-c", queue_source).strip()):
        raise RuntimeError("Wait for the previous validation queue to drain before starting another run")
    created = docker("exec", "-T", "api", "python", "create_site.py", "validation.example")
    key = re.search(r"dxs_[A-Za-z0-9_-]+", created).group()
    site_id = re.search(r"site_id=([a-f0-9-]+)", created).group(1)
    headers = {"X-API-Key": key}
    events = [{"event_id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc).isoformat(),
               "ip_hash": "b" * 64, "method": "GET", "path": path, "status": 200,
               "latency_ms": 1, "query_redacted": query}
              for path, query in [("/home", ""), ("/.env", ""), ("/search", "q=union+select+name")]]
    with httpx.Client(timeout=10, trust_env=False) as http:
        response = http.post(BASE_URL + "/v1/events", headers=headers, json={"events": events})
        assert response.status_code == 202, response.text
        assert response.json()["accepted"] == 3
        assert http.post(BASE_URL + "/v1/events", headers=headers, json={"events": events}).json()["accepted"] == 0
        for _ in range(30):
            incidents = http.get(BASE_URL + "/v1/incidents", headers=headers).json()
            if incidents:
                break
            time.sleep(1)
        assert incidents, "worker did not create an incident"
        assert http.get(BASE_URL + "/dashboard", auth=("site", key)).status_code == 200
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
        sensor = ShieldMiddleware(app, BASE_URL, key, "local-validation-salt")
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
    checkpoint = {"state": "running", "started_at": datetime.now(timezone.utc).isoformat(),
                  "site_id": site_id, "profile": args.profile, "target_rate": args.rate,
                  "duration_seconds": args.seconds, "runtime_details": runtime,
                  "note": "Incomplete checkpoint, not an acceptance result or proof the process is live."}
    write_report(args.output, checkpoint)
    async def measured_load():
        samples = []
        async def monitor():
            while True:
                await asyncio.sleep(60)
                sample = await asyncio.to_thread(counters, site_id)
                samples.append(sample)
                write_report(args.output, {**checkpoint, "updated_at": datetime.now(timezone.utc).isoformat(),
                                          "backlog_samples_each_minute": list(samples)})
                print(f"Load progress: {sample['total']} received, {sample['pending']} pending", flush=True)
        task = asyncio.create_task(monitor())
        try:
            report = await load.run(BASE_URL, key, args.rate, args.seconds, args.profile)
            report["backlog_samples_each_minute"] = samples
            return report
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    report = asyncio.run(measured_load())
    report["state"] = "draining"
    report["site_id"] = site_id
    report["runtime_details"] = runtime
    write_report(args.output, report)
    complete_measurement(args, report, site_id)


def complete_measurement(args, report, site_id):
    """Read-only completion of a persisted draining checkpoint; never repeats load."""
    expected_hash = report["runtime_details"]["detection_release"]["rules_source_sha256"]
    report["database_at_load_end"] = counters(site_id)
    start = time.monotonic()
    final = report["database_at_load_end"]
    while final["pending"] and time.monotonic() - start < 120:
        time.sleep(2)
        final = counters(site_id)
    report["database_after_drain"] = final
    report["processing_drain_seconds"] = time.monotonic() - start
    report["processing"] = processing_metrics(site_id)
    evidence_source = """
import sys,json
from sqlalchemy import text
from app.db import SessionLocal
with SessionLocal() as db:
    row=db.execute(text("SELECT count(*) FILTER (WHERE features->>'rules_source_sha256' = :fingerprint), count(*) FILTER (WHERE findings::jsonb @> CAST(:finding AS jsonb)) FROM events WHERE site_id=:site AND processed_at IS NOT NULL"), {'site':sys.argv[1],'fingerprint':sys.argv[2], 'finding':json.dumps([{'rule_id':'sqli_union'}])}).one()
    print(json.dumps({'matching_release_events':row[0], 'sqli_union_events':row[1]}))
"""
    report["rules_evidence"] = json.loads(docker("exec", "-T", "api", "python", "-c", evidence_source, site_id, expected_hash))
    rules_ok = report["rules_evidence"]["matching_release_events"] == final["total"]
    if args.profile in {"mixed", "mixed_comments"}:
        rules_ok = rules_ok and report["rules_evidence"]["sqli_union_events"] == args.rate * args.seconds // 10 + 1
    report["rules_evidence_passed"] = rules_ok
    report["functional_checks"] = {"ingest_idempotency": True, "rq_incident": True, "dashboard_auth": True, "real_backend_outage_fail_open": True}
    report["environment"] = "Dedicated local Docker validation stack; see runtime_details"
    report["project"] = PROJECT
    report["api_origin"] = BASE_URL
    report["compose_override"] = bool(os.getenv("SHIELD_VALIDATION_COMPOSE"))
    report["capacity_passed"] = report["accepted"] == args.rate * args.seconds and report["failed"] == 0 and final["pending"] == 0 and final["total"] == args.rate * args.seconds + 3 and report["processing"]["failed_jobs"] == 0 and report["processing"]["queued_jobs"] == 0 and report["elapsed_seconds"] <= args.seconds * 1.05
    report["max_processing_p95_seconds"] = args.max_processing_p95_seconds
    lag = report["processing"]["lag_p95_seconds"]
    report["latency_target_passed"] = lag is not None and lag <= args.max_processing_p95_seconds
    report["acceptance_passed"] = report["capacity_passed"] and report["latency_target_passed"] and report["rules_evidence_passed"]
    report["state"] = "completed"
    write_report(args.output, report)
    print(json.dumps(report, indent=2), flush=True)
    if not report["acceptance_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
