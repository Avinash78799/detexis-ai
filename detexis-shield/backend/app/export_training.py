"""Export explicitly labeled, tenant-scoped requests. No automatic attack labels."""
import argparse
import json
from pathlib import Path

from sqlalchemy import select
from .db import SessionLocal
from .models import Event
from .worker import utc


def export(site_id, labels, dataset, output):
    count = 0
    with SessionLocal() as db, Path(output).open("x", encoding="utf-8") as stream:
        for row in db.scalars(select(Event).where(Event.site_id == site_id).order_by(Event.received_at)):
            if row.event_id not in labels:
                continue
            label = labels[row.event_id]
            if type(label) is not int or label not in (0, 1):
                raise ValueError("labels must be reviewed integers 0 or 1")
            record = {"path": row.path, "query_redacted": row.query_redacted, "ts": utc(row.received_at).isoformat(),
                      "session_id": row.ip_hash, "dataset": dataset, "label": label,
                      "provenance": "operator-reviewed site telemetry"}
            stream.write(json.dumps(record) + "\n")
            count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("site_id")
    parser.add_argument("labels", type=Path)
    parser.add_argument("dataset")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(export(args.site_id, json.loads(args.labels.read_text()), args.dataset, args.output))
