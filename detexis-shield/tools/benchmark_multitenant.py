"""Synthetic concurrent HTTPS ingest/owner reads on a fresh shield-perf-* project.

Never targets computer hosting or an arbitrary URL. No scans, uploads, external
alerts or browser automation. Credentials exist in memory only. Checkpoints and
failures are retained in the report; this is not a browser or classifier benchmark.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import secrets
import ssl
import statistics
import subprocess
import threading
import time
import uuid

import httpx

from load_test import event

ORIGIN = "https://localhost:18443"


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Docker inspection failed; no credentials or response bodies are printed")
    return result.stdout.strip()


def checked(response, expected=200):
    if response.status_code != expected:
        raise RuntimeError(f"Expected HTTP {expected}; received {response.status_code}")
    return response


def summary(values):
    return {"samples": len(values), "median_ms": statistics.median(values) if values else None,
            "p95_ms": sorted(values)[math.ceil(len(values)*.95)-1] if values else None,
            "max_ms":max(values) if values else None}


def validate_proxy_ports(info):
    expected={('127.0.0.1','18443'),('::1','18443')}
    for bindings in [info['HostConfig']['PortBindings'],info['NetworkSettings']['Ports']]:
        published={key:value for key,value in bindings.items() if value is not None}
        if set(published)!={'8443/tcp'} or len(published['8443/tcp'])!=2:
            raise RuntimeError('Proxy must actually publish both loopbacks on port 18443')
        if {(x['HostIp'],x['HostPort']) for x in published['8443/tcp']}!=expected:
            raise RuntimeError('Refusing unexpected proxy interfaces or ports')


def inspect_state(project):
    code = """
import json
from sqlalchemy import text
from app.db import engine
from app.redis_store import get_redis
from rq import Queue
from rq.registry import FailedJobRegistry,StartedJobRegistry
from app.rule_manifest import RULES_SHA256
with engine.connect() as c:
 counts={t:c.execute(text('select count(*) from '+t)).scalar() for t in ['users','sites','events']}
 rows=c.execute(text('''select site_id,count(*),count(*) filter(where processed_at is null),
 percentile_cont(.5) within group(order by extract(epoch from (processed_at-received_at))),
 percentile_cont(.95) within group(order by extract(epoch from (processed_at-received_at))),
 count(*) filter(where processed_at is not null and (features->>'rules_source_sha256') is distinct from :hash)
 from events group by site_id'''),{'hash':RULES_SHA256}).all()
 r=get_redis();q=Queue('shield',connection=r)
 print(json.dumps({'counts':counts,'sites':[dict(site_id=x[0],stored=x[1],pending=x[2],processing_median_s=x[3],processing_p95_s=x[4],wrong_rule_fingerprint=x[5]) for x in rows],
 'queued':q.count,'started':StartedJobRegistry('shield',connection=r).count,'failed':FailedJobRegistry('shield',connection=r).count,'rules_source_sha256':RULES_SHA256}))
