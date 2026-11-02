import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="monitor")  # monitor | block (block stays off in v1)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    honeytokens: Mapped[list] = mapped_column(JSON, default=lambda: ["/.env", "/admin-backup"])
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    verification_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    prefix: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64))  # sha256 hex; raw key is never stored
    revoked: Mapped[bool] = mapped_column(default=False)


class Event(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_hash: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(2048))
    query_redacted: Mapped[str] = mapped_column(String(2048), default="")
    ua: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column()
    flags: Mapped[list] = mapped_column(JSON, default=list)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (
        Index("ix_events_site_ts", "site_id", "ts"),
        Index("ix_events_site_ip", "site_id", "ip_hash"),
        Index("ix_events_unprocessed", "received_at", postgresql_include=["site_id", "event_id"],
              postgresql_where=text("processed_at IS NULL"), sqlite_where=text("processed_at IS NULL")),
        Index("ix_events_site_connection", "site_id", "received_at", postgresql_include=["processed_at"]),
        Index("ix_events_received", "received_at"),
    )


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    ip_hash: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    rules: Mapped[list] = mapped_column(JSON, default=list)
    correlations: Mapped[list] = mapped_column(JSON, default=list)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("site_id", "ip_hash", "bucket", name="uq_incident_group"),
                      Index("ix_incidents_site_seen", "site_id", "last_seen"))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    delivered: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HourBucket(Base):
    __tablename__ = "hour_buckets"
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), primary_key=True)
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    result: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    recovery_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IncidentAction(Base):
    __tablename__ = "incident_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    previous_status: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
