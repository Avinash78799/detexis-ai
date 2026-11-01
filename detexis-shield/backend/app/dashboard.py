from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from .auth import current_site
from .db import get_db
from .models import Event, Incident, Scan

router = APIRouter()
basic = HTTPBasic(auto_error=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def dashboard_site(credentials: HTTPBasicCredentials | None = Depends(basic), db=Depends(get_db)):
    try:
        if credentials is None:
            raise HTTPException(401)
        return current_site(x_api_key=credentials.password, db=db)
    except HTTPException:
        raise HTTPException(401, "Use your site API key as the password", headers={"WWW-Authenticate": 'Basic realm="Detexis Shield", charset="UTF-8"'})


def context(db, site):
    return {"site": site,
            "events": db.scalars(select(Event).where(Event.site_id == site.id).order_by(Event.received_at.desc()).limit(50)).all(),
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
