import importlib.util
from io import BytesIO
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("csic_audit", Path("ml/audit_csic.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def request(target="/product", body=b"", newline=b"\n"):
    return (b"POST " + target.encode() + b" HTTP/1.1" + newline
            + b"Cookie: session=private-fixture-cookie" + newline
            + b"Content-Length: " + str(len(body)).encode() + newline + newline + body + newline + newline)


def test_body_framing_does_not_turn_payload_request_lines_into_records():
    embedded = b"GET /fake HTTP/1.1\n\n"
    rows = list(audit.requests(BytesIO(request(body=embedded) + request("/real", newline=b"\r\n"))))
    assert len(rows) == 2 and [r["target"] for r in rows] == ["/product", "/real"]
    assert rows[0]["body_bytes"] == len(embedded)
    assert "private-fixture-cookie" not in json.dumps(rows)


def test_projection_uses_sdk_redaction_and_omits_body_and_cookie_values():
    row = next(audit.requests(BytesIO(request("http://localhost:8080/%2e%2e/private?pwd=private-fixture-password&q=hello", body=b"private-body"))))
    observed = audit.project(row)
    assert observed["path"] == "/../private"
    assert "private-fixture-password" not in json.dumps(observed)
    assert "private-body" not in json.dumps(observed)
    assert "private-fixture-cookie" not in json.dumps(observed)
    assert "ts" not in observed and "session_id" not in observed and "label" not in observed


@pytest.mark.parametrize("raw", [b"not-http\n", b"GET / HTTP/1.1\n", request(body=b"abc")[:-6],
                                 b"GET / HTTP/1.1\nContent-Length: 1048577\n\n",
                                 b"GET / HTTP/1.1\nContent-Length: " + b"9" * 5000 + b"\n\n",
                                 b"GET / HTTP/1.1\nTransfer-Encoding: chunked\n\n0\n\n"])
def test_unsupported_or_truncated_inputs_fail_closed(raw):
    with pytest.raises(audit.CorpusError):
        list(audit.requests(BytesIO(raw)))


def test_cross_label_observability_collision_is_reported_without_training(tmp_path):
    normal, anomalous = tmp_path / "normal.txt", tmp_path / "anomalous.txt"
    normal.write_bytes(request(body=b"name=ordinary"))
    anomalous.write_bytes(request(body=b"name=UNION SELECT secret"))
    report = audit.audit([("normal", normal), ("anomalous", anomalous)])
    assert report["complete"] and report["release_evidence"] is False and report["model_trained"] is False
    assert report["overlap"]["sdk_path_query_shared_representations"] == 1
    assert report["overlap"]["shared_feature_vectors"] == 1
    assert all(row["empty_query_with_body"] == 1 for row in report["files"])
    assert "UNION SELECT" not in json.dumps(report)
    assert all(row["matching_requests"] == 0 for row in report["files"])
