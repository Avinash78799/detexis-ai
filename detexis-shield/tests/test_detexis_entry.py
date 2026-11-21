"""Deployment boundary: no inference, accounts or datastore writes on Vercel."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def entry(monkeypatch):
    spec = importlib.util.spec_from_file_location("detexis_entry_test", ROOT / "app.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    monkeypatch.syspath_prepend(str(ROOT))
    spec.loader.exec_module(module)
    return module


def test_entry_boots_without_models_database_or_session_secret(entry, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHIELD_PUBLIC_ORIGIN", raising=False)
    client = entry.create_app().test_client()
    assert client.get("/health").json == {"ok": True, "service": "detexis-entry"}
    response = client.get("/")
    assert response.status_code == 200 and b"connection needs setup" in response.data
    assert client.get("/shield").status_code == 503
    assert not list(tmp_path.iterdir())
    assert "set-cookie" not in response.headers
    assert "script-src 'none'" in response.headers["Content-Security-Policy"]


@pytest.mark.parametrize("origin", ["http://shield.example", "https://user:pass@shield.example",
    "https://shield.example/path", "https://shield.example?next=x", "https://shield.example#x",
    "https://shield.example:444", "https://shield.example\r\nX: x", "https://shield.example\\@evil.example",
    "//shield.example", "https://[invalid", "https://shield.example:bad"])
def test_operator_origin_validation_rejects_unsafe_configuration(entry, origin):
    assert entry.shield_origin(origin) is None


def test_routes_bridge_without_forwarding_passwords_uploads_or_next_query(entry, monkeypatch):
    monkeypatch.setenv("SHIELD_PUBLIC_ORIGIN", "https://shield.example/")
    client = entry.create_app().test_client()
    assert client.get("/shield?next=https://evil.example").headers["Location"] == "https://shield.example/app"
    assert client.get("/analyze").headers["Location"] == "https://shield.example/app/analyze"
    for path in ("/predict", "/signin", "/signup", "/analyze_upload", "/clear_alerts"):
        response = client.post(path, data={"password": "never-forward-this", "file": "sample"})
        assert response.status_code == 410
        assert "Location" not in response.headers and b"never-forward-this" not in response.data
        assert b"not been deleted or automatically migrated" in response.data
    monkeypatch.setenv("SHIELD_VERIFICATION_TOKEN", "dxs-verification=public-proof")
    assert client.get("/.well-known/detexis-shield.txt").data == b"dxs-verification=public-proof"


def test_entry_static_stylesheet_is_available(entry):
    client = entry.create_app().test_client()
    assert client.get("/static/shield-entry.css").status_code == 200
    assert client.get("/missing").status_code == 404
