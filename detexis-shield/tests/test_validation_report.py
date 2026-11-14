import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("validation_runner", Path(__file__).resolve().parents[1] / "tools/validate_stack.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_checkpoint_is_incomplete_and_can_be_replaced_by_final_result(tmp_path):
    target = tmp_path / "reports" / "result.json"
    runner.write_report(target, {"state": "running", "site_id": "synthetic"})
    assert "acceptance_passed" not in json.loads(target.read_text())
    runner.write_report(target, {"state": "completed", "acceptance_passed": False})
    assert json.loads(target.read_text()) == {"state": "completed", "acceptance_passed": False}


def test_failed_snapshot_does_not_truncate_previous_report(tmp_path):
    target = tmp_path / "result.json"
    original = {"state": "running", "received": 100}
    runner.write_report(target, original)
    with pytest.raises(TypeError):
        runner.write_report(target, {"bad": object()})
    assert json.loads(target.read_text()) == original
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("url", ["https://example.com", "http://localhost:18000", "http://user:secret@127.0.0.1:18000", "http://127.0.0.1:18000/path", "http://127.0.0.1:18000?token=x"])
def test_validation_refuses_non_loopback_or_decorated_origin(monkeypatch, url):
    monkeypatch.setattr(runner, "BASE_URL", url)
    monkeypatch.setattr(runner, "docker", lambda *args: pytest.fail("Must reject before Docker or HTTP"))
    with pytest.raises(ValueError, match="plain HTTP loopback"):
        runner.validate_target()


def test_validation_port_must_belong_to_its_compose_project(monkeypatch):
    monkeypatch.setattr(runner, "BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(runner, "docker", lambda *args: "127.0.0.1:18000\n")
    with pytest.raises(ValueError, match="dedicated Compose project"):
        runner.validate_target()
    monkeypatch.setattr(runner, "BASE_URL", "http://127.0.0.1:18000")
    runner.validate_target()


def test_ingest_capacity_does_not_pass_without_actual_rule_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "counters", lambda site: {"total":103,"pending":0})
    monkeypatch.setattr(runner, "processing_metrics", lambda site: {"lag_p95_seconds":1,"failed_jobs":0,"queued_jobs":0})
    def evidence_probe(*args):
        # The exact generated subprocess source must be executable Python.
        compile(args[args.index("-c")+1], "<generated-probe>", "exec")
        return json.dumps({"matching_release_events":103,"sqli_union_events":0})
    monkeypatch.setattr(runner, "docker", evidence_probe)
    args = SimpleNamespace(rate=100,seconds=1,profile="mixed_comments",max_processing_p95_seconds=10,output=tmp_path / "result.json")
    report = {"accepted":100,"failed":0,"elapsed_seconds":1,"runtime_details":{"detection_release":{"rules_source_sha256":"fixture"}}}
    with pytest.raises(SystemExit):
        runner.complete_measurement(args, report, "synthetic-site")
    result = json.loads(args.output.read_text())
    assert result["capacity_passed"] and result["latency_target_passed"]
    assert not result["rules_evidence_passed"] and not result["acceptance_passed"]
