import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from .db import SessionLocal
from .models import Scan, Site
from .worker import utc


def run_scan(scan_id):
    with SessionLocal() as db:
        record = db.scalar(select(Scan).where(Scan.id == scan_id).with_for_update())
        if record is None or record.status != "pending":
            return
        site = db.get(Site, record.site_id)
        if site.verified_at is None or utc(site.verified_at) < datetime.now(timezone.utc) - timedelta(days=7):
            record.status = "unverified"
        else:
            try:
                # Only this dispatcher holds DB credentials; the scanner service does not.
                with httpx.Client(timeout=30, trust_env=False) as http:
                    response = http.post(os.getenv("SCANNER_SERVICE_URL", "http://scanner:8001") + "/scan",
                                         json={"domain": site.domain, "selectors": site.settings.get("dkim_selectors", [])})
                    response.raise_for_status()
                    record.result = response.json()
                    record.status = "complete"
            except Exception:
                record.status = "failed"
                record.result = {"error": "Scanner unavailable, unsafe target, or scan failed"}
        db.commit()


def enqueue_scan(scan_id, redis):
    """Serialize publishers per site; recover a pending scan after Redis loss."""
    from rq import Queue
    with SessionLocal() as db:
        site = db.scalar(select(Site).join(Scan, Scan.site_id == Site.id)
                         .where(Scan.id == scan_id).with_for_update(of=Site, key_share=True))
        if site is None:
            return False
        record = db.get(Scan, scan_id)
        if record is None or record.status != "pending":
            return False
        queue = Queue("shield", connection=redis)
        identity = "dxs-scan-" + scan_id
        job = queue.fetch_job(identity)
        if job is not None:
            if job.get_status() in {"queued", "started", "deferred", "scheduled"}:
                return False
            job.delete()
        queue.enqueue("app.scan_jobs.run_scan", scan_id, job_id=identity,
                      job_timeout=45, result_ttl=0)
        return True


def schedule_rescans(redis):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        sites = list(db.scalars(select(Site.id).where(Site.verified_at.is_not(None))))
    for site_id in sites:
        with SessionLocal() as db:
            site = db.scalar(select(Site).where(Site.id == site_id)
                             .with_for_update(key_share=True, skip_locked=True))
            if site is None or site.verified_at is None or utc(site.verified_at) < now - timedelta(days=7):
                continue
            pending = db.scalar(select(Scan).where(Scan.site_id == site.id, Scan.status == "pending")
                                .order_by(Scan.created_at, Scan.id).limit(1))
            recent = db.scalar(select(Scan).where(Scan.site_id == site.id)
                               .order_by(Scan.created_at.desc(), Scan.id).limit(1))
            if pending is not None:
                record = pending
            elif recent is None or utc(recent.created_at) < now - timedelta(days=1):
                record = Scan(site_id=site.id)
                db.add(record)
            else:
                continue
            # A fast worker must be able to see the row when the job is published.
            db.commit()
            scan_id = record.id
        enqueue_scan(scan_id, redis)
