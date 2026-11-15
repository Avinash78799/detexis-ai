"""Missing heartbeat signals are operational gaps, never attack verdicts."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, or_, exists, select, func

from .accounts import owner
from .db import SessionLocal, get_db
from .models import Site, ApiKey, SensorHealthAlert

router = APIRouter()
HEARTBEAT_GRACE = timedelta(minutes=3)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def check_sensor_health(at=None, limit=100):
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None or not 1 <= limit <= 100:
        raise ValueError("Use an aware timestamp and a batch limit of 1 to 100")
    cutoff = at - HEARTBEAT_GRACE
    active_key = exists(select(ApiKey.id).where(ApiKey.site_id == Site.id, ApiKey.revoked.is_(False)))
    configuring = exists(select(ApiKey.id).where(ApiKey.site_id == Site.id, ApiKey.revoked.is_(False), ApiKey.created_at >= cutoff))
    open_alert = exists(select(SensorHealthAlert.id).where(SensorHealthAlert.site_id == Site.id, SensorHealthAlert.resolved_at.is_(None)))
    # Only select transitions. Already-open stale signals cannot starve later sites.
    transition = or_(and_(active_key, ~configuring, Site.last_heartbeat < cutoff, ~open_alert),
                     and_(open_alert, or_(~active_key, Site.last_heartbeat >= cutoff)))
    changes = {"opened":0,"resolved":0}
    with SessionLocal() as db:
        sites = db.scalars(select(Site).where(transition).order_by(Site.id).limit(limit)
                           .with_for_update(skip_locked=True)).all()
        for site in sites:
            # Site mutex matches worker/account mutation ordering. PostgreSQL
            # serializes concurrent checkers and heartbeat updates on this row.
            alert = db.scalar(select(SensorHealthAlert).where(SensorHealthAlert.site_id == site.id,
                                                              SensorHealthAlert.resolved_at.is_(None)))
            active = db.scalar(select(exists().where(ApiKey.site_id == site.id, ApiKey.revoked.is_(False))))
            if alert and (not active or (site.last_heartbeat and aware(site.last_heartbeat) >= cutoff)):
                alert.resolved_at = at
                alert.resolution = "heartbeat_resumed" if active else "monitoring_disabled"
                changes["resolved"] += 1
            elif active and site.last_heartbeat and aware(site.last_heartbeat) < cutoff and alert is None:
                db.add(SensorHealthAlert(site_id=site.id, opened_at=at, heartbeat_at=site.last_heartbeat))
                changes["opened"] += 1
        db.commit()
    return changes


def health_feed(db, user, limit=100):
    query = select(SensorHealthAlert, Site.domain).join(Site, Site.id == SensorHealthAlert.site_id).where(Site.owner_id == user.id)
    rows = db.execute(query.order_by(SensorHealthAlert.resolved_at.is_not(None), SensorHealthAlert.opened_at.desc(),
                                    SensorHealthAlert.id).limit(limit+1)).all()
    open_count = db.scalar(select(func.count()).select_from(SensorHealthAlert).join(Site, Site.id == SensorHealthAlert.site_id)
                           .where(Site.owner_id == user.id, SensorHealthAlert.resolved_at.is_(None)))
    return {"alerts":[{"id":alert.id,"site_id":alert.site_id,"domain":domain,
                       "opened_at":aware(alert.opened_at),"last_heartbeat_at":aware(alert.heartbeat_at),
                       "resolved_at":aware(alert.resolved_at) if alert.resolved_at else None,
                       "resolution":alert.resolution} for alert,domain in rows[:limit]],
            "open_count":open_count,"truncated":len(rows)>limit,
            "checked_at":datetime.now(timezone.utc),"heartbeat_grace_seconds":int(HEARTBEAT_GRACE.total_seconds())}


@router.get("/app/api/sensor-health")
def sensor_health(user=Depends(owner), db=Depends(get_db), limit: int = Query(default=100, ge=1, le=100)):
    return health_feed(db, user, limit)


@router.get("/app/sensor-health")
def sensor_health_page(request: Request, user=Depends(owner), db=Depends(get_db)):
    from .dashboard import templates
    return templates.TemplateResponse(request=request, name="sensor_health.html", context={"health":health_feed(db,user)})
