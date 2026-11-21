"""Restore a stopped synthetic shield-perf-* database without changing its rows.

Uses new database names and private host-copy dumps. Never attaches an API,
worker or delivery process. A second round trip tests seeded heartbeat history
in the isolated copy. This is not off-device disaster recovery or failover.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import uuid


def docker(*args, input=None):
    result = subprocess.run(["docker", *args], input=input, text=True,
                            capture_output=True, timeout=300)
    if result.returncode:
        # SQL/COPY output and restored authentication verifiers stay private.
        raise RuntimeError("Docker/database command failed; private artifacts are retained")
    return result.stdout.strip()


def validate_fixture(project, containers):
    if not re.fullmatch(r"shield-perf-[a-z0-9-]+", project):
        raise ValueError("Only synthetic shield-perf-* projects are allowed")
    databases = []
    for item in containers:
        labels = item["Config"]["Labels"]
        if labels.get("com.docker.compose.project") != project:
            raise ValueError("Container does not belong to the requested fixture")
        if labels.get("com.docker.compose.service") == "db":
            databases.append(item)
        if item["State"]["Running"]:
            raise ValueError("Stop every fixture container before rehearsal")
    if len(databases) != 1:
        raise ValueError("Expected exactly one stopped fixture database")
    return databases[0]["Id"]


def sql(container, database, statement):
    return docker("exec", "-i", "-e", "PGOPTIONS=-c timezone=UTC", container,
                  "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "detexis",
                  "-d", database, input=statement)


def fingerprint(container, database):
    tables = sql(container, database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;").splitlines()
    result = {}
    for table in tables:
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", table):
            raise RuntimeError("Unexpected table identifier")
        # Stream deterministic complete rows into a digest; never print row data.
        statement = f'COPY (SELECT row_to_json(t)::text FROM public."{table}" t ORDER BY row_to_json(t)::text COLLATE "C") TO STDOUT;'
        process = subprocess.Popen(["docker", "exec", "-i", "-e", "PGOPTIONS=-c timezone=UTC", container,
                                    "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "detexis",
                                    "-d", database], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        process.stdin.write(statement.encode())
        process.stdin.close()
        digest = hashlib.sha256()
        count = 0
        for row in process.stdout:
            digest.update(row)
            count += 1
        process.stdout.close()
        if process.wait(timeout=300):
            raise RuntimeError("Complete-row fingerprint failed")
        result[table] = {"rows": count, "sha256": digest.hexdigest()}
    return result


def backup_restore(container, source, target, folder):
    # No --clean, dropdb, overwrite or original-database restore is permitted.
    host_dump = folder / (target + ".dump")
    remote_dump = "/tmp/" + target + ".dump"
    if host_dump.exists():
        raise RuntimeError("Refusing an existing dump filename")
    before = fingerprint(container, source)
    metadata_query = """
