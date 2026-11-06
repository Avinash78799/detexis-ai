# Hosting with no paid services

## Current constraint: no payment-card details

The owner explicitly requires zero paid services **and no card verification**.
Oracle is excluded from the current deployment path; the Oracle instructions
below are retained as reference, not an action to take. No provider account or
paid resource has been created by this guide.

As checked on 6 November 2026:

- [Azure for Students](https://azure.microsoft.com/en-us/free/students/) advertises
  no card and $100 valid for 12 months. Current student eligibility is required.
  This is a possible credit-limited bridge, not permanent free hosting. Do not
  upgrade to a paid subscription; capacity/cost must fit the credit allowance.
- [Northflank pricing](https://northflank.com/pricing) advertises a no-card
  Sandbox, but its [billing documentation](https://northflank.com/docs/v1/application/billing/pricing-on-northflank)
  says all users need a payment method before creating resources and says the
  Sandbox is not for production. These conflicting statements do not establish
  a suitable deployment route. Its status page also reports an ongoing security
  incident review; do not connect project secrets based on the pricing claim.
- [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-overview) documents
  sleeping on free hardware. It does not establish continuous security monitoring
  or durable PostgreSQL storage for this stack.
- Cloudflare Tunnel exposes an origin; the current Docker origin still needs a
  running computer/server. Moving the application to Workers would require an
  explicit architecture migration and new quota/performance/security validation.

No permanent, always-on, cardless host for the complete measured stack has yet
been verified. Continue local validation while checking student eligibility or
access to a permissioned college/community server. Do not silently substitute
sleeping demos, trial credits or a rewritten backend for a verified deployment.

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

### Account signup: verified 6 November 2026

Open https://signup.cloud.oracle.com/ and select your actual country. Verify your
email and complete Oracle's identity/card verification yourself. Keep passwords,
card details, OTPs and private SSH keys outside chat and the repository. Oracle's
FAQ says supported cards may receive temporary authorization holds; these are
not actual service charges. Some card types, including prepaid/virtual cards,
are not accepted. Use accurate details; one free account per person is allowed.

Choose an offered home region suitable for your users. Do not upgrade to Pay As
You Go. Trial credits are separate from Always Free and are not our hosting plan.
After account creation, use the console's Always Free eligibility and resource
limits as the final check before provisioning.

The current documentation lists an A1 Arm allowance equivalent to **2 OCPUs and
12 GB RAM**, with **200 GB combined boot/block storage**. Do not follow older
guides promising larger allowances. A single eligible Ubuntu A1 VM within these
limits is a candidate for the stack; Arm build and actual-host performance still
need validation. The 1 GB E2 Micro is not sufficient evidence for the measured
full-stack workload. If free A1 capacity is unavailable, wait or keep the local
demo rather than choosing a paid shape. Free-tier resources have no SLA and idle
instances may be reclaimed, so off-host backups remain necessary.

Once the console is available, record the selected region and eligible shape.
Create the VM only after checking the console's cost/eligibility summary; use SSH
keys and restrict SSH ingress to your IP. The remaining sections describe service
setup, public HTTPS and validation. Account creation alone does not deploy Shield.

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
