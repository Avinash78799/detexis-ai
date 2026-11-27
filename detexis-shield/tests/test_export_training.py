import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app import export_training
from test_pipeline import seed
from test_smoke import make_site


def test_export_reads_reviewed_site_events_in_time_order_and_redacts_legacy_query(tmp_path, monkeypatch):
    site, _ = make_site("training-export.example.test")
    foreign, _ = make_site("training-foreign.example.test")
    stamp = datetime.now(timezone.utc)
    newest = seed(site, "/recent", received_at=stamp, query_redacted="q=fixture&auth.token=old-private-value")
    older = seed(site, "/earlier", received_at=stamp - timedelta(minutes=1))
    seed(site, "/unreviewed", received_at=stamp)
    seed(foreign, "/other-tenant", event_id=newest, received_at=stamp)
    monkeypatch.setattr(export_training, "EXPORT_BATCH_SIZE", 1)
    output = tmp_path / "training.jsonl"

    assert export_training.export(site, {newest: 1, older: 0}, "reviewed-fixture", output) == 2
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [record["path"] for record in records] == ["/earlier", "/recent"]
    assert [record["label"] for record in records] == [0, 1]
    assert all(record["dataset"] == "reviewed-fixture" for record in records)
    assert records[1]["query_redacted"] == "q=fixture&auth.token=%5BREDACTED%5D"
    assert "old-private-value" not in output.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_training.export(site, {older: 0}, "reviewed-fixture", output)
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_mixed_site_review_batch_is_rejected_without_partial_output(tmp_path):
    site, _ = make_site("training-scope.example.test")
    foreign, _ = make_site("training-scope-foreign.example.test")
    reviewed = seed(site, "/mine")
    unavailable = seed(foreign, "/unavailable")
    output = tmp_path / "training.jsonl"

    with pytest.raises(ValueError, match="missing from the selected site"):
        export_training.export(site, {reviewed: 0, unavailable: 1}, "scope", output)
    assert not output.exists()


@pytest.mark.parametrize("labels", [{}, {str(uuid4()): True}, {str(uuid4()): "0"}, {"missing": 0}])
def test_invalid_labels_are_rejected_without_creating_an_output(tmp_path, labels):
    output = tmp_path / "training.jsonl"
    with pytest.raises(ValueError):
        export_training.export("fixture-site", labels, "reviewed", output)
    assert not output.exists()


def test_duplicate_input_labels_cannot_silently_override_a_review(tmp_path):
    event = str(uuid4())
    labels = tmp_path / "labels.json"
    labels.write_text(f'{{"{event}": 0, "{event}": 1}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate event IDs"):
        export_training.read_labels(labels)
