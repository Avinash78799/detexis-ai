"""Export explicitly labeled, tenant-scoped requests. No automatic attack labels."""
import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from detexis_shield.redact import redact_query
from sqlalchemy import select
from .db import SessionLocal
from .models import Event
from .schemas import MAX_INGEST_QUERY_LENGTH
from .worker import utc

EXPORT_BATCH_SIZE = 500


def read_labels(path):
    def unique_object(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("review labels contain duplicate event IDs")
        return result

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def check_labels(labels):
    if not isinstance(labels, dict) or not labels:
        raise ValueError("provide a nonempty object mapping reviewed event IDs to labels")
    for event_id, label in labels.items():
        try:
            canonical = str(UUID(event_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("event IDs must be canonical UUID strings") from None
        if event_id != canonical:
            raise ValueError("event IDs must be canonical UUID strings")
        if type(label) is not int or label not in (0, 1):
            raise ValueError("labels must be reviewed integers 0 or 1")


def export(site_id, labels, dataset, output):
    check_labels(labels)
    if not isinstance(dataset, str) or not dataset.strip():
        raise ValueError("dataset name must identify the reviewed source")
    ordered_ids = list(labels)
    rows = []
    with SessionLocal() as db:
        for start in range(0, len(ordered_ids), EXPORT_BATCH_SIZE):
            batch = ordered_ids[start:start + EXPORT_BATCH_SIZE]
            rows.extend(db.execute(select(Event.event_id, Event.received_at, Event.path,
                                          Event.query_redacted, Event.ip_hash)
                        .where(Event.site_id == site_id, Event.event_id.in_(batch))).all())
    if len(rows) != len(labels):
        raise ValueError("some reviewed events are missing from the selected site; no dataset was exported")

    rows.sort(key=lambda row: (utc(row.received_at), row.event_id))
    with open(output, "x", encoding="utf-8", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
        for row in rows:
            record = {"path": row.path,
                      "query_redacted": redact_query(row.query_redacted, max_len=MAX_INGEST_QUERY_LENGTH),
                      "ts": utc(row.received_at).isoformat(), "session_id": row.ip_hash,
                      "dataset": dataset, "label": labels[row.event_id],
                      "provenance": "operator-reviewed site telemetry"}
            stream.write(json.dumps(record) + "\n")
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("site_id")
    parser.add_argument("labels", type=Path)
    parser.add_argument("dataset")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        print(export(args.site_id, read_labels(args.labels), args.dataset, args.output))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Export failed: {exc}\n")
