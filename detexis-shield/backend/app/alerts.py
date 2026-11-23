"""Per-site notification outbox. Destinations are configured by the operator."""
import json
import os
import smtplib
from email.message import EmailMessage
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select, and_, or_, case

from .db import SessionLocal
from .models import Alert, Incident


def deliver(channel, destination, message):
    if channel == "email":
        email = EmailMessage()
        email["From"] = os.environ["SMTP_FROM"]
        email["To"] = destination
        email["Subject"] = "Detexis Shield security incident"
        email.set_content(message)
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "465")), timeout=5) as smtp:
            if os.getenv("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(email)
    elif channel == "slack":
        target = urlsplit(destination)
        if target.scheme != "https" or target.hostname != "hooks.slack.com" or target.port not in (None, 443) or target.username:
            raise ValueError("invalid Slack webhook")
        with httpx.Client(timeout=5, trust_env=False) as http:
            http.post(destination, json={"text": message}).raise_for_status()
    elif channel == "telegram":
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        if not destination.lstrip("-").isdigit() or not all(c.isalnum() or c in "-_:" for c in token):
            raise ValueError("invalid Telegram configuration")
        with httpx.Client(timeout=5, trust_env=False) as http:
            response = http.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                 json={"chat_id": destination, "text": message})
            response.raise_for_status()
            if not response.json().get("ok"):
                raise ValueError("Telegram rejected delivery")
    else:
        raise ValueError("unsupported alert channel")


def send_pending(limit=100):
    targets = json.loads(os.getenv("SHIELD_ALERT_TARGETS") or "{}")
    configured = [site for site, channels in targets.items() if channels]
    sent = 0
    with SessionLocal() as db:
        # Mark new destination-free rows once, then reconsider only after their
        # site is configured. Deliverable rows take priority over that bookkeeping
        # so an unconfigured tenant cannot consume another tenant's whole batch.
        enabled = Alert.site_id.in_(configured)
        eligible = or_(Alert.status == "pending", and_(Alert.status == "unconfigured", enabled))
        rows = db.scalars(select(Alert).where(eligible, Alert.attempts < 5)
                          .order_by(case((enabled, 0), else_=1), Alert.created_at, Alert.id)
                          .limit(limit).with_for_update(skip_locked=True)).all()
        for alert in rows:
            channels = targets.get(alert.site_id, {})
            if not channels:
                alert.status = "unconfigured"
                continue
            incident = db.get(Incident, alert.incident_id)
            message = f"Detexis Shield: {incident.severity} incident {incident.id}; rules: {', '.join(incident.rules)}; events: {incident.event_count}."
            delivered = set(alert.delivered)
            alert.attempts += 1
            for channel, destination in channels.items():
                if channel in delivered:
                    continue
                try:
                    deliver(channel, destination, message)
                    delivered.add(channel)
                except Exception:
                    pass  # Store outcome, never credentials or exception URLs.
            alert.delivered = sorted(delivered)
            if set(channels) <= delivered:
                alert.status = "sent"
                sent += 1
            elif alert.attempts == 5:
                alert.status = "failed"
        db.commit()
    return sent
