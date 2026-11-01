import asyncio
import sys
from unittest.mock import Mock

import httpx
import pytest

sys.path.insert(0, "sensor-sdk")
from detexis_shield import ShieldMiddleware, ShieldWSGIMiddleware
from detexis_shield.client import ShieldClient
from detexis_shield.redact import hash_ip


@pytest.fixture
def sink(monkeypatch):
    client = Mock()
    monkeypatch.setattr("detexis_shield.middleware.ShieldClient", lambda *a, **k: client)
    return client


def wrap(cls, app):
    return cls(app, "http://backend.invalid", "test-key", "site-salt")


def test_asgi_telemetry_failure_preserves_response(sink):
    sink.submit.side_effect = RuntimeError("sensor broken")
    messages = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 201})
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(message):
        messages.append(message)

    asyncio.run(wrap(ShieldMiddleware, app)({"type": "http"}, None, send))
    assert messages[-1]["body"] == b"ok"
    assert messages[0]["status"] == 201


def test_asgi_host_exception_is_preserved(sink):
    async def app(*args):
        raise ValueError("host failure")

    with pytest.raises(ValueError, match="host failure"):
        asyncio.run(wrap(ShieldMiddleware, app)({"type": "http"}, None, None))
    assert sink.submit.call_args.args[0]["status"] == 500


def test_full_buffer_drops_without_network(monkeypatch):
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    client = ShieldClient("http://backend.invalid", "key", max_buffer=1)
    client.submit({"event_id": "one"})
    client.submit({"event_id": "two"})
    assert client.q.qsize() == 1
    assert client.dropped == 1


@pytest.mark.parametrize("options", [{"max_buffer": 0}, {"batch_size": 101}, {"flush_interval": 0}])
def test_invalid_client_limits(options):
    with pytest.raises(ValueError):
        ShieldClient("http://backend.invalid", "key", **options)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_rejected_batches_are_counted(monkeypatch, status):
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    client = ShieldClient("http://backend.invalid", "key")
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status))) as http:
        client._send(http, [{"event_id": "one"}])
    assert client.dropped == 1


def test_backend_offline_is_counted(monkeypatch):
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    client = ShieldClient("http://backend.invalid", "key")
    http = Mock()
    http.post.side_effect = httpx.ConnectError("offline")
    client._send(http, [{"event_id": "one"}])
    assert client.dropped == 1


def test_wsgi_stream_redaction_and_cleanup(sink):
    closed = []

    def app(environ, start_response):
        def stream():
            try:
                start_response("201 Created", [])
                yield b"one"
                yield b"two"
            finally:
                closed.append(True)
        return stream()

    sensor = wrap(ShieldWSGIMiddleware, app)
    response = sensor({"PATH_INFO": "/.env", "QUERY_STRING": "password=secret&q=hello",
                       "REMOTE_ADDR": "192.0.2.1", "HTTP_X_FORWARDED_FOR": "spoofed"}, Mock())
    assert not sink.submit.called
    assert list(response) == [b"one", b"two"]
    response.close()
    response.close()
    sink.submit.assert_called_once()
    event = sink.submit.call_args.args[0]
    assert event["status"] == 201
    assert "secret" not in event["query_redacted"]
    assert "q=hello" in event["query_redacted"]
    assert event["ip_hash"] == hash_ip("192.0.2.1", "site-salt")
    assert event["flags"] == ["honeytoken_hit"]
    assert closed == [True]


def test_wsgi_close_before_iteration(sink):
    body = Mock()
    body.__iter__ = Mock(return_value=iter([b"ok"]))
    response = wrap(ShieldWSGIMiddleware, lambda *args: body)({}, Mock())
    response.close()
    body.close.assert_called_once()
    sink.submit.assert_called_once()


def test_wsgi_telemetry_failure_preserves_body(sink):
    sink.submit.side_effect = RuntimeError("sensor failure")
    def app(environ, start_response):
        start_response("200 OK", [])
        return [b"ok"]
    response = wrap(ShieldWSGIMiddleware, app)({}, Mock())
    assert list(response) == [b"ok"]
    response.close()


def test_wsgi_host_exception_is_preserved(sink):
    def app(*args):
        raise ValueError("host failure")
    with pytest.raises(ValueError, match="host failure"):
        wrap(ShieldWSGIMiddleware, app)({}, Mock())
    assert sink.submit.call_args.args[0]["status"] == 500


def test_wsgi_stream_exception_is_preserved(sink):
    def app(environ, start_response):
        start_response("200 OK", [])
        yield b"first"
        raise ValueError("stream failure")
    response = wrap(ShieldWSGIMiddleware, app)({}, Mock())
    assert next(response) == b"first"
    with pytest.raises(ValueError, match="stream failure"):
        next(response)
    response.close()
    sink.submit.assert_called_once()


def test_wsgi_request_body_is_untouched(sink):
    body = Mock()
    def app(environ, start_response):
        start_response("200 OK", [])
        return [b"ok"]
    response = wrap(ShieldWSGIMiddleware, app)({"wsgi.input": body}, Mock())
    assert list(response) == [b"ok"]
    response.close()
    assert body.mock_calls == []
