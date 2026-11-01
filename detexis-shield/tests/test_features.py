import asyncio
import json
import sys
from unittest.mock import Mock
from urllib.parse import parse_qsl

import pytest

sys.path.insert(0, "sensor-sdk")
from detexis_shield import ShieldMiddleware, ShieldWSGIMiddleware
from detexis_shield.features import extract_features
from detexis_shield.redact import redact_query


def test_known_url_features():
    assert extract_features("/a", "q=%3C%3E") == {
        "schema_version": 1, "payload_len": 11, "special_char_ratio": .6,
        "num_params": 1, "path_depth": 1,
    }


@pytest.mark.parametrize("path,depth", [("", 0), ("/", 0), ("///", 0),
                                         ("/a/b/", 2), ("/a//b", 2), ("/café", 1)])
def test_path_depth_counts_nonempty_segments(path, depth):
    features = extract_features(path, "")
    assert features["path_depth"] == depth
    assert features["payload_len"] == len(path.encode("utf-8"))
    assert 0 <= features["special_char_ratio"] <= 1


def test_empty_request_has_no_division_by_zero():
    assert extract_features("", "") == {
        "schema_version": 1, "payload_len": 0, "special_char_ratio": 0,
        "num_params": 0, "path_depth": 0,
    }


def test_query_values_keep_parameter_boundaries():
    query = redact_query("q=a%26b%3Dc&tag=one&tag=two&blank=&flag")
    assert parse_qsl(query, keep_blank_values=True) == [
        ("q", "a&b=c"), ("tag", "one"), ("tag", "two"), ("blank", ""), ("flag", ""),
    ]
    assert extract_features("/", query)["num_params"] == 5


def test_redaction_precedes_features_and_masks_encoded_case_insensitive_keys():
    first = redact_query("%50aSsWoRd=short&q=hello")
    second = redact_query("%50aSsWoRd=%3Cscript%3E%26reallylongsecret&q=hello")
    assert first == second
    assert extract_features("/login", first) == extract_features("/login", second)
    assert dict(parse_qsl(first))["PaSsWoRd"] == "[REDACTED]"


def test_redaction_marker_is_not_a_punctuation_signal():
    masked = redact_query("password=secret")
    assert extract_features("/a", masked)["special_char_ratio"] == extract_features("/a", "password=")["special_char_ratio"]


def test_percent_decoding_happens_once_for_query_values():
    assert parse_qsl(redact_query("q=%2527")) == [("q", "%27")]
    # Feature text is /q%27: two punctuation characters out of five.
    assert extract_features("/", redact_query("q=%2527"))["special_char_ratio"] == .4


def test_unicode_letters_are_not_special_characters():
    assert extract_features("/café", "")["special_char_ratio"] == .2


def test_query_processing_and_stored_features_are_bounded():
    query = redact_query("&".join("a=x" for _ in range(10000)))
    assert len(query) <= 1024
    assert extract_features("/", query)["num_params"] == 50
    large = extract_features("/a" * 5000, "q=" + "x" * 10000)
    assert large["payload_len"] == 2048 + 1 + 1024


def test_malformed_escapes_do_not_break_features():
    features = extract_features("/", redact_query("q=%ZZ%FF&empty="))
    assert features["num_params"] == 2
    assert 0 <= features["special_char_ratio"] <= 1


def test_asgi_and_wsgi_emit_identical_reproducible_features(monkeypatch):
    sink = Mock()
    monkeypatch.setattr("detexis_shield.middleware.ShieldClient", lambda *a, **k: sink)
    query = b"q=a%26b%3Dc&password=secret&tag=one&tag=two"

    async def asgi(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(message):
        pass

    async def unread_receive():
        raise AssertionError("sensor read a request body")

    asgi_sensor = ShieldMiddleware(asgi, "http://unused.invalid", "key", "salt")
    asyncio.run(asgi_sensor({"type": "http", "method": "GET", "path": "/café",
                             "query_string": query}, unread_receive, send))

    def wsgi(environ, start_response):
        start_response("200 OK", [])
        return [b"ok"]

    wsgi_sensor = ShieldWSGIMiddleware(wsgi, "http://unused.invalid", "key", "salt")
    body = Mock()
    response = wsgi_sensor({"PATH_INFO": "/café".encode("utf-8").decode("latin-1"),
                            "QUERY_STRING": query.decode("ascii"), "wsgi.input": body}, Mock())
    assert list(response) == [b"ok"]
    response.close()
    events = [call.args[0] for call in sink.submit.call_args_list]
    assert len(events) == 2
    assert events[0]["path"] == events[1]["path"] == "/café"
    assert events[0]["query_redacted"] == events[1]["query_redacted"]
    assert events[0]["features"] == events[1]["features"]
    for event in events:
        # Simulate worker/training reconstruction from a stored JSON event.
        stored = json.loads(json.dumps(event))
        assert stored["features"] == extract_features(stored["path"], stored["query_redacted"])
        assert "secret" not in json.dumps(stored)
    assert body.mock_calls == []
