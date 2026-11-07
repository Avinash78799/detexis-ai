import importlib.util
import json
from pathlib import Path

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
