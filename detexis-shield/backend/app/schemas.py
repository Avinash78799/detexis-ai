from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from uuid import UUID


class EventIn(BaseModel):
    event_id: str = Field(min_length=36, max_length=36)
    ts: datetime
    ip_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    method: str = Field(max_length=10)
    path: str = Field(max_length=2048)
    query_redacted: str = Field(default="", max_length=2048)
    ua: str = Field(default="", max_length=512)
    status: int = Field(ge=100, le=599)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    flags: list[str] = Field(default_factory=list, max_length=20)
    features: dict = Field(default_factory=dict)

    @field_validator("event_id")
    @classmethod
    def canonical_event_id(cls, value):
        return str(UUID(value))

    @field_validator("ts")
    @classmethod
    def aware_timestamp(cls, value):
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value


class BatchIn(BaseModel):
    events: list[EventIn] = Field(max_length=100)  # batch cap = payload cap
