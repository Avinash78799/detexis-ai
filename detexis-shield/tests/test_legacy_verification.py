import sys
from pathlib import Path

from flask import Flask

sys.path.append(str(Path("..").resolve()))
from shield_verification import blueprint


def test_legacy_site_ownership_route_is_opt_in_and_does_not_accept_header_injection(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(blueprint)
    client = app.test_client()
    monkeypatch.delenv("SHIELD_VERIFICATION_TOKEN", raising=False)
    assert client.get("/.well-known/detexis-shield.txt").status_code == 404
    monkeypatch.setenv("SHIELD_VERIFICATION_TOKEN", "dxs-verification=public-proof")
    response = client.get("/.well-known/detexis-shield.txt")
    assert response.status_code == 200
    assert response.data == b"dxs-verification=public-proof"
    assert response.headers["Cache-Control"] == "no-store"
    monkeypatch.setenv("SHIELD_VERIFICATION_TOKEN", "dxs-verification=x\r\nInjected: header")
    assert client.get("/.well-known/detexis-shield.txt").status_code == 404
