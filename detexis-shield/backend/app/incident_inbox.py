"""Owner-scoped in-app inbox and incident triage; no messages leave the platform."""
from typing import Literal
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, and_, func

from .accounts import owner, owned_site, throttle
from .redis_store import get_redis
from .db import get_db
from .models import Site, Incident, IncidentAction, Event

router = APIRouter()


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def incident_summary(row, domain):
    return {"id": row.id, "site_id": row.site_id, "domain": domain, "severity": row.severity,
            "status": row.status, "rules": row.rules, "event_count": row.event_count,
            "first_seen": aware(row.first_seen), "last_seen": aware(row.last_seen)}


@router.get("/app/api/inbox")
def inbox(user=Depends(owner), db=Depends(get_db), before: datetime | None = None, before_id: UUID | None = None,
          limit: int = Query(default=30, ge=1, le=100)):
    query = select(Incident, Site.domain).join(Site, Site.id == Incident.site_id).where(Site.owner_id == user.id)
    if (before is None) != (before_id is None):
        raise HTTPException(422, "Provide both cursor fields")
    if before:
        if before.tzinfo is None:
            raise HTTPException(422, "Use a timezone-aware cursor")
        query = query.where(or_(Incident.last_seen < before,
                            and_(Incident.last_seen == before, Incident.id > str(before_id))))
    rows = db.execute(query.order_by(Incident.last_seen.desc(), Incident.id).limit(limit)).all()
    return {"incidents": [incident_summary(row, domain) for row, domain in rows],
            "next": {"before": aware(rows[-1][0].last_seen), "before_id": rows[-1][0].id} if len(rows) == limit else None}


def find_incident(db, user, incident_id, lock=False):
    query = select(Incident).join(Site, Site.id == Incident.site_id).where(Incident.id == incident_id, Site.owner_id == user.id)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Incident not found")
    if lock:
        # Match the worker's Site -> Incident lock order.
        owned_site(db, user, row.site_id)
        row = db.scalar(select(Incident).where(Incident.id == incident_id).with_for_update().execution_options(populate_existing=True))
        if row is None:
            # Retention can remove an old incident between the two reads.
            raise HTTPException(404, "Incident not found")
    return row


@router.get("/app/api/incidents/{incident_id}")
def details(incident_id: str, user=Depends(owner), db=Depends(get_db)):
    row = find_incident(db, user, incident_id)
    # Same grouping boundaries as the worker; cap evidence to bound response size.
    start = datetime.fromtimestamp(row.bucket * 300, timezone.utc)
    end = datetime.fromtimestamp((row.bucket + 1) * 300, timezone.utc)
    events = db.scalars(select(Event).where(Event.site_id == row.site_id, Event.ip_hash == row.ip_hash,
        Event.received_at >= start, Event.received_at < end, Event.processed_at.is_not(None), func.json_array_length(Event.findings) > 0)
        .order_by(Event.received_at.desc()).limit(100)).all()
    actions = db.scalars(select(IncidentAction).where(IncidentAction.incident_id == row.id)
                         .order_by(IncidentAction.created_at.desc(), IncidentAction.id.desc()).limit(50)).all()
    site = db.get(Site, row.site_id)
    return {**incident_summary(row, site.domain), "correlations": row.correlations,
            "evidence": [{"ts": event.received_at, "method": event.method, "path": event.path,
                          "status": event.status, "findings": event.findings} for event in events if event.findings],
            "actions": [{"at": action.created_at, "status": action.status, "previous_status": action.previous_status,
                         "note": action.note, "actor": "Owner" if action.actor_id else "System"} for action in actions]}


class Triage(BaseModel):
    status: Literal["open", "acknowledged", "resolved", "false_positive"]
    note: str = Field(default="", max_length=1000)


@router.post("/app/api/incidents/{incident_id}/status")
def triage(incident_id: str, body: Triage, request: Request, user=Depends(owner), db=Depends(get_db), redis=Depends(get_redis)):
    throttle(request, redis, identity=user.id, limit=60, namespace="triage")
    row = find_incident(db, user, incident_id, lock=True)
    previous = row.status
    if body.status != previous or body.note.strip():
        db.add(IncidentAction(incident_id=row.id, actor_id=user.id, previous_status=previous,
                              status=body.status, note=body.note.strip()))
        row.status = body.status
        db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/app/inbox")
def inbox_page(request: Request, user=Depends(owner)):
    from .dashboard import templates
    return templates.TemplateResponse(request=request, name="inbox.html", context={})
