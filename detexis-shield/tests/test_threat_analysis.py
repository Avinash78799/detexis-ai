import base64
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import malware, threat_analysis
from test_accounts import register
from test_smoke import make_site


def test_analysis_requires_session_and_csrf_and_does_not_persist_samples():
    make_site("analysis-fixture.test")
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post("/app/api/analyze/request", json={"path": "/"}).status_code == 401
        headers = register(client, "analysis-owner")
        assert client.post("/app/api/analyze/request", json={"path": "/"}).status_code == 403
        assert client.get("/app/analyze").status_code == 200
        response = client.post("/app/api/analyze/request", headers=headers,
                               json={"path": "/search", "query": "q=1+UNION+SELECT+password+FROM+users"})
        assert response.status_code == 200
        value = response.json()
        assert value["verdict"] == "suspicious_pattern"
        assert [f["rule_id"] for f in value["findings"]] == ["sqli_union"]
        assert "FROM+users" not in response.text
        # Samples must not synthesize incidents or telemetry for the owner.
        assert client.get("/app/api/sites").json() == []
        assert client.get("/app/api/inbox").json()["incidents"] == []
        clean = client.post("/app/api/analyze/request", headers=headers,
                            json={"path": "/docs", "query": "topic=union+membership&password=UNION+SELECT"}).json()
        assert clean["findings"] == [] and clean["verdict"] == "no_pattern_detected"
        assert "safety" in clean["limitations"]
        assert client.post("/app/api/analyze/request", headers=headers, json={"path": "https://example.com"}).status_code == 422
        assert client.post("/app/api/analyze/request", headers=headers, json={"path": "/", "query": "x" * 1025}).status_code == 422


def test_file_scan_size_invalid_input_unavailable_and_bounded_concurrency(monkeypatch):
    make_site("file-fixture.test")
    with TestClient(app, base_url="https://testserver") as client:
        headers = register(client, "file-owner")
        assert client.post("/app/api/analyze/file", headers=headers, json={"content_base64": "????"}).status_code == 422
        monkeypatch.delenv("CLAMAV_HOST", raising=False)
        body = {"content_base64": base64.b64encode(b"harmless text").decode()}
        assert client.post("/app/api/analyze/file", headers=headers, json=body).status_code == 503
        assert threat_analysis.scan_slot.acquire(blocking=False)
        try:
            assert client.post("/app/api/analyze/file", headers=headers, json=body).status_code == 503
        finally:
            threat_analysis.scan_slot.release()
        monkeypatch.setattr(malware, "scan", lambda data: {"verdict": "no_signature_detected", "signature": None, "engine": "test-fixture"})
        response = client.post("/app/api/analyze/file", headers=headers, json=body)
        assert response.status_code == 200 and len(response.json()["sha256"]) == 64
        assert response.json()["bytes"] == 13
        oversized = base64.b64encode(b"x" * (malware.MAX_FILE_BYTES + 1)).decode()
        assert client.post("/app/api/analyze/file", headers=headers, json={"content_base64": oversized}).status_code == 413
        assert client.post("/app/api/analyze/file", headers=headers, content=b"x" * 1500001).status_code == 413


@pytest.mark.parametrize("answer,expected", [
    ("stream: OK", "no_signature_detected"),
    ("stream: Win.Test.Signature FOUND", "signature_detected"),
    ("stream: Heuristics.Limits.Exceeded.MaxScanSize FOUND", "needs_review"),
    ("stream: Heuristics.Encrypted.Zip FOUND", "needs_review"),
    ("stream: scanner ERROR", None), ("unexpected", None),
])
def test_engine_verdicts_never_turn_errors_into_clean(monkeypatch, answer, expected):
    monkeypatch.setenv("CLAMAV_HOST", "test-engine")
    date = datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Y")
    monkeypatch.setattr(malware, "exchange", lambda host, command, content=None:
                        "ClamAV 1.4.6/12345/" + date if command == b"zVERSION\0" else answer)
    if expected is None:
        with pytest.raises(malware.ScanUnavailable):
            malware.scan(b"test")
    else:
        assert malware.scan(b"test")["verdict"] == expected


@pytest.mark.parametrize("version", ["ClamAV 1.4.6", "ERROR", "ClamAV 1.4.6/12345/invalid", "stale"])
def test_old_or_unknown_definition_versions_are_unavailable(monkeypatch, version):
    monkeypatch.setenv("CLAMAV_HOST", "test-engine")
    if version == "stale":
        version = "ClamAV 1.4.6/12345/" + (datetime.now(timezone.utc) - timedelta(days=4)).strftime("%a %b %d %H:%M:%S %Y")
    monkeypatch.setattr(malware, "exchange", lambda *args: version)
    with pytest.raises(malware.ScanUnavailable):
        malware.scan(b"test")


def test_clamd_reply_requires_bounded_terminated_response():
    import time
    class FakeSocket:
        def settimeout(self, timeout):
            assert timeout > 0
        def recv(self, count):
            return b"x" * count
    with pytest.raises(malware.ScanUnavailable):
        malware.reply(FakeSocket(), time.monotonic() + 1)
