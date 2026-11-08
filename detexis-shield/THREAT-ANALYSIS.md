# On-demand threat analysis

Open `/app/analyze` from the signed-in workspace. This replaces the purpose of the
old prediction form with tools whose inputs and evidence match their claims.
No live malware is needed to validate either tool.

## Request inspection

`POST /app/api/analyze/request` accepts a path (2048 characters), query (1024),
user agent (512), and status (100–599). It uses the same bounded single-request
rules as workers and returns rule ID, reason, severity, CWE and OWASP tags.
It makes no network request and does not fetch the pasted path.

Named secret query values are redacted before rule matching, using the sensor's
helper. Do not submit secrets or personal data: redaction is not comprehensive.
Manual samples are not persisted, added to incidents or used for training.
Traffic history, site honeytokens and body inspection are outside this tool's
scope. A no-match result does not establish safety. ML is not used here; no
validated real-traffic model quality is claimed.

## File-signature scanning

`POST /app/api/analyze/file` accepts base64 content for one nonempty file up to
1 MiB. JSON is capped at 1,500,000 bytes; request bodies time out after 15 seconds.
Account sessions, HTTPS Origin, CSRF and a per-owner five-per-minute Redis rate
limit protect the endpoint. Request inspection has its own 30-per-minute limit.
One scan per API process is admitted; others return 503 rather than queueing
unbounded work. The current computer deployment has one API process.

The API streams bytes to ClamD with bounded INSTREAM frames; it never sends a
filesystem path or runs the content. The engine's reply is bounded and timed out.
It returns SHA-256, bytes, engine/definition version and signature, if any.
Definition timestamps must parse and be no older than three days, or the tool
returns unavailable. The managed engine's clock/timezone is UTC.

Verdicts are `signature_detected`, `no_signature_detected`, or `needs_review`.
Heuristic/limit/encryption results require review. Engine/protocol failures do
not become clean results. A no-signature result does not prove safety. This is
not behavioral sandboxing, endpoint protection or a whole-device/site malware
scan. File samples and results are not persisted by the application. ClamD may
use temporary files in its private tmpfs while scanning; no sample volume or
host filesystem is mounted. Container and host administrators remain trusted.

## Optional computer-host engine

```powershell
python tools/computer.py start
python tools/computer.py malware-start
python tools/computer.py status
```

The overlay `docker-compose.malware.yml` uses the official ClamAV 1.4.6 image,
an unprivileged user, separate internal API link and update-egress network, no
published port, no DB/Redis network or secrets, dropped capabilities, a CPU cap
and 2800 MiB memory cap. The engine is optional so normal monitoring can start
without downloading/loading signatures. Its signatures update through FreshClam.
The image seeds a named volume containing public signature definitions; updates
survive container recreation. No samples are stored in that volume. An unavailable engine leaves request
inspection and connected-sensor monitoring available.

This cap is a constrained-computer setting, below ClamAV's preferred 4 GiB engine
allocation. Concurrent definition reload is disabled to reduce peak memory;
scans can be temporarily unavailable during reload. Check actual host memory and
logs. Do not promise uninterrupted file scanning. For higher upload volume or
larger files, provision more resources and re-run isolation/concurrency tests.

```powershell
python tools/computer.py malware-stop
```

Stops only file scanning. `computer.py stop` also stops the optional engine.

Primary references: [INSTREAM protocol](https://docs.clamav.net/manual/Usage/ClamdProtocol.html),
[official images and memory guidance](https://docs.clamav.net/manual/Installing/Docker.html),
[ClamAV releases](https://www.clamav.net/downloads).

Runtime acceptance on 8 November passed with ClamAV 1.4.6 / definitions 28177:
the harmless 68-byte EICAR test returned `Eicar-Test-Signature`; 47 bytes of benign
text returned `no_signature_detected`. API `/ready` passed before and after both
scans. The engine used about 1.01 GiB in a single idle resource snapshot, not a
peak-memory or load benchmark. The container had no published host ports, ran as
`clamav`, and joined only its API-link and update-egress networks.

Reproduce with `python tools/smoke_threat_analysis.py` after engine startup. The
fingerprinted [runtime report](threat-analysis-smoke.json) records the engine,
definition date, sample hashes and scope. This is wiring acceptance with harmless
fixtures, not real-malware recall/FPR, broad file coverage or a load test. The
local suite passed 293 Python tests (one integration skip) and nine Node tests.
Rendered browser acceptance of the new analysis screen remains outstanding.
