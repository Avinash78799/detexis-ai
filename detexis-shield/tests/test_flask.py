import sys
from unittest.mock import Mock

import pytest
from flask import Flask, Response, request

sys.path.insert(0, "sensor-sdk")
from detexis_shield import ShieldWSGIMiddleware


@pytest.fixture
def monitored_app(monkeypatch):
    sink = Mock()
    monkeypatch.setattr("detexis_shield.middleware.ShieldClient", lambda *a, **k: sink)
    app = Flask(__name__)
    app.testing = True
    app.wsgi_app = ShieldWSGIMiddleware(app.wsgi_app, "http://unused.invalid", "key", "salt")

    @app.post("/echo")
    def echo():
        return request.get_data(), 201

    @app.get("/stream")
    def stream():
        return Response(iter([b"one", b"two"]))

    @app.get("/failure")
    def failure():
        raise ValueError("host exception")

    return app, sink


def test_flask_post_body_status_and_redaction(monitored_app):
    app, sink = monitored_app
    with app.test_client() as client:
        response = client.post("/echo?password=hidden&q=hello", data=b"untouched body")
        assert response.status_code == 201
        assert response.data == b"untouched body"
        response.close()
    sink.submit.assert_called_once()
    event = sink.submit.call_args.args[0]
    assert event["method"] == "POST"
    assert event["status"] == 201
    assert "hidden" not in event["query_redacted"]
    assert "q=hello" in event["query_redacted"]
    assert event["features"]["schema_version"] == 1
    assert event["features"]["num_params"] == 2
    assert event["features"]["path_depth"] == 1


def test_flask_unicode_path_matches_stored_features(monitored_app):
    app, sink = monitored_app
    with app.test_client() as client:
        response = client.get("/café?q=hello")
        assert response.status_code == 404
        response.get_data()
        response.close()
    event = sink.submit.call_args.args[0]
    assert event["path"] == "/café"
    assert event["features"]["payload_len"] == len("/café?q=hello".encode("utf-8"))


def test_flask_stream_survives_sensor_failure(monitored_app):
    app, sink = monitored_app
    sink.submit.side_effect = RuntimeError("telemetry failed")
    with app.test_client() as client:
        response = client.get("/stream")
        assert response.data == b"onetwo"
        response.close()
    sink.submit.assert_called_once()


def test_flask_host_exception_is_not_swallowed(monitored_app):
    app, sink = monitored_app
    with app.test_client() as client:
        with pytest.raises(ValueError, match="host exception"):
            client.get("/failure")
    assert sink.submit.call_args.args[0]["status"] == 500