SELECT json_build_object(
 'constraints',(SELECT json_agg(x ORDER BY x::text) FROM
   (SELECT conrelid::regclass::text AS relation,conname,pg_get_constraintdef(oid) AS definition
    FROM pg_constraint WHERE connamespace='public'::regnamespace) x),
 'indexes',(SELECT json_agg(x ORDER BY x::text) FROM
   (SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public') x),
 'sequences',(SELECT json_agg(x ORDER BY x::text) FROM
   (SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public') x));
"""
    metadata = sql(container, source, metadata_query)
    docker("exec", container, "pg_dump", "-U", "detexis", "-d", source, "-Fc", "-f", remote_dump)
    docker("cp", container + ":" + remote_dump, str(host_dump))
    if not host_dump.is_file() or not host_dump.stat().st_size:
        raise RuntimeError("Host dump copy is missing or empty")
    imported = remote_dump + ".host-copy"
    docker("cp", str(host_dump), container + ":" + imported)
    docker("exec", container, "createdb", "-U", "detexis", target)
    started = time.monotonic()
    docker("exec", container, "pg_restore", "-U", "detexis", "-d", target, "--exit-on-error", imported)
    elapsed = time.monotonic() - started
    after = fingerprint(container, target)
    if before != after or fingerprint(container, source) != before:
        raise RuntimeError("Restored rows differ, or source changed during rehearsal")
    if sql(container, target, metadata_query) != metadata:
        raise RuntimeError("Restored constraints, indexes or sequence positions differ")
    invalid = sql(container, target, "SELECT count(*) FROM pg_constraint WHERE NOT convalidated;")
    invalid_indexes = sql(container, target, "SELECT count(*) FROM pg_index WHERE NOT indisvalid;")
    if invalid != "0" or invalid_indexes != "0":
        raise RuntimeError("Restored constraints/indexes are invalid")
    return {"source": source, "restored": target, "tables": after,
            "schema_and_sequences_sha256": hashlib.sha256(metadata.encode()).hexdigest(),
            "dump_bytes": host_dump.stat().st_size, "restore_seconds": elapsed,
            "invalid_constraints": 0, "invalid_indexes": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--confirm-disposable", required=True, action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"shield-perf-[a-z0-9-]+", args.project):
        parser.error("Only synthetic shield-perf-* projects are allowed")
    ids = docker("ps", "-aq", "--filter", "label=com.docker.compose.project=" + args.project).split()
    container = validate_fixture(args.project, json.loads(docker("inspect", *ids)) if ids else [])
    folder = args.backup_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower() + "_" + uuid.uuid4().hex[:8]
    restored = "shield_restore_" + suffix
    report_path = folder / (restored + ".json")
    report = {"project": args.project, "passed": False,
              "fixture_database_stopped": False,
              "scope": "Offline synthetic fixture; complete-row round trips from host copies. No off-device restore or application failover."}
    try:
        docker("start", container)
        deadline = time.monotonic() + 60
        while True:
            try:
                docker("exec", container, "pg_isready", "-U", "detexis", "-d", "detexis")
                break
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Fixture database did not become ready")
                time.sleep(1)
        if sql(container, "detexis", "SELECT version_num FROM alembic_version;") != "0009":
            raise RuntimeError("This heartbeat-history rehearsal requires schema 0009")
        report["populated_restore"] = backup_restore(container, "detexis", restored, folder)
        # Seed only the isolated restored copy, leaving the benchmark source intact.
        sql(container, restored, """
BEGIN;
INSERT INTO sensor_health_alerts(id,site_id,opened_at,heartbeat_at,resolved_at,resolution)
SELECT md5('restore-closed-'||id)::uuid::text,id,now()-interval '2 hours',now()-interval '3 hours',
       now()-interval '1 hour','heartbeat_resumed' FROM sites;
INSERT INTO sensor_health_alerts(id,site_id,opened_at,heartbeat_at)
SELECT md5('restore-open-'||id)::uuid::text,id,now(),now()-interval '10 minutes' FROM sites
WHERE NOT EXISTS (SELECT 1 FROM sensor_health_alerts h WHERE h.site_id=sites.id AND h.resolved_at IS NULL);
COMMIT;
""")
        report["health_history_restore"] = backup_restore(container, restored, restored + "_health", folder)
        health = sql(container, restored + "_health", "SELECT count(*),count(*) FILTER (WHERE resolved_at IS NULL),count(*) FILTER (WHERE resolution='heartbeat_resumed') FROM sensor_health_alerts;")
        sites = int(report["populated_restore"]["tables"]["sites"]["rows"])
        if sites < 1 or report["populated_restore"]["tables"]["events"]["rows"] < 1:
            raise RuntimeError("A populated fixture is required")
        report["health_counts"] = health
        if health.split("|")[1] != str(sites) or int(health.split("|")[2]) < sites:
            raise RuntimeError("Expected open and resumed history for every site")
        report["passed"] = True
    except Exception as error:
        report["failure"] = type(error).__name__
        raise
    finally:
        try:
            docker("stop", container)
            report["fixture_database_stopped"] = True
        finally:
            if not report["fixture_database_stopped"]:
                report["passed"] = False
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "report": str(report_path)}))


if __name__ == "__main__":
    main()
