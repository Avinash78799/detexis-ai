"""Manage the separate computer-hosted instance. Requires Python and Docker Compose.

No cloud account, public port, tunnel, OS startup setting or paid resource is created.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import re
import subprocess
from datetime import datetime, timezone
from uuid import uuid4
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "detexis-shield-computer"
ENV = ROOT / ".computer.env"


def command(*args, capture=False):
    environment = dict(os.environ)
    # Compose must use this instance's saved credentials, not another shell's.
    environment.pop("POSTGRES_PASSWORD", None)
    environment.pop("POSTGRES_SHARED_BUFFERS", None)
    result = subprocess.run(["docker", *args], cwd=ROOT, text=True,
                            capture_output=capture, env=environment)
    if result.returncode:
        raise RuntimeError("Docker command failed; check Docker Desktop and the displayed service logs")
    return result.stdout if capture else None


def prepare_env(path, existing_volume):
    if path.exists():
        passwords = [line.partition("=")[2] for line in path.read_text().splitlines()
                     if line.startswith("POSTGRES_PASSWORD=")]
        if len(passwords) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", passwords[0]):
            raise RuntimeError("Invalid .computer.env: restore its original 64-character hexadecimal database password. Do not change a live database password by editing this file.")
        return
    if existing_volume:
        raise RuntimeError("Database volume already exists but .computer.env is missing. Restore that private file; do not generate a replacement password.")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write("POSTGRES_PASSWORD=" + secrets.token_hex(32) + "\nPOSTGRES_SHARED_BUFFERS=512MB\n")


def compose(*args, capture=False):
    return command("compose", "-p", PROJECT, "--env-file", str(ENV),
                   "-f", "docker-compose.yml", "-f", "docker-compose.computer.yml",
                   "-f", "docker-compose.malware.yml",
                   *args, capture=capture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "logs", "stop", "backup", "malware-start", "malware-stop"])
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    command("info", "--format", "{{.ServerVersion}}", capture=True)
    if args.action == "start":
        volumes = command("volume", "ls", "--format", "{{.Name}}", capture=True).splitlines()
        prepare_env(ENV, PROJECT + "_pgdata" in volumes)
        compose("up", "--build", "-d", "--wait")
        if not compose("port", "api", "8000", capture=True).strip():
            raise RuntimeError("API has no host port mapping. Check port 8000 conflicts before recreating only the API container.")
        with urlopen("http://127.0.0.1:8000/ready", timeout=5) as response:
            if json.load(response) != {"ok": True}:
                raise RuntimeError("Unexpected API readiness response")
        print("Computer instance started. API: http://127.0.0.1:8000/ready")
        print("Account UI requires HTTPS; see COMPUTER-HOSTING.md. Keep .computer.env private and back it up.")
    elif not ENV.exists():
        raise RuntimeError("Start the computer instance first, or restore its .computer.env")
    elif args.action == "status":
        compose("ps")
    elif args.action == "logs":
        compose("logs", "--tail", "100", "api", "worker", "maintenance", "scanner")
    elif args.action == "stop":
        compose("--profile", "malware", "stop")  # Preserve containers, credentials and database volume.
    elif args.action == "malware-start":
        compose("--profile", "malware", "up", "-d", "--wait", "--wait-timeout", "240", "clamav")
    elif args.action == "malware-stop":
        compose("--profile", "malware", "stop", "clamav")
    elif args.action == "backup":
        if args.backup_dir is None:
            parser.error("backup requires --backup-dir pointing to a private directory")
        folder = args.backup_dir.resolve()
        folder.mkdir(parents=True, exist_ok=True)
        name = "shield-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8] + ".dump"
        destination = folder / name
        temporary = "/tmp/" + name
        compose("exec", "-T", "db", "pg_dump", "-U", "detexis", "-d", "detexis", "-Fc", "-f", temporary)
        compose("cp", "db:" + temporary, str(destination))
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("Backup copy is missing or empty; container dump retained")
        compose("exec", "-T", "db", "rm", temporary)
        print(json.dumps({"backup": str(destination), "bytes": destination.stat().st_size,
                          "note": "Local copy only. Keep private; copy off this computer and rehearse restoration."}))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as error:
        raise SystemExit(str(error))
