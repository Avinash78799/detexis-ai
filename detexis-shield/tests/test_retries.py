import json
import sys
import threading
from unittest.mock import Mock

import httpx
import pytest

sys.path.insert(0, "sensor-sdk")
from detexis_shield.client import ShieldClient, retry_after_seconds


@pytest.fixture
def sender(monkeypatch):
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    client = ShieldClient("http://backend.invalid", "key")
    client._stop.wait = Mock(return_value=False)
    monkeypatch.setattr("detexis_shield.client.random.uniform", lambda low, high: high)
    return client


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_response_then_success_keeps_payload(sender, status):
    payloads = []

    def handle(request):
        payloads.append(request.content)
        return httpx.Response(status if len(payloads) == 1 else 202)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        sender._send(http, [{"event_id": "stable-id"}])
    assert len(payloads) == 2 and payloads[0] == payloads[1]
    assert json.loads(payloads[0])["events"][0]["event_id"] == "stable-id"
    assert sender.dropped == 0
    sender._stop.wait.assert_called_once_with(0.25)


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError])
def test_transport_failure_then_success(sender, failure):
    http = Mock()
    http.post.side_effect = [failure("temporary"), httpx.Response(202)]
    sender._send(http, [{"event_id": "stable-id"}])
    assert http.post.call_count == 2
    assert sender.dropped == 0


def test_retry_budget_and_exponential_waits(sender):
    http = Mock()
    http.post.return_value = httpx.Response(503)
    sender._send(http, [{"event_id": "one"}, {"event_id": "two"}])
    assert http.post.call_count == 3
    assert [call.args[0] for call in sender._stop.wait.call_args_list] == [0.25, 0.5]
    assert sender.dropped == 2


def test_backoff_is_capped(sender):
    sender.max_retries = 5
    http = Mock()
    http.post.return_value = httpx.Response(503)
    sender._send(http, [{}])
    assert http.post.call_count == 6
    assert [call.args[0] for call in sender._stop.wait.call_args_list] == [0.25, 0.5, 1, 2, 2]


@pytest.mark.parametrize("status", [301, 400, 401, 403, 404, 413, 422, 501])
def test_permanent_response_is_not_retried(sender, status):
    http = Mock()
    http.post.return_value = httpx.Response(status)
    sender._send(http, [{}])
    http.post.assert_called_once()
    sender._stop.wait.assert_not_called()
    assert sender.dropped == 1


def test_invalid_url_is_not_retried(sender):
    http = Mock()
    http.post.side_effect = httpx.InvalidURL("bad configuration")
    sender._send(http, [{}])
    http.post.assert_called_once()
    assert sender.dropped == 1


@pytest.mark.parametrize("header, expected_calls, expected_delay", [("1", 2, 1), ("120", 1, None), ("garbage", 2, .25)])
def test_retry_after_policy(sender, header, expected_calls, expected_delay):
    http = Mock()
    http.post.side_effect = [httpx.Response(429, headers={"Retry-After": header}), httpx.Response(202)]
    sender._send(http, [{}])
    assert http.post.call_count == expected_calls
    if expected_delay is None:
        sender._stop.wait.assert_not_called()
        assert sender.dropped == 1
    else:
        sender._stop.wait.assert_called_once_with(expected_delay)
        assert sender.dropped == 0


def test_retry_after_date(monkeypatch):
    monkeypatch.setattr("detexis_shield.client.time.time", lambda: 0)
    assert retry_after_seconds("Thu, 01 Jan 1970 00:00:02 GMT") == 2
    assert retry_after_seconds("Thu, 01 Jan 1970 00:00:00 GMT") == 0
    assert retry_after_seconds("-5") == 0


def test_shutdown_during_backoff_prevents_another_attempt(sender):
    sender._stop.wait.return_value = True
    http = Mock()
    http.post.return_value = httpx.Response(503)
    sender._send(http, [{}])
    http.post.assert_called_once()
    assert sender.dropped == 1


def test_shutdown_before_send_skips_network(sender):
    sender._stop.set()
    http = Mock()
    sender._send(http, [{}])
    http.post.assert_not_called()
    assert sender.dropped == 1


def test_unserializable_batch_drops_once_without_network(sender):
    circular = {}
    circular["self"] = circular
    http = Mock()
    sender._send(http, [circular])
    http.post.assert_not_called()
    assert sender.dropped == 1


@pytest.mark.parametrize("options", [{"max_retries": -1}, {"max_retries": 6},
                                     {"max_retries": 1.5}, {"max_retries": True},
                                     {"flush_interval": float("nan")},
                                     {"flush_interval": float("inf")}])
def test_unbounded_or_invalid_retry_settings_rejected(options):
    with pytest.raises(ValueError):
        ShieldClient("http://backend.invalid", "key", **options)


def test_close_interrupts_worker_and_accounts_for_queued_events(monkeypatch):
    original_client = httpx.Client
    waiting = threading.Event()
    attempts = []

    def handle(request):
        attempts.append(request.content)
        return httpx.Response(503)

    monkeypatch.setattr("detexis_shield.client.httpx.Client",
                        lambda **kw: original_client(transport=httpx.MockTransport(handle), **kw))
    client = ShieldClient("http://backend.invalid", "key", batch_size=1)
    original_wait = client._stop.wait

    def wait(delay):
        waiting.set()
        # A long simulated backoff makes interruption independent of timing luck.
        return original_wait(30)

    client._stop.wait = wait
    try:
        client.submit({"event_id": "in-flight"})
        assert waiting.wait(2), "worker did not enter backoff"
        client.submit({"event_id": "queued-one"})
        client.submit({"event_id": "queued-two"})
        client.close()
        assert not client._thread.is_alive()
        assert len(attempts) == 1
        assert client.q.empty()
        assert client.dropped == 3
        client.submit({"event_id": "after-close"})
        client.close()  # idempotent
        assert client.dropped == 4
    finally:
        client.close()


def test_sender_startup_failure_drops_buffer_and_rejects_new_events(monkeypatch):
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    client = ShieldClient("http://backend.invalid", "key")
    client.submit({"event_id": "queued"})
    monkeypatch.setattr("detexis_shield.client.httpx.Client", Mock(side_effect=RuntimeError("startup failed")))
    client._run()
    assert client.q.empty()
    assert client.dropped == 1
    client.submit({"event_id": "later"})
    assert client.dropped == 2


def test_shutdown_discards_partial_batch_without_sending(sender, monkeypatch):
    original_get = sender.q.get

    def get_then_stop(*args, **kwargs):
        item = original_get(*args, **kwargs)
        sender._stop.set()
        return item

    monkeypatch.setattr(sender.q, "get", get_then_stop)
    factory = Mock()
    http = Mock()
    factory.return_value.__enter__ = Mock(return_value=http)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("detexis_shield.client.httpx.Client", factory)
    sender.submit({"event_id": "partial-batch"})
    sender.submit({"event_id": "queued"})
    sender._run()
    http.post.assert_not_called()
    assert sender.q.empty()
    assert sender.dropped == 2
