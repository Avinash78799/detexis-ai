"""Check the incident order migration against an existing incident record."""
import os
import sqlite3
import subprocess
import sys


def test_incident_order_upgrade_preserves_historical_correlations(tmp_path):
    path = tmp_path / "incident-order.db"
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + path.as_posix()}

    def migrate(direction, revision):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", direction, revision],
            env=env, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr

    migrate("upgrade", "0009")
    with sqlite3.connect(path) as db:
        stamp = "2026-11-24 08:00:00"
        db.execute("INSERT INTO sites (id, domain, mode, created_at) VALUES (?, ?, ?, ?)",
                   ("fixture-site", "migration.example", "monitor", stamp))
        db.execute("""INSERT INTO incidents (id, site_id, ip_hash, bucket, severity, rules,
                          correlations, event_count, first_seen, last_seen)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   ("fixture-incident", "fixture-site", "a" * 64, 1, "high", '["honeytoken", "xss"]',
                    '["recon_to_exploit"]', 2, stamp, stamp))
        previous = db.execute("SELECT * FROM incidents").fetchone()

    migrate("upgrade", "0010")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM incidents").fetchone() == (*previous, None, None)

    migrate("upgrade", "0011")
    with sqlite3.connect(path) as db:
        indexes = db.execute("PRAGMA index_list(incidents)").fetchall()
        assert any(index[1] == "ix_incidents_workspace_attention" and index[4] for index in indexes)
        assert db.execute("SELECT * FROM incidents").fetchone() == (*previous, None, None)

    migrate("downgrade", "0009")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM incidents").fetchone() == previous
