import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import EventIn
from test_smoke import event, make_site


@pytest.mark.parametrize("change", [{"event_id": "x" * 36}, {"ip_hash": "x" * 64}, {"ip_hash": ""},
                                    {"latency_ms": float("inf")}, {"latency_ms": float("nan")},
                                    {"ts": "2026-11-01T10:00:00"}])
def test_malformed_identity_or_nonfinite_measurements_rejected(change):
    with pytest.raises(ValueError):
        EventIn(**{**event(), **change})


def test_uuid_casing_cannot_bypass_idempotency():
    _, key = make_site("canonical-id.test")
    item = event()
    with TestClient(app) as client:
        first = client.post("/v1/events", headers={"X-API-Key": key}, json={"events": [item]})
        item["event_id"] = item["event_id"].upper()
        second = client.post("/v1/events", headers={"X-API-Key": key}, json={"events": [item]})
    assert first.json()["accepted"] == 1
    assert second.json()["accepted"] == 0
