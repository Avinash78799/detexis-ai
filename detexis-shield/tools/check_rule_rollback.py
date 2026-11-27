"""Exercise image rollback only on a healthy, zero-site, empty-queue instance.

Capture the old images before building a new release. The check temporarily
recreates API/worker/maintenance using those local images, then always restores
the current tagged images. No volume or datastore is recreated. No images pull.
"""
import argparse
import json
from pathlib import Path
import re
from datetime import datetime, timezone
from uuid import uuid4

from computer import compose, command, ROOT, PROJECT, ENV

ROLES = ("api", "worker", "maintenance")
INFO = """
import hashlib,json
from pathlib import Path
from app import rules
value={'version':getattr(rules,'RULESET_VERSION',1),
       'release':getattr(rules,'RULESET_RELEASE','legacy-v1'),
       'rules_sha256':hashlib.sha256(Path(rules.__file__).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()}
"""


def assert_empty():
    compose("exec", "-T", "api", "python", "-c",
        "from app.db import SessionLocal;from app.models import Site;from sqlalchemy import select,func;"
        "s=SessionLocal();assert s.scalar(select(func.count()).select_from(Site))==0,'Websites exist; use an isolated validation instance';s.close()")
    compose("exec", "-T", "worker", "python", "-c",
        "from app.worker_health import REGISTRATION_FILE,healthy;from app.redis_store import get_redis;from rq import Queue;"
        "r=get_redis();k=REGISTRATION_FILE.read_text().strip();"
        "assert healthy(r,k) and r.hget(k,'state')==b'idle' and Queue('shield',connection=r).count==0,'Worker is not idle with an empty queue'")


def snapshot(*, retain=False):
    result = {}
    for role in ROLES:
        identity = compose("ps", "-q", role, capture=True).strip()
        reference = command("inspect", identity, "--format", "{{.Config.Image}}", capture=True).strip()
        # Docker's container .Image may be a platform config digest, which is
        # not necessarily a usable image reference in the containerd store.
        image = command("image", "inspect", reference, "--format", "{{.Id}}", capture=True).strip()
        if retain:
            retained = "detexis-shield-rule-rollback-" + role + ":" + uuid4().hex[:12]
            command("image", "tag", reference, retained)
            reference = retained
        code = INFO
        if role == "api":
            code += "\nfrom urllib.request import urlopen\nassert json.load(urlopen('http://127.0.0.1:8000/ready',timeout=5))=={'ok':True}\n"
            code += "from app.db import SessionLocal\nfrom sqlalchemy import text\nwith SessionLocal() as db: value['schema_version']=db.scalar(text('SELECT version_num FROM alembic_version'))\n"
        code += "\nprint(json.dumps(value))"
        result[role] = {"image":image, "image_reference":reference,
                        **json.loads(compose("exec", "-T", role, "python", "-c", code, capture=True))}
    assert len({value["rules_sha256"] for value in result.values()}) == 1, "Mixed rule sources in running services"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-zero-site-check", action="store_true", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture-baseline", type=Path)
    group.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert_empty()
    if args.capture_baseline:
        current = snapshot(retain=True)
        with args.capture_baseline.open("x", encoding="utf-8") as handle:
            json.dump(current, handle, indent=2)
        print("Captured healthy rollback baseline; no services changed")
        return
    current = snapshot()
    if not args.output:
        parser.error("rollback check requires --output")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if set(baseline) != set(ROLES) or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", value["image"]) for value in baseline.values()):
        parser.error("Baseline must contain exactly the three local image IDs")
    for role in ROLES:
        reference = baseline[role].get("image_reference", "")
        if not re.fullmatch(r"detexis-shield-rule-rollback-" + role + r":[0-9a-f]{12}", reference):
            parser.error("Capture a baseline with retained local tags before upgrading")
        retained_id = command("image", "inspect", reference, "--format", "{{.Id}}", capture=True).strip()
        if retained_id != baseline[role]["image"]:
            parser.error("Retained rollback tag changed; do not roll out")
    assert baseline["api"]["version"] < current["api"]["version"], "Capture an earlier release before upgrading"
    overlay = args.baseline.parent / ("rule-rollback-override-" + uuid4().hex + ".json")
    with overlay.open("x", encoding="utf-8") as handle:
        json.dump({"services":{role:{"image":baseline[role]["image_reference"],"pull_policy":"never"} for role in ROLES}},handle)
    rolled_back = None
    try:
        command("compose", "-p", PROJECT, "--env-file", str(ENV),
                "-f", str(ROOT / "docker-compose.yml"), "-f", str(ROOT / "docker-compose.computer.yml"),
                "-f", str(ROOT / "docker-compose.malware.yml"), "-f", str(overlay),
                "up", "-d", "--no-build", "--no-deps", "--wait", "--wait-timeout", "120", *ROLES)
        rolled_back = snapshot()
        assert rolled_back == baseline, "Rollback did not select the captured images and source"
        assert_empty()
    finally:
        # Never leave the accepted current release downgraded, even on failure.
        compose("up", "-d", "--no-build", "--no-deps", "--wait", "--wait-timeout", "120", *ROLES)
    restored = snapshot()
    assert restored == current, "Current release was not restored exactly"
    assert restored["api"]["schema_version"] == baseline["api"]["schema_version"]
    assert_empty()
    report = {"passed":True,"checked_at":datetime.now(timezone.utc).isoformat(),
              "before":current,"rolled_back":rolled_back,"restored":restored,
              "scope":"Configuration/image rollback with zero sites and an idle empty queue. API readiness, source consistency and unchanged migration were verified; live traffic, account sessions and active jobs were not tested."}
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"passed":True,"restored_release":restored["api"]["release"],"report":str(args.output)}))


if __name__ == "__main__":
    main()
