# Hosting with no paid services

Use the existing Docker stack on your computer for development and demos. For
a public deployment, an available Oracle Cloud Always Free VM is a possible
host. Free capacity and continued availability are not guaranteed. Oracle can
reclaim idle resources; keep an independent database backup. A computer running
Docker also consumes electricity and disk space.

The default database cache is now 512 MB, with WAL compression and a larger
background-writer allowance. The full local stack has been measured on a roughly
4 GiB Docker VM. Reserve room for PostgreSQL's other allocations, Redis, Python
processes, scanner and OS cache; `shared_buffers` is not a database memory limit.
Set `POSTGRES_SHARED_BUFFERS` for the chosen host and repeat acceptance there.
Do not assume a 1 GiB VM can run the complete measured workload.

## Choose the host

Create an Oracle Free Tier account yourself and select only resources explicitly
labelled Always Free eligible. Check the current console limits and estimated
cost before creating anything. Do not upgrade to paid resources or use temporary
trial credits as a substitute for ongoing free eligibility. Signup may require
identity/payment-card verification. If capacity is unavailable, keep using local
Docker; do not purchase an alternative to follow this guide.

Official sources:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://www.oracle.com/cloud/free/faq/

Render's free services do not cover this architecture: background workers have
no free plan and free PostgreSQL expires after 30 days. See
https://render.com/docs/free and https://render.com/docs/migrate-from-heroku.

## Start privately on the VM

Use a Linux VM with Docker Engine and the Compose plugin. Restrict SSH ingress
to your own source IP, use SSH keys, and leave datastore/scanner ports closed.
Clone the repository and check out the reviewed Shield branch or release. In
`detexis-shield/`, copy `.env.example` to `.env` and replace the development database
password with a long random hexadecimal value. Keep this file private.

```sh
docker compose -f docker-compose.yml -f docker-compose.free.yml up --build -d --wait
docker compose -f docker-compose.yml -f docker-compose.free.yml exec api python create_site.py your-site.example
```

Keep the printed API key and site salt. The override restarts services after a
host reboot, reduces telemetry retention to seven days, and caps Redis at 256 MB
with no eviction. If Redis fills, ingestion fails explicitly and the sensor keeps
the host application running. Pending database events can be recovered after
capacity is restored. Monitor disk usage; PostgreSQL storage is not bounded by
this override. A seven-day retention policy is not a disk quota.

All application endpoints remain bound to VM loopback. Access the dashboard from
your own computer without buying a domain:

```sh
ssh -N -L 8000:127.0.0.1:8000 YOUR_SSH_USER@YOUR_VM_IP
```

Open `http://127.0.0.1:8000/dashboard` locally and use your site key as the password.
The SSH tunnel encrypts this remote connection. This private setup is useful for
validation; external site sensors need a public HTTPS API endpoint.

## Enable public sensors

When you control a DNS hostname, point it at the VM, set `SHIELD_DOMAIN`, permit
ports 80/443, and add the existing TLS proxy:

```sh
docker compose -f docker-compose.yml -f docker-compose.free.yml -f docker-compose.prod.yml up --build -d --wait
```

The proxy needs a DNS hostname under your control. Domain registration is not
included in this plan. Never publish plaintext HTTP with an API key to avoid
buying/configuring TLS. Your existing Vercel application remains a separate site;
the current sensor requires a persistent Python application.

## Validate on the actual VM

Run the documented end-to-end and load checks before claiming the local results
apply to this host. The 500 events/s benchmark used eight exposed Docker CPUs
and about 3.74 GiB memory on a development machine; a free VM may perform
differently. ARM builds and VM performance still require validation on that host.
See `DEPLOYMENT.md` and `BENCHMARKS.md`.

Back up PostgreSQL to an independent location and test restoring into a separate
database. Do not delete your active volume for a restore test. Free hosting does
not provide a permanent uptime guarantee, and a backup on the same VM does not
protect against VM loss.
