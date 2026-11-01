import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(16), default="monitor")  # monitor | block (block stays off in v1)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    prefix: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64))  # sha256 hex; raw key is never stored
    revoked: Mapped[bool] = mapped_column(default=False)


class Event(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)  # client-made UUID = idempotency
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
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
    __table_args__ = (
        Index("ix_events_site_ts", "site_id", "ts"),
        Index("ix_events_site_ip", "site_id", "ip_hash"),
    )
