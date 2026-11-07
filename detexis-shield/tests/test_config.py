from unittest.mock import Mock

import httpx
import pytest

from detexis_shield.client import ShieldClient


@pytest.mark.parametrize("paths,expected", [(["/canary"], frozenset({"/canary"})),
                                            ([], frozenset()), (["https://bad"], None),
                                            (["/bad\r\n"], None), (["/x?y"], None),
                                            (["/x"] * 21, None), ("/not-a-list", None)])
def test_config_validation_and_monitor_only(monkeypatch, paths, expected):
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    sensor = ShieldClient("http://unused.invalid", "key")
    before = sensor.honeytoken_paths
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"mode": "block", "honeytokens": paths}))) as http:
        sensor._sync_config(http)
    assert sensor.honeytoken_paths == (before if expected is None else expected)
    assert not hasattr(sensor, "mode")


def test_config_failure_retains_last_valid_paths(monkeypatch):
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    sensor = ShieldClient("http://unused.invalid", "key")
    sensor.honeytoken_paths = frozenset({"/custom"})
    http = Mock()
    http.get.side_effect = httpx.ConnectError("offline")
    sensor._sync_config(http)
    assert sensor.honeytoken_paths == frozenset({"/custom"})
