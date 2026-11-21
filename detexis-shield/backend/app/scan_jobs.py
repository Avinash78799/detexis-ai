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


def schedule_rescans(redis):
    from rq import Queue
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        for site in db.scalars(select(Site).where(Site.verified_at.is_not(None))):
            if utc(site.verified_at) < now - timedelta(days=7):
                continue
            recent = db.scalar(select(Scan).where(Scan.site_id == site.id).order_by(Scan.created_at.desc()).limit(1))
            if recent is None or utc(recent.created_at) < now - timedelta(days=1):
                recent = Scan(site_id=site.id)
                db.add(recent)
                db.flush()
            if recent.status == "pending":
                Queue("shield", connection=redis).enqueue("app.scan_jobs.run_scan", recent.id, job_timeout=45, result_ttl=0)
        db.commit()
