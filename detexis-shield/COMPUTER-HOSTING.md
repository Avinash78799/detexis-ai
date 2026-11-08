# Run Shield on your computer

Local acceptance on 7 November: the separate instance started with healthy API,
database, Redis, worker and maintenance services. `http://127.0.0.1:8000/ready`
returned `{"ok":true}`. Backup creation and restoration into a separate rehearsal
database at migration `0008` succeeded. The fresh instance had no customer traffic;
this is schema recovery evidence, not an off-device disaster recovery test.
The current suite passed 265 Python tests (one integration skip) and seven Node
tests. After explicit owner approval, a temporary Cloudflare HTTPS tunnel was
started. Its public `/ready` endpoint returned healthy, and a real browser opened
the HTTPS workspace with account creation enabled. The assigned URL is saved in
the private task outputs file `computer-public-url.txt`; it is not a stable URL.

This is the owner's chosen hosting target. No cloud VM, card or paid plan is
required. The computer, Docker Desktop, internet connection and power must remain
available while other websites use it. Sleep, shutdown, Docker exit and internet
outages interrupt monitoring. Sensors fail open and may drop events during an
outage; do not promise continuous coverage or replay of every request.

## Start the separate instance

The signed-in workspace also links to [on-demand threat analysis](THREAT-ANALYSIS.md).
Request inspection is included. File-signature scanning is an optional separate
ClamAV engine: use `python tools/computer.py malware-start` after normal startup.
It requires additional memory and signature updates; unavailable scans never
produce a safety verdict. See that guide for limits and privacy behavior.

Open Docker Desktop and wait until its engine is running. From this directory:

```powershell
python tools/computer.py start
python tools/computer.py status
```

This uses project `detexis-shield-computer`, a separate database volume and private
`.computer.env`. Its random database password is created once, never printed and
ignored by Git. Preserve that file with your private recovery material. If the
database volume exists and the file is lost, startup refuses to invent a new
password. Never edit it to change an existing database's password.

The API is bound to `127.0.0.1:8000`; datastores are loopback-bound and the scanner
is unpublished. If another Shield validation stack owns port 8000, stop that
known project first without removing its volumes. Do not stop unrelated apps.
All services have restart policies. Those policies work only after Docker starts;
they do not start Windows, sign in, prevent sleep or launch Docker Desktop.
Configure Docker Desktop startup and Windows power behavior yourself as desired.

## Open the account UI over HTTPS

The local HTTP endpoint supports diagnostics; account actions require HTTPS.
For a temporary public demonstration, run the installed official cloudflared:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate
```

Open the HTTPS `trycloudflare.com` URL printed by that process. This exposes the
Shield application publicly, including its authenticated APIs, while the tunnel
and computer are running. Do not publish datastore ports or router port forwards.
Use synthetic data until the deployment checks and operator/privacy arrangements
are complete. Create your account, save the one-use recovery code privately, add
your hostname, and follow `/app/install`. Never paste sensor keys in browser code.

The temporary URL changes when the tunnel restarts. Owners must update
`SHIELD_URL` and restart their sensor applications then. This is unsuitable for
an unattended stable real-site trial unless you accept and manage that limitation.
A stable named tunnel needs an account and suitable DNS hostname configuration;
no domain purchase, card or paid service is authorized by this guide. Retain a
local/private deployment if no suitable stable hostname is available.

## Check operations and back up

```powershell
python tools/computer.py status
python tools/computer.py logs
python tools/computer.py backup --backup-dir C:\PRIVATE\ShieldBackups
python tools/computer.py stop
```

Replace the backup path with a private directory you control. Backup uses a
unique custom-format PostgreSQL dump and preserves live data. Treat dumps as
sensitive: they contain account verifiers and telemetry. A same-computer backup
does not protect against computer loss; keep an encrypted additional copy on
another device/location and rehearse a separate-database restore using
`BACKUP-RESTORE.md`. Backup generation does not prove restore readiness.

Seven-day telemetry retention and a 256 MB Redis cap apply. Retention is not a
disk quota: monitor Docker disk usage. API health checks test dependencies;
worker and maintenance probes test their documented liveness/progress limits.
An unhealthy status does not automatically repair a running unhealthy process.
Keep operator contact and outage/recovery instructions available to site owners.

## Real-user acceptance remains required

Computer hosting resolves the need to obtain a cloud server; it does not supply
site-owner consent, a stable reachable URL, uptime, off-device backups, verified
domain scans, representative ML labels or real adoption. Record only actual
permissioned sites and observed usage. See `RELEASE-READINESS.md` for remaining
checks. The benchmark project and its millions of synthetic events are not users.
