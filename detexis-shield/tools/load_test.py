"""Authorized loopback/staging ingestion benchmark; defaults to 500 events/s for 10m."""
import argparse
import asyncio
import json
import os
import statistics
import time
import uuid
from datetime import datetime, timezone

import httpx


def event(index, profile="uniform"):
    row = {"event_id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc).isoformat(),
           "ip_hash": "a" * 64, "method": "GET", "path": "/benchmark", "status": 200, "latency_ms": 1}
    if profile == "mixed":
        # 80% benign-shaped, 10% honeytoken, 10% SQLi-shaped; 128 clients.
        row["ip_hash"] = f"{(index // 10) % 128:064x}"
        kind = index % 10
        row["path"] = ["/", "/products", "/search", "/docs", "/cart", "/account", "/api/items", "/health", "/.env", "/search"][kind]
        row["status"] = 404 if kind == 8 else 200
        row["query_redacted"] = "q=union+select+name+from+users" if kind == 9 else "q=notebook&page=1" if kind == 2 else ""
    elif profile != "uniform":
        raise ValueError("unknown workload profile")
    return row


async def run(url, key, rate, seconds, profile="uniform"):
    if rate <= 0 or seconds <= 0:
        raise ValueError("rate and duration must be positive")
    batch_size = min(100, rate)
    interval = batch_size / rate
    attempts, accepted, failed, latency = 0, 0, 0, []
    responses, transport_errors = {}, {}
    semaphore = asyncio.Semaphore(20)
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        async def send(count, offset):
            nonlocal attempts, accepted, failed
            body = [event(offset + i, profile) for i in range(count)]
            started = time.perf_counter()
            try:
                response = await http.post(url + "/v1/events", headers={"X-API-Key": key}, json={"events": body})
                code = str(response.status_code)
                responses[code] = responses.get(code, 0) + 1
                attempts += count
                if response.status_code == 202:
                    accepted += response.json()["accepted"]
                else:
                    failed += count
            except httpx.HTTPError as exc:
                name = type(exc).__name__
                transport_errors[name] = transport_errors.get(name, 0) + 1
                attempts += count
                failed += count
            finally:
                latency.append((time.perf_counter() - started) * 1000)
                semaphore.release()
        started = time.monotonic()
        target = rate * seconds
        scheduled = 0
        jobs = []
        while scheduled < target:
            deadline = started + scheduled / rate
            await asyncio.sleep(max(0, deadline - time.monotonic()))
            await semaphore.acquire()
            count = min(batch_size, target - scheduled)
            jobs.append(asyncio.create_task(send(count, scheduled)))
            scheduled += count
        await asyncio.gather(*jobs)
        elapsed = time.monotonic() - started
    return {"profile": profile, "target_rate": rate, "duration_seconds": seconds, "events": attempts, "accepted": accepted,
            "failed": failed, "elapsed_seconds": elapsed, "accepted_per_second": accepted / elapsed,
            "batch_latency_median_ms": statistics.median(latency),
            "batch_latency_p95_ms": sorted(latency)[max(0, int(len(latency)*.95)-1)],
            "http_responses": responses, "transport_errors": transport_errors,
            "note": "Ingest acceptance only. Check pending events, RQ failures and processing lag separately."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--rate", type=int, default=500)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--profile", choices=["uniform", "mixed"], default="uniform")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.url.rstrip("/"), os.environ["SHIELD_API_KEY"], args.rate, args.seconds, args.profile)), indent=2))
