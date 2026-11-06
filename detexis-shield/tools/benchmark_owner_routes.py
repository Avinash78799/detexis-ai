"""Run inside the API container against a development database, never production.

Creates one synthetic account/site and retains its fixture for inspection. No
network requests, scanning, external alerts, or credential output. Measures ASGI
application + real database/Redis latency, excluding TLS/network/browser costs.
Usage: PYTHONPATH=/srv python /tmp/benchmark_owner_routes.py
"""
import asyncio
import json
import math
import secrets
import statistics
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import insert

from app.db import SessionLocal
from app.main import app
from app.models import Event, Incident


def checked(response, status=200):
    if response.status_code != status:
        # Never include a response body: registration returns recovery secrets.
        raise RuntimeError(f"Unexpected HTTP {response.status_code}, expected {status}")
    return response


async def main():
    stamp = datetime.now(timezone.utc)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="https://benchmark.example") as client:
        response = checked(await client.post("/app/api/register", headers={"Origin": str(client.base_url).rstrip("/")},
            json={"email": f"routes-{uuid.uuid4().hex}@example.test", "password": secrets.token_urlsafe(32)}), 201)
        headers = {"Origin": str(client.base_url).rstrip("/"), "X-CSRF-Token": response.json()["csrf_token"]}
        site = checked(await client.post("/app/api/sites", headers=headers,
                                        json={"domain": "route-benchmark.example"}), 201).json()["id"]
        with SessionLocal() as db:
            for start in range(0, 10000, 1000):
                db.execute(insert(Event), [{"event_id": str(uuid.uuid4()), "site_id": site,
                    "ts": stamp, "received_at": stamp + timedelta(microseconds=i),
                    "processed_at": stamp + timedelta(seconds=1), "ip_hash": "a" * 64,
                    "method": "GET", "path": f"/synthetic/{i % 100}", "status": 200,
                    "latency_ms": 1.0} for i in range(start, start + 1000)])
            for i in range(100):
                db.add(Incident(site_id=site, ip_hash=f"{i:064x}", bucket=i, severity="low",
                                rules=["synthetic"], correlations=[], first_seen=stamp, last_seen=stamp))
            db.commit()
        routes = ["/app", "/app/api/session", "/app/api/sites", "/app/api/inbox",
                  f"/app/api/sites/{site}/connection", f"/app/sites/{site}", f"/app/sites/{site}/feed"]
        results = []
        for path in routes:
            for _ in range(5):
                checked(await client.get(path))
            samples = []
            for _ in range(100):
                begin = time.perf_counter()
                checked(await client.get(path))
                samples.append((time.perf_counter() - begin) * 1000)
            results.append({"route": path.replace(site, "{site_id}"), "samples": len(samples),
                            "median_ms": round(statistics.median(samples), 3),
                            "p95_ms": round(sorted(samples)[math.ceil(len(samples) * .95) - 1], 3)})
        print(json.dumps({"at": stamp.isoformat(), "scope": "sequential warm ASGI application; real PostgreSQL/Redis; no network/TLS/browser",
                          "fixture_site": site, "events": 10000, "incidents": 100,
                          "warmups_per_route": 5, "results": results}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