"""
    return json.loads(docker("exec", project+"-api-1", "python", "-c", code))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--ca", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-disposable", action="store_true", required=True)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--rate", type=int, default=500)
    parser.add_argument("--workers", type=int, choices=range(1,5), default=1,
                        help="Expected healthy worker replicas; does not change the stack")
    args = parser.parse_args()
    import re
    if not re.fullmatch(r"shield-perf-[a-z0-9-]+", args.project) or not 10 <= args.seconds <= 3600 or not 4 <= args.rate <= 1000 or args.rate % 4:
        parser.error("Use a shield-perf-* project, 10–3600 seconds and a rate divisible by four (4–1000)")
    info = json.loads(docker("inspect", args.project+"-localproxy-1"))[0]
    assert info["Config"]["Labels"]["com.docker.compose.project"] == args.project
    validate_proxy_ports(info)
    initial = inspect_state(args.project)
    assert initial["counts"] == {"users":0,"sites":0,"events":0}, "Refusing a nonempty instance"
    assert initial["queued"] == initial["started"] == initial["failed"] == 0
    context = ssl.create_default_context(cafile=str(args.ca))
    report = {"at":datetime.now(timezone.utc).isoformat(),"project":args.project,"passed":False,
              "scope":"Four synthetic owners/sites; concurrent CA-verified HTTPS ingest and owner HTTP reads; real PostgreSQL/Redis/RQ/maintenance. No browser rendering, scanner, ML or real users.",
              "rate":args.rate,"duration_seconds":args.seconds,"checkpoints":[],"initial":initial,
              "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    report["images"]={service:docker("inspect",args.project+'-'+service+'-1',"--format","{{.Image}}") for service in ['api','worker','maintenance','db','redis','localproxy']}
    worker_ids=docker("ps","-q","--filter","label=com.docker.compose.project="+args.project,
                      "--filter","label=com.docker.compose.service=worker").split()
    assert len(worker_ids)==args.workers, "Worker replica count differs from the requested measurement"
    workers=json.loads(docker("inspect",*worker_ids))
    assert all(w["State"].get("Health",{}).get("Status")=="healthy" for w in workers), "Every worker must start healthy"
    report["workers"]=[{"name":w["Name"],"image":w["Image"],"initial_restarts":w["RestartCount"]} for w in workers]
    assert all(not any(item.startswith('SHIELD_MODEL_DIR=') and item.partition('=')[2] for item in w['Config']['Env']) for w in workers), "This workload requires rules-only workers"
    lock = threading.Lock()
    def save():
        temporary = args.output.with_suffix(args.output.suffix+".tmp")
        temporary.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        temporary.replace(args.output)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    save()
    tenants = []
    try:
        for i in range(4):
            client = httpx.Client(base_url=ORIGIN,verify=context,timeout=10,trust_env=False)
            registered = checked(client.post("/app/api/register",headers={"Origin":ORIGIN},json={"email":f"perf-{uuid.uuid4().hex}@example.test","password":secrets.token_urlsafe(32)}),201)
            headers = {"Origin":ORIGIN,"X-CSRF-Token":registered.json()["csrf_token"]}
            site = checked(client.post("/app/api/sites",headers=headers,json={"domain":f"tenant-{i}.example"}),201).json()
            tenants.append({"client":client,"site":site["id"],"key":site["api_key"],"headers":headers,"accepted":0,"batch_ms":[],"owner_ms":[],"owner_routes":{},"owner_cold_ms":None,"errors":[]})
        # Same event ID in every tenant; spoofed site_id must never redirect it.
        probe = event(0,"mixed_comments")
        for i,t in enumerate(tenants):
            body={"events":[{**probe,"path":f"/tenant-probe-{i}","site_id":tenants[(i+1)%4]["site"]}]}
            headers={"X-API-Key":t["key"]}
            assert checked(t["client"].post("/v1/events",headers=headers,json=body),202).json()["accepted"] == 1
            assert checked(t["client"].post("/v1/events",headers=headers,json=body),202).json()["duplicates"] == 1
            checked(t["client"].post("/v1/heartbeat",headers=headers))
        for i,t in enumerate(tenants):
            feed=checked(t["client"].get("/app/sites/"+t["site"]+"/feed")).text
            assert f"/tenant-probe-{i}" in feed
            assert all(f"/tenant-probe-{j}" not in feed for j in range(4) if i!=j)
            for other in tenants:
                if other is t: continue
                for suffix in ["", "/feed"]:
                    checked(t["client"].get("/app/sites/"+other["site"]+suffix),404)
                checked(t["client"].get("/app/api/sites/"+other["site"]+"/keys"),404)
        started = time.monotonic();stop = threading.Event();finished=threading.Event()
        def ingest(t):
            per_rate=args.rate//4;target=per_rate*args.seconds;offset=0;last_heartbeat=started
            with httpx.Client(base_url=ORIGIN,verify=context,timeout=10,trust_env=False) as client:
                while offset < target and not stop.is_set():
                    time.sleep(max(0,started+offset/per_rate-time.monotonic()))
                    count=min(50, per_rate, target-offset);begin=time.perf_counter()
                    try:
                        response=checked(client.post("/v1/events",headers={"X-API-Key":t["key"]},json={"events":[event(offset+j,"mixed_comments") for j in range(count)]}),202)
                        accepted=response.json()["accepted"]
                        assert accepted==count,"Unexpected accepted count"
                        with lock:t["accepted"]+=accepted
                    except Exception as error:
                        with lock:t["errors"].append(type(error).__name__+": "+str(error) if isinstance(error,AssertionError) else type(error).__name__)
                        stop.set()
                    finally:
                        with lock:t["batch_ms"].append((time.perf_counter()-begin)*1000)
                    offset+=count
                    if time.monotonic()-last_heartbeat>30:
                        checked(client.post("/v1/heartbeat",headers={"X-API-Key":t["key"]}));last_heartbeat=time.monotonic()
            return time.monotonic()
        def read_owner(t):
            # Separate connection pool; same synthetic owner's secure session.
            paths=["/app/api/sites","/app/api/inbox","/app/api/sensor-health","/app/api/sites/"+t["site"]+"/connection","/app/sites/"+t["site"],"/app/sites/"+t["site"]+"/feed"]
            with httpx.Client(base_url=ORIGIN,verify=context,timeout=10,trust_env=False,cookies=t["client"].cookies) as client:
                n=0
                while not finished.is_set() and not stop.is_set():
                    path=paths[n%len(paths)];begin=time.perf_counter()
                    try:
                        r=checked(client.get(path))
                        if path=="/app/api/sites":assert [x["id"] for x in r.json()]==[t["site"]]
                        elif path=="/app/api/inbox":assert all(x["site_id"]==t["site"] for x in r.json()["incidents"])
                        elif path=="/app/api/sensor-health":assert all(x["site_id"]==t["site"] for x in r.json()["alerts"])
                    except Exception as error:
                        with lock:t["errors"].append(type(error).__name__)
                        stop.set()
                    finally:
                        with lock:
                            duration=(time.perf_counter()-begin)*1000
                            t["owner_ms"].append(duration)
                            t["owner_routes"].setdefault(path.replace(t["site"],'{site_id}'),[]).append(duration)
                            if n==0:t["owner_cold_ms"]=duration
                    n+=1;finished.wait(.5)
        with ThreadPoolExecutor(max_workers=8) as pool:
            readers=[pool.submit(read_owner,t) for t in tenants]
            writers=[pool.submit(ingest,t) for t in tenants]
            try:
                progress=time.monotonic()
                while not all(f.done() for f in writers):
                    wait(writers,timeout=1)
                    if time.monotonic()-progress>=30:
                        with lock:
                            report["checkpoints"].append({"elapsed_seconds":time.monotonic()-started,"accepted":sum(t["accepted"] for t in tenants)})
                            save()
                        print(json.dumps(report["checkpoints"][-1]),flush=True)
                        progress=time.monotonic()
                elapsed=max(future.result() for future in writers)-started
            finally:
                stop.set();finished.set()
            for future in readers:future.result()
        report["elapsed_ingest_seconds"]=elapsed
        report["accepted_per_second"]=sum(t["accepted"] for t in tenants)/elapsed
        save()
        # Preserve the first drain snapshot before any later evidence query.
        deadline=time.monotonic()+120
        while True:
            state=inspect_state(args.project);report["checkpoints"].append({"elapsed_seconds":time.monotonic()-started,"runtime":state})
            report["last_observed_runtime"]=state;save()
            if all(s["pending"]==0 for s in state["sites"]) and state["queued"]==state["started"]==0:break
            if time.monotonic()>deadline:raise RuntimeError("Processing did not drain within 120 seconds")
            time.sleep(5)
        report["elapsed_ingest_seconds"]=elapsed
        report["tenants"]=[{"site_id":t["site"],"accepted":t["accepted"],"errors":t["errors"],"batch_latency":summary(t["batch_ms"]),"owner_http_latency":summary(t["owner_ms"])} for t in tenants]
        report["accepted_per_second"]=sum(t["accepted"] for t in tenants)/elapsed
        report["final"]=state;save()
        assert state["counts"]=={"users":4,"sites":4,"events":sum(t["accepted"] for t in tenants)+4}
        for t in tenants:
            foreign=tenants[(tenants.index(t)+1)%4]
            incidents=checked(t["client"].get("/app/api/inbox")).json()["incidents"]
            assert incidents, "Expected mixed workload findings"
            checked(foreign["client"].get("/app/api/incidents/"+incidents[0]["id"]),404)
            checked(foreign["client"].post("/app/api/incidents/"+incidents[0]["id"]+"/status",headers=foreign["headers"],json={"status":"resolved"}),404)
            row=next(s for s in state["sites"] if s["site_id"]==t["site"])
            assert row["stored"]==t["accepted"]+1 and row["wrong_rule_fingerprint"]==0
            assert not t["errors"] and t["accepted"]==args.rate//4*args.seconds
            assert row["processing_p95_s"]<=10, "Processing p95 exceeded 10 seconds"
            assert summary(t["owner_ms"])["p95_ms"]<=1000, "Owner HTTP p95 exceeded 1000 ms"
            assert summary(t["batch_ms"])["p95_ms"]<=1000, "Ingest batch p95 exceeded 1000 ms"
        assert state["failed"]==0 and report["accepted_per_second"]>=args.rate*.99
        final_workers=json.loads(docker("inspect",*worker_ids))
        report["final_workers"]=[{"name":w["Name"],"status":w["State"].get("Health",{}).get("Status"),"restarts":w["RestartCount"]} for w in final_workers]
        assert all(w["State"].get("Health",{}).get("Status")=="healthy" and w["RestartCount"]==before["RestartCount"] for w,before in zip(final_workers,workers)), "Workers restarted or lost health during the measurement"
        report["passed"]=True
    except Exception as error:
        report["failure"]={"type":type(error).__name__,"message":str(error) if isinstance(error,(AssertionError,RuntimeError)) else "Transport or runtime failure; inspect services"}
        raise
    finally:
        with lock:
            report["tenants"]=[{"site_id":t["site"],"accepted":t["accepted"],"errors":t["errors"],"batch_latency":summary(t["batch_ms"]),"owner_http_latency":summary(t["owner_ms"]),"first_owner_request_ms":t["owner_cold_ms"],"owner_routes":{path:summary(samples) for path,samples in t["owner_routes"].items()}} for t in tenants]
        save()
        for tenant in tenants:tenant["client"].close()
    print(json.dumps({"passed":True,"report":str(args.output),"accepted_per_second":report["accepted_per_second"]}),flush=True)


if __name__ == "__main__":
    main()
