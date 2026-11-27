21 November: computer hosting declares and runs three healthy normal RQ workers.
The current release passed an isolated four-site, ten-minute capacity comparison
at 499.844 accepted events/s with processing p95 5.654 seconds. The earlier
two-worker failure remains retained. Only the third local worker was added after
a fresh backup; existing workers, credentials and all table digests were preserved.
See `MULTITENANT-PERFORMANCE.md` for scope and limits. Embedded-browser registration,
coverage navigation and three request-inspector submissions passed; full Chrome,
accessibility and recovery/error-state acceptance remain open.

15 November: the owner chose local-only operation, without a new public tunnel.
The previous temporary hostname expired. Existing computer-instance services were
resumed with their saved volumes/credentials and API/worker readiness verified.
Local HTTPS passed isolated CI and was activated on Windows; the owner reports
warning-free Chrome access after reviewing/importing the public root. Automated
signed-in browser acceptance remains pending. See [LOCAL-HTTPS.md](LOCAL-HTTPS.md).
The historical public-tunnel commands below are for reference, not authorization
to start a new public tunnel after this local-only decision.

# Run Shield on your computer

14 November checkpoint: the existing computer instance was restored without
changing the unrelated Hookpilot services. API, PostgreSQL, Redis, maintenance,
ClamAV and the worker were verified healthy after fixes. The worker now requests
a warm restart after three invalid native registrations; its controlled idle
recovery check passed in about 87 seconds. See `WORKER-RECOVERY.md`. Python
dependency pins include the dnspython 2.9.2 security update. Current rule-release CI passed
326 Python tests and twelve Node tests. Version-2 deployment and a controlled
previous-source rollback passed; current images are explicitly retained. See
`RULE-RELEASES.md` for the limited rehearsal scope. These are local/CI acceptance results,
not a continuous availability promise.

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

Open Docker Desktop and wait until its engine is running. For the initial
installation, run these commands from this directory:

```powershell
python tools/computer.py start --local-https
python tools/computer.py status
```

After a reboot or deliberate stop, resume the existing release:

```powershell
python tools/computer.py resume --local-https
python tools/computer.py status
```

Add `--with-malware` if you already set up ClamAV and want to resume it too.
With `--local-https`, resume also verifies the certificate for `localhost` and
requests `https://localhost:8443/ready` through the proxy. It uses system trust
by default. If Python needs a separate trust file, pass `--ca-file` followed by
the path to the reviewed PEM root certificate exported during local HTTPS setup.
`resume` starts the existing containers and verifies API readiness. If any
requested containers are missing, it reports them before starting anything.
Use the original release configuration if you need to recreate them.

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

The computer overlay starts three RQ workers. An earlier two-worker validation
on this machine ran a four-site, ten-minute rules-only workload at 500.248
events/s with 4.200-second processing p95 and no final backlog. The equivalent
single-worker run failed.
This is a measured configuration, not a capacity guarantee for every computer,
traffic pattern or enabled feature. See `MULTITENANT-PERFORMANCE.md`.

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

Set `SHIELD_SUPPORT_EMAIL` in the saved `.computer.env` to the public address you
want displayed in the workspace and data-handling guide, then recreate only the
API with the reviewed build. This is an optional validated `mailto:` contact for
support/data requests. It does not configure SMTP, send email, verify mailboxes
or enable email alerts/recovery. Keep the saved database password unchanged.

```powershell
python tools/computer.py status
python tools/computer.py logs
python tools/computer.py backup --backup-dir C:\PRIVATE\ShieldBackups
python tools/computer.py stop
```

Replace the backup path with a private directory you control. Backup uses a
unique custom-format PostgreSQL dump and preserves live data. The command copies
the archive into a temporary directory, compares its SHA-256 with the database
container's copy, then publishes the completed `.dump` by renaming it. Its JSON
result includes the checksum for verifying subsequent transfers. Treat dumps as
sensitive: they contain account verifiers and telemetry. A same-computer backup
does not protect against computer loss; keep an encrypted additional copy on
another device/location and rehearse a separate-database restore using
`BACKUP-RESTORE.md`. Backup generation does not prove restore readiness.

Seven-day telemetry retention and a 256 MB Redis cap apply. Retention is not a
disk quota: monitor Docker disk usage. API health checks test dependencies;
worker and maintenance probes test their documented liveness/progress limits.
An unhealthy status does not automatically repair a running unhealthy process.
Keep operator contact and outage/recovery instructions available to site owners.

Hourly aggregate counts retain the complete boundary hour (up to one extra hour)
so cleanup does not erase the seventh same-hour baseline sample during the
current hour. Raw requests still expire at the exact retention cutoff. The
23 November regression checks seven- and thirty-day cleanup at three minute
positions for two sites, preserving their distinct baselines while removing
older counts and expired requests. This is source-level validation; local image
activation is recorded separately in `RELEASE-READINESS.md`.

## Real-user acceptance remains required

Computer hosting resolves the need to obtain a cloud server; it does not supply
site-owner consent, a stable reachable URL, uptime, off-device backups, verified
domain scans, representative ML labels or real adoption. Record only actual
permissioned sites and observed usage. See `RELEASE-READINESS.md` for remaining
checks. The benchmark project and its millions of synthetic events are not users.

Local HTTPS lifecycle: `start --local-https` explicitly includes the optional
proxy after its first setup, without installing trust. Plain `start` leaves the
optional proxy inactive unless it is already running. `status` shows optional
and stopped services; `stop` includes the HTTPS proxy and malware engine while
preserving their volumes. See `SENSOR-HEALTH.md` for migration 0009 and the new
heartbeat-gap signals; running-instance acceptance is separate from source tests.
