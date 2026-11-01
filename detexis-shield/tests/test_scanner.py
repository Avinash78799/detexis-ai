import time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.safe_fetch import UnsafeTarget, domain_name, fetch, public_ip
from app.scanner import scan
from test_smoke import make_site


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "0.0.0.0", "192.168.0.1",
                              "172.16.0.1", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1",
                              "64:ff9b::7f00:1", "2002:7f00:1::", "224.0.0.1"])
def test_nonpublic_and_tunneled_ips_rejected(ip):
    assert not public_ip(ip)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://example.com:8080/", "http://user@example.com/",
                                "http://127.0.0.1/", "http://example.com.evil.test/", "http://example.com/#fragment",
                                "http://example.com/\r\nx", "http://example.com\\@evil.test/"])
def test_unsafe_urls_never_reach_transport(url):
    transport = Mock()
    with pytest.raises((UnsafeTarget, ValueError)):
        fetch(url, "example.com", resolver=lambda host: ["8.8.8.8"], transport=transport)
    transport.assert_not_called()


def test_dns_rebinding_checked_again_on_same_host_redirect():
    resolver = Mock(side_effect=[["8.8.8.8"], ["127.0.0.1"]])
    transport = Mock(return_value={"status": 302, "headers": [("Location", "/next")], "body": b"", "tls": None})
    with pytest.raises(UnsafeTarget):
        fetch("https://example.com/", "example.com", resolver=resolver, transport=transport)
    assert resolver.call_count == 2
    assert transport.call_count == 1
    assert transport.call_args.args[2] == "8.8.8.8"


def test_mixed_dns_answers_refused_before_connection():
    transport = Mock()
    with pytest.raises(UnsafeTarget):
        fetch("https://example.com/", "example.com", resolver=lambda host: ["8.8.8.8", "10.0.0.1"], transport=transport)
    transport.assert_not_called()


def test_cross_domain_and_https_downgrade_redirects_refused():
    for target in ("https://other.test/", "http://example.com/"):
        transport = Mock(return_value={"status": 302, "headers": [("Location", target)]})
        with pytest.raises(UnsafeTarget):
            fetch("https://example.com/", "example.com", resolver=lambda host: ["8.8.8.8"], transport=transport)
        assert transport.call_count == 1


def test_deadline_prevents_network_calls():
    resolver = Mock()
    with pytest.raises(TimeoutError):
        fetch("https://example.com/", "example.com", deadline=time.monotonic() - 1, resolver=resolver)
    resolver.assert_not_called()


def test_scanner_does_not_return_discovered_secret_bodies():
    def fake_fetch(url, domain, **kwargs):
        body = b"SECRET_KEY=do-not-store-me" if url.endswith("/.env") else b"not found"
        return {"status": 200, "headers": [], "body": body, "tls": {"version": "TLSv1.3"}}
    result = scan("example.com", fetcher=fake_fetch, lookup=lambda name: [])
    assert 0 <= result["score"] <= 100
    assert "do-not-store-me" not in str(result)
    assert next(f for f in result["findings"] if f["check"] == "exposed_files")["passed"] is False
    assert next(f for f in result["findings"] if f["check"] == "dkim")["passed"] is None


def test_ownership_gate_verification_and_cross_tenant_scan_lookup(monkeypatch):
    site, key = make_site("owned.example")
    _, other_key = make_site("other.example")
    headers = {"X-API-Key": key}
    with TestClient(app) as client:
        assert client.post("/v1/scans", headers=headers).status_code == 403
        challenge = client.post("/v1/domain/verification", headers=headers).json()
        monkeypatch.setattr("app.scan_api.txt", lambda name: [challenge["value"]])
        assert client.post("/v1/domain/verify", headers=headers).status_code == 200
        response = client.post("/v1/scans", headers=headers)
        assert response.status_code == 202
        scan_id = response.json()["scan_id"]
        assert client.get(f"/v1/scans/{scan_id}", headers={"X-API-Key": other_key}).status_code == 404
        assert client.get(f"/v1/scans/{scan_id}", headers=headers).status_code == 200


def test_cannot_verify_with_another_domains_token(monkeypatch):
    _, key = make_site("verify.example")
    headers = {"X-API-Key": key}
    with TestClient(app) as client:
        client.post("/v1/domain/verification", headers=headers)
        monkeypatch.setattr("app.scan_api.txt", lambda name: ["dxs-verification=wrong"])
        monkeypatch.setattr("app.scan_api.verify_http", lambda *args: False)
        assert client.post("/v1/domain/verify", headers=headers).status_code == 422


def test_vercel_style_domain_can_verify_using_https_file(monkeypatch):
    _, key = make_site("detexis.vercel.app")
    headers = {"X-API-Key": key}
    monkeypatch.setattr("app.scan_api.txt", lambda name: [])
    monkeypatch.setattr("app.scan_api.verify_http", lambda *args: True)
    with TestClient(app) as client:
        challenge = client.post("/v1/domain/verification", headers=headers).json()
        assert challenge["http_url"] == "https://detexis.vercel.app/.well-known/detexis-shield.txt"
        assert client.post("/v1/domain/verify", headers=headers).status_code == 200


def test_isolated_http_verification_checks_exact_body_and_fixed_path(monkeypatch):
    import hashlib
    from app.scanner_service import VerificationInput, verify_page
    body = b"dxs-verification=correct"
    fetcher = Mock(return_value={"status": 200, "body": body})
    monkeypatch.setattr("app.scanner_service.fetch", fetcher)
    challenge = VerificationInput(domain="example.com", expected_hash=hashlib.sha256(body).hexdigest())
    assert verify_page(challenge) == {"verified": True}
    assert fetcher.call_args.args[0] == "https://example.com/.well-known/detexis-shield.txt"
    fetcher.return_value = {"status": 200, "body": b"reflected correct substring"}
    assert verify_page(challenge) == {"verified": False}


def test_pinned_http_connects_to_vetted_ip_and_preserves_host_and_close_semantics(monkeypatch):
    from urllib.parse import urlsplit
    from app.safe_fetch import pinned_request

    class Socket:
        def __init__(self):
            self.data = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
            self.closed = False
            self.sent = b""
        def settimeout(self, timeout):
            assert 0 < timeout <= 2
        def sendall(self, data):
            self.sent += data
        def recv_into(self, buffer):
            assert not self.closed
            n = min(len(buffer), len(self.data))
            buffer[:n] = self.data[:n]
            self.data = self.data[n:]
            return n
        def close(self):
            self.closed = True

    sock = Socket()
    connect = Mock(return_value=sock)
    monkeypatch.setattr("app.safe_fetch.socket.create_connection", connect)
    result = pinned_request(urlsplit("http://example.com/a?q=x"), 80, "8.8.8.8", time.monotonic() + 5)
    assert result["body"] == b"ok"
    assert connect.call_args.args[0] == ("8.8.8.8", 80)
    assert b"Host: example.com\r\n" in sock.sent
    assert sock.closed
