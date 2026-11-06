import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("shield_load", Path(__file__).resolve().parents[1] / "tools/load_test.py")
load = importlib.util.module_from_spec(spec)
spec.loader.exec_module(load)


def test_mixed_workload_preserves_distribution_across_batches():
    rows = [load.event(i, "mixed") for i in range(1280)]
    assert len({row["event_id"] for row in rows}) == 1280
    assert len({row["ip_hash"] for row in rows}) == 128
    assert sum(row["path"] == "/.env" for row in rows) == 128
    assert sum("union" in row["query_redacted"] for row in rows) == 128
    assert rows[99]["ip_hash"] != rows[100]["ip_hash"]


def test_uniform_profile_remains_the_original_workload():
    row = load.event(1000)
    assert row["path"] == "/benchmark" and row["ip_hash"] == "a" * 64
    assert "query_redacted" not in row
