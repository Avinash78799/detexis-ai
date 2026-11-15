"""Migration acceptance in a disposable SQLite DB; real PostgreSQL runs in CI."""
import os
import sqlite3
import subprocess
import sys


def test_health_migration_preserves_existing_sites_and_enforces_one_open_gap(tmp_path):
    path = tmp_path / "health-migration.db"
    env = {**os.environ,"DATABASE_URL":"sqlite:///"+path.as_posix()}
    def migrate(target):
        direction = "downgrade" if target == "0008" and path.exists() else "upgrade"
        result = subprocess.run([sys.executable,"-m","alembic","-c","backend/alembic.ini",direction,target],
                                env=env,capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
    migrate("0008")
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO sites (id,domain,mode,created_at,honeytokens,settings) VALUES (?,?,?,?,?,?)",
                   ("migration-fixture","migration.example","monitor","2026-11-15 00:00:00","[]","{}"))
        db.execute("INSERT INTO api_keys (site_id,prefix,key_hash,revoked) VALUES (?,?,?,?)",("migration-fixture","fixture","a"*64,0))
    migrate("0009")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT domain FROM sites WHERE id='migration-fixture'").fetchone() == ("migration.example",)
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0009",)
        assert db.execute("SELECT created_at FROM api_keys WHERE prefix='fixture'").fetchone()[0]
        fields = ("gap-one","migration-fixture","2026-11-15 00:00:00","2026-11-14 23:55:00")
        statement = "INSERT INTO sensor_health_alerts (id,site_id,opened_at,heartbeat_at) VALUES (?,?,?,?)"
        db.execute(statement,fields); db.commit()
        try:
            db.execute(statement,("gap-duplicate",*fields[1:]))
        except sqlite3.IntegrityError:
            db.rollback()
        else:
            raise AssertionError("Two open gaps were accepted for one site")
        db.execute("UPDATE sensor_health_alerts SET resolved_at='2026-11-15 00:01:00' WHERE id='gap-one'")
        db.execute(statement,("gap-two",*fields[1:])); db.commit()
    # This intentionally discards only this disposable fixture's health history.
    migrate("0008")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT domain FROM sites WHERE id='migration-fixture'").fetchone() == ("migration.example",)
        assert db.execute("SELECT name FROM sqlite_master WHERE name='sensor_health_alerts'").fetchone() is None
        assert db.execute("SELECT key_hash FROM api_keys WHERE prefix='fixture'").fetchone() == ("a"*64,)
