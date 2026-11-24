from pathlib import Path
import hashlib
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from .auth import current_site
from .db import get_db
from .models import Alert, Event, Incident, Scan

router = APIRouter()
basic = HTTPBasic(auto_error=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
def support_contact():
    address = os.getenv("SHIELD_SUPPORT_EMAIL", "").strip()
    if len(address) <= 254 and re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", address):
        return address
    return None


templates.env.globals["support_contact"] = support_contact
templates.env.globals["asset_versions"] = {
    name: hashlib.sha256((Path(__file__).parent / "static" / name).read_bytes()).hexdigest()[:12]
    for name in ("dashboard.css", "dashboard.js", "account.css", "api.js", "account.js", "htmx.min.js", "inbox.js", "analyze.js", "analyze.css")
}


def dashboard_site(credentials: HTTPBasicCredentials | None = Depends(basic), db=Depends(get_db)):
    try:
        if credentials is None:
            raise HTTPException(401)
        return current_site(x_api_key=credentials.password, db=db)
    except HTTPException:
        raise HTTPException(401, "Use your site API key as the password", headers={"WWW-Authenticate": 'Basic realm="Detexis Shield", charset="UTF-8"'})


def context(db, site):
    now = datetime.now(timezone.utc)
    def age(value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return now - value
    sensor_status = ("Awaiting first heartbeat" if site.last_heartbeat is None else
                     "Reporting" if age(site.last_heartbeat) <= timedelta(minutes=3) else "Heartbeat overdue")
    verification_status = ("Not verified" if site.verified_at is None else
                           "Verified" if age(site.verified_at) < timedelta(days=7) else "Verification expired")
    states = db.scalars(select(Alert.status).where(Alert.site_id == site.id).order_by(Alert.created_at.desc()).limit(10)).all()
    notifications = ("Delivery needs setup" if "unconfigured" in states else "Delivery failed" if "failed" in states
                     else "Pending delivery" if "pending" in states else "Delivered" if states else "No alert records")
    events = db.scalars(select(Event).where(Event.site_id == site.id)
                        .order_by(Event.received_at.desc()).limit(50)).all()
    pending_events = [event for event in events if event.processed_at is None]
    if not events:
        traffic_status = "waiting"
    elif not pending_events:
        traffic_status = "processed"
    else:
        # The feed is newest first. A newer completion can precede older pending work.
        traffic_status = "delayed" if age(pending_events[-1].received_at) > timedelta(minutes=1) else "pending"
    return {"site": site,
            "sensor_status": sensor_status, "verification_status": verification_status,
            "notifications": notifications,
            "traffic_status": traffic_status, "pending_count": len(pending_events), "events": events,
            "incidents": db.scalars(select(Incident).where(Incident.site_id == site.id).order_by(Incident.last_seen.desc()).limit(20)).all(),
            "scans": db.scalars(select(Scan).where(Scan.site_id == site.id).order_by(Scan.created_at.desc()).limit(5)).all()}


@router.get("/dashboard")
def dashboard(request: Request, site=Depends(dashboard_site), db=Depends(get_db)):
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context(db, site))


@router.get("/dashboard/feed")
def feed(request: Request, site=Depends(dashboard_site), db=Depends(get_db)):
    return templates.TemplateResponse(request=request, name="feed.html", context=context(db, site))


@router.get("/v1/incidents")
def incidents(site=Depends(current_site), db=Depends(get_db)):
    rows = db.scalars(select(Incident).where(Incident.site_id == site.id).order_by(Incident.last_seen.desc()).limit(100)).all()
    return [{"id": r.id, "severity": r.severity, "rules": r.rules, "correlations": r.correlations,
             "event_count": r.event_count, "last_seen": r.last_seen} for r in rows]
