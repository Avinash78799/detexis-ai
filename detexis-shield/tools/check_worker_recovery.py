"""Controlled idle-worker fault check for an instance with ZERO websites.

Removes only this worker's ephemeral RQ registration. Requires an empty queue,
an idle healthy worker and no Site records. Does not modify tenant data. Waits
for the in-process watcher and Compose restart policy to recover registration.
Do not use this as an availability or active-job recovery benchmark.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from computer import compose, command

STATE = """
import json
from app.worker_health import REGISTRATION_FILE, healthy
from app.redis_store import get_redis
r=get_redis(); key=REGISTRATION_FILE.read_text().strip()
print(json.dumps({'key':key,'healthy':healthy(r,key)}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-idle-fault-check", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Refuse to disrupt an instance once somebody has connected a website.
    compose("exec", "-T", "api", "python", "-c",
            "from app.db import SessionLocal;from app.models import Site;from sqlalchemy import select,func;"
            "s=SessionLocal();assert s.scalar(select(func.count()).select_from(Site))==0,'Refusing fault check: websites exist';s.close()")
    identity = compose("ps", "-q", "worker", capture=True).strip()
    before_restarts = int(command("inspect", identity, "--format", "{{.RestartCount}}", capture=True))
    before = json.loads(compose("exec", "-T", "worker", "python", "-c", STATE, capture=True))
    assert before["healthy"], "Worker must start healthy"
    compose("exec", "-T", "worker", "python", "-c", """
from app.worker_health import REGISTRATION_FILE, healthy
from app.redis_store import get_redis
from rq import Queue
r=get_redis(); key=REGISTRATION_FILE.read_text().strip()
assert key.startswith('rq:worker:') and healthy(r,key)
assert r.hget(key,'state')==b'idle' and Queue('shield',connection=r).count==0
assert r.delete(key)==1
""")
    started = time.monotonic()
    deadline = started + 150
    while time.monotonic() < deadline:
        restarts = int(command("inspect", identity, "--format", "{{.RestartCount}}", capture=True))
        if restarts > before_restarts:
            try:
                after = json.loads(compose("exec", "-T", "worker", "python", "-c", STATE, capture=True))
            except RuntimeError:
                after = None
            if after and after["healthy"] and after["key"] != before["key"]:
                report = {"passed":True, "checked_at":datetime.now(timezone.utc).isoformat(),
                          "elapsed_seconds":time.monotonic()-started,
                          "restart_count_delta":restarts-before_restarts,
                          "new_registration":True, "native_health":True,
                          "scope":"Idle recovery on a zero-site instance with an empty queue. No active job, customer data, host suspend or Redis outage was tested."}
                code = ("import hashlib,json;from pathlib import Path;print(json.dumps({n:"
                        "hashlib.sha256(Path('app',n).read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest() "
                        "for n in ['run_worker.py','worker_watch.py','worker_health.py']}))")
                report["source_sha256"] = json.loads(compose("exec", "-T", "worker", "python", "-c", code, capture=True))
                report["image_id"] = command("inspect", identity, "--format", "{{.Image}}", capture=True).strip()
                args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
                print(json.dumps(report))
                return
        time.sleep(3)
    raise RuntimeError("Worker did not recover within 150 seconds; inspect its logs")


if __name__ == "__main__":
    main()
