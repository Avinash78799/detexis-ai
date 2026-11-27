"""Remove one owner's live records in the caller's transaction."""
from sqlalchemy import delete, select, update

from .models import (Alert, ApiKey, BrowserSession, Event, HourBucket, Incident,
                     IncidentAction, Scan, SensorHealthAlert, Site, User)


def remove_site_data(db, sites):
    """Remove records for site IDs locked and authorized by the caller."""
    incidents = select(Incident.id).where(Incident.site_id.in_(sites))
    db.execute(delete(IncidentAction).where(IncidentAction.incident_id.in_(incidents)))
    for model in [Alert, Scan, SensorHealthAlert, HourBucket, Event, ApiKey, Incident]:
        db.execute(delete(model).where(model.site_id.in_(sites)))
    db.execute(delete(Site).where(Site.id.in_(sites)))


def remove_account_data(db, user_id):
    # The caller holds the User NO KEY UPDATE lock. This permits in-flight
    # actor foreign-key checks to finish while we wait for their Site locks.
    sites = list(db.scalars(select(Site.id).where(Site.owner_id == user_id)
                           .order_by(Site.id).with_for_update()))
    remove_site_data(db, sites)
    # Preserve any historical record on another owner's site, without retaining
    # a reference to the removed account (normal owner triage is site-scoped).
    db.execute(update(IncidentAction).where(IncidentAction.actor_id == user_id).values(actor_id=None))
    db.execute(delete(BrowserSession).where(BrowserSession.user_id == user_id))
    db.execute(delete(User).where(User.id == user_id))
