from pathlib import Path
import yaml


def test_scanner_has_no_datastore_network_or_credentials_or_public_port():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    scanner = compose["services"]["scanner"]
    assert "control" not in scanner["networks"]
    assert "environment" not in scanner
    assert "ports" not in scanner
    assert scanner["read_only"] is True
    assert scanner["cap_drop"] == ["ALL"]
    assert compose["networks"]["control"]["internal"] is True
    for service in ("db", "redis", "api"):
        assert all(port.startswith("127.0.0.1:") for port in compose["services"][service]["ports"])
