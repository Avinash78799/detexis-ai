import copy
import importlib.util
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Event
from app.rule_manifest import manifest, release_record
from app.rules import RULES, RULESET_RELEASE, RULESET_VERSION
from app.worker import process_batch
from test_accounts import register
from test_pipeline import seed
from test_smoke import make_site

spec = importlib.util.spec_from_file_location("rule_release_gate", Path("tools/validate_rule_release.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_release_manifest_authentication_and_sensor_config_agree(monkeypatch):
    monkeypatch.delenv("SHIELD_MODEL_DIR", raising=False)
    site_id, key = make_site("manifest-fixture.test")
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/app/api/detection").status_code == 401
        navigate = client.get("/app/detection", headers={"Accept":"text/html"}, follow_redirects=False)
        assert navigate.status_code == 303
        assert navigate.headers["location"] == "/app?next=%2Fapp%2Fdetection"
        register(client, "manifest-owner")
        value = client.get("/app/api/detection").json()
        config = client.get("/v1/config", headers={"X-API-Key":key}).json()
        assert value["release_record_verified"] is True
        assert {item["id"] for item in value["rules"]} == set(RULES)
        assert value["mode"] == config["mode"] == "monitor"
        assert value["rules_version"] == config["rules_version"] == RULESET_VERSION
        assert value["rules_source_sha256"] == config["rules_source_sha256"]
        page = client.get("/app/detection")
        assert page.status_code == 200 and page.headers["Cache-Control"] == "no-store"
        assert RULESET_RELEASE in page.text
        assert "A live web-rule update feed is not connected" in page.text
        assert "classifier is disabled" in page.text


def test_worker_stamps_actual_release_on_both_matched_and_unmatched_events(isolated_redis):
    site, _ = make_site("manifest-worker.test")
    clean = seed(site, "/normal", features={"rules_release":"forged", "rules_source_sha256":"fake"})
    attack = seed(site, "/search", query_redacted=urlencode({"q":"UNION/**/SELECT name"}))
    assert process_batch(site, [clean, attack], isolated_redis) == 2
    with SessionLocal() as db:
        for event_id in (clean, attack):
            row = db.get(Event, (event_id, site))
            assert row.features["rules_release"] == RULESET_RELEASE
            assert row.features["rules_source_sha256"] == manifest()["rules_source_sha256"]
        assert db.get(Event, (attack, site)).findings[0]["rules_release"] == RULESET_RELEASE
        assert db.get(Event, (clean, site)).findings == []


def test_release_gate_rejects_rewriting_a_published_record_or_unversioned_source():
    current, record = manifest(), release_record()
    gate.verify(current, record, old_source="RULESET_VERSION = 1\n")
    with pytest.raises(ValueError, match="higher rules_version"):
        gate.verify(current, record, old_source="RULESET_VERSION = 2\n# different detector\n")
    previous_record = copy.deepcopy(record)
    previous_record["changes"] = ["different historical release record"]
    with pytest.raises(ValueError, match="immutable"):
        gate.verify(current, record, old_record=previous_record)
    with pytest.raises(ValueError, match="does not match"):
        gate.verify({**current,"release_record_verified":False}, record)


def test_previous_source_is_parsed_without_executing_it(tmp_path):
    marker = tmp_path / "must-not-be-created"
    source = "RULESET_VERSION = 1\nopen(" + repr(str(marker)) + ", 'w').write('bad')\n"
    assert gate.previous_version(source) == 1
    assert not marker.exists()
