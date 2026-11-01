import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("shield_training", Path("ml/train.py"))
training = importlib.util.module_from_spec(spec)
spec.loader.exec_module(training)


def records(count=100):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [{"path": "/", "query_redacted": "", "ts": (start + timedelta(minutes=i)).isoformat(),
             "session_id": str(i), "dataset": "primary", "label": i % 2} for i in range(count)]


def test_temporal_split_has_no_session_overlap_and_purges_spanning_sessions():
    rows = records()
    rows[0]["session_id"] = rows[-1]["session_id"] = "spanning"
    rows += [{**rows[0], "dataset": "cross"}]
    fit, cal, test, cross, audit = training.prepare(rows, "cross")
    assert not {r["session_id"] for r in fit} & {r["session_id"] for r in test}
    assert max(r["_time"] for r in fit) < min(r["_time"] for r in cal)
    assert max(r["_time"] for r in cal) < min(r["_time"] for r in test)
    assert audit["purged_session_rows"] == 2
    assert audit["duplicate_request_overlap"]


def test_small_benign_sample_cannot_claim_one_percent_fpr():
    with pytest.raises(ValueError, match="insufficient"):
        training.choose_threshold([0] * 20, [.1] * 20, .01)


def test_threshold_selected_from_benign_fpr_confidence_bound():
    labels = [0] * 1000 + [1] * 100
    probabilities = [.1] * 1000 + [.9] * 100
    threshold = training.choose_threshold(labels, probabilities, .01)
    result = training.metrics(labels, probabilities, threshold)
    assert result["fp"] == 0
    assert result["fpr_upper_95"] < .01
    assert result["recall"] == 1


def test_rejected_artifact_is_not_loaded(tmp_path, monkeypatch):
    import json
    from app.ml_runtime import classify
    (tmp_path / "metadata.json").write_text(json.dumps({"schema_version": 99}))
    monkeypatch.setenv("SHIELD_MODEL_DIR", str(tmp_path))
    assert classify({}) is None


def test_logistic_pipeline_artifact_and_runtime_on_controlled_fixture(tmp_path, monkeypatch):
    # This is a software test, not evidence of real-world classifier performance.
    rows = records(2000)
    for index, row in enumerate(rows):
        row["label"] = int(index % 5 == 0)
        row["path"] = "/../../private/secret" if row["label"] else "/home"
        row["query_redacted"] = "q=%3Cscript%3E" if row["label"] else "q=hello"
    rows += [{**row, "dataset": "independent-fixture"} for row in rows[:500]]
    metadata = training.train(rows, tmp_path / "artifact", "independent-fixture", target_fpr=.05)
    assert metadata["evaluation_status"] == "validated"
    assert (tmp_path / "artifact/model.joblib").is_file()
    from app.ml_runtime import classify
    from detexis_shield.features import extract_features
    monkeypatch.setenv("SHIELD_MODEL_DIR", str(tmp_path / "artifact"))
    assert classify(extract_features("/home", "q=hello"))["alert"] is False
    assert classify(extract_features("/../../private/secret", "q=%3Cscript%3E"))["alert"] is True


def test_nonfinite_model_probability_falls_back_to_rules(monkeypatch):
    from unittest.mock import Mock
    from app.ml_runtime import classify
    model = Mock()
    model.predict_proba.return_value = [[0, float("nan")]]
    monkeypatch.setenv("SHIELD_MODEL_DIR", "unit-test-invalid-model")
    monkeypatch.setattr("app.ml_runtime.load_model", lambda path: (model, {"threshold": .5}))
    assert classify({name: 0 for name in training.NAMES}) is None
