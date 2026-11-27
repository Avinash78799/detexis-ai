# Mixed-traffic checkpoint

## Version-2 SQL-comment workload: passed 14 November 2026

`mixed-comments-v2-600s.json` records 300,000 accepted workload events at
500.053 events/second over 599.937 seconds. Ingest batch median/p95 was
81.520/160.648 ms; processing median/p95 was 0.187/1.212 seconds, within the
unchanged ten-second p95 target. All 3,000 workload batches returned 202 with
zero transport errors. The final observed database contained 300,003 processed
events (including three functional setup events), with zero pending events,
queued jobs or failed jobs. All processed rows carried the measured version-2
rule-source fingerprint; 30,001 rows had SQL UNION findings (30,000 workload
SQL examples plus one setup example).

The dedicated `detexis-shield-validation-v2` stack used loopback port 18000,
a separate PostgreSQL volume, one RQ worker and no ML model. The computer-hosted
API stayed running separately. Its API and the validation worker were observed
healthy with zero restarts and no memory kill during the run. The workload has
80% benign-shaped requests, 10% sensitive-path probes and 10% comment-separated
SQL examples across 128 synthetic IP hashes for one site. See `VALIDATION.md`
for commands, isolation checks and exact gate definitions.

The original load process finished and persisted its draining checkpoint, then
failed in the final generated evidence query because of Python string quoting.
The corrected query and report completion were run read-only against the same
database after checking unchanged worker/rule identities. The workload was not
repeated and measured latencies were not modified. The exact end-of-load database
snapshot was not preserved; the report marks it null and labels the later
recovery snapshot. Its recorded drain interval covers report completion only.
The runner now saves database/processing snapshots before subsequent queries,
and regression coverage verifies that query failures retain an incomplete report.

This establishes this local, synthetic, single-site rules-only workload. It does
not establish multi-tenant capacity, internet/TLS or sensor overhead, concurrent
browser latency, ML performance, malware scanning capacity, or representative
recall/FPR. Background desktop activity and database history limit comparisons
with the earlier version-1 run; do not attribute timing differences solely to
the detector change.

## Full batched-worker run: passed 7 November 2026

The completed report `mixed-load-batched-600s.json` passed both unchanged gates:
300,000 events at 500 events/s for 600 seconds, and processing p95 <=10 seconds.
Actual acceptance rate was 500.104 events/s. Processing median/p95 was
0.135/1.608 seconds. Ingest median/p95 was 80.295/322.197 ms. All 3,000 HTTP
batches returned 202, with zero transport failures, failed RQ jobs, queued jobs
or pending events at load end. Three functional setup events are additional.

This run used the batched worker introduced at `0012b66`, the upgraded framework,
one RQ worker and ML disabled. The recorded worker SHA256
`053a4b701903d24e3ce7ba708c22d3575a5a9a0623818ba0efe3e92a4d4ed574`
matched the current source. Atomic checkpoint reporting was enabled. One minute
sample reached 1,500 pending and the following sample returned to 100.

The prior 17.814-second failure remains below. The improved result validates
this local synthetic profile; differences in cache, database history and shared
desktop activity prevent assigning the whole change to batching alone. This is
not an actual-host, multi-tenant, concurrent-browser or ML-enabled load result.

## Interrupted candidate run

After the 6 November batching change, a ten-minute run was started but its process
handle was missing on 7 November, Docker was stopped, and no final report existed.
That run is unverified; do not infer a pass or failure from it. The validation
runner now atomically saves initial and minute-by-minute checkpoints, followed by
a draining snapshot and a completed report. Only a completed report with the
acceptance flags proves the gate result. A `running` file may be stale and is
never proof of a live process. Failed serialization preserves the prior snapshot.

## Ten-minute run: latency gate failed

The subsequent full-duration run on 6 November 2026 accepted all 300,000 events
at 500.118 events/s over 600 seconds. There were zero transport failures, failed
RQ jobs or queued jobs after draining. Ingest median/p95 was 71.602/192.916 ms.
Processing median/p95 was 0.171/**17.814 seconds**, exceeding the unchanged
ten-second target. Capacity passed, latency failed, and overall acceptance failed.

The final 7,500 pending events drained in 11.922 seconds. Minute samples were
low until a late rise to 6,700 pending. The worker had zero restarts and was not
OOM-killed. PostgreSQL checkpoint activity was present, but this observation
does not establish the cause of the slowdown. Profiling and a validated fix are
still required. Raw results: `mixed-load-upgraded-600s.json`.

The passing shorter run below does not override this failure. Do not describe
the upgraded stack as meeting the full mixed-load latency release requirement.

## Earlier two-minute run

### Follow-up candidate: batch incident/outbox work

The failed run's per-minute p95 stayed below 2.42 seconds through 17:50 UTC,
then rose to about 19.98 seconds in 17:51 UTC. No worker restart/OOM was observed.
The cause of the late spike remains unproven.

A separate direct-worker profile of 2,000 mixed events in 20 batches found 1,020
SQLAlchemy SQL executions and 148 flush calls. A candidate prefetches all
batch-scoped incident groups and existing outbox identities, allocates incident
IDs locally, and flushes new parents together before adding outbox children.
The Site mutex, tenant predicates and single atomic commit remain in place.

The candidate profile recorded 162 SQL executions and 33 flush calls. Direct
wall time changed from 1.640 to 1.843 seconds; this does **not** prove a speedup
or resolve the failed gate. The local suite passed 249 tests with one service
skip. Existing real-service assertions also passed with the candidate loaded in
an isolated database `shield_upgrade_ac63947ebf2c` and Redis DB 11. A new test
checks twelve client groups across repeated batches, correlation, counts,
idempotency and exactly one outbox entry per incident. Rebuild and full-duration
load validation are still required before calling this a performance fix.

On 6 November 2026, the upgraded local stack accepted and processed 60,000
events at 500 events/second for 120 seconds, with one RQ worker and ML disabled.
The raw report is `mixed-load-upgraded-120s.json`; it records runtime versions,
database settings, migration and worker source hash.

The deterministic `mixed` generator uses eight benign-shaped routes, a honeytoken
hit and a SQLi-shaped query per ten events, rotating across 128 synthetic client
hashes. Event IDs remain unique. No real website is contacted. This is synthetic
capacity evidence and does not establish classifier quality or false-positive rate.

- 60,000 accepted, no HTTP/transport failures; 600 successful batches.
- Ingest median/p95: 65.564/137.458 ms.
- Processing median/p95: 0.107/0.208 seconds, below the ten-second local target.
- No pending events at load end; no failed or queued RQ jobs after measurement.
- Ingest idempotency, worker incident generation, authenticated dashboard and
  host fail-open behavior during a real API stop/start passed before loading.

Post-run queries on synthetic site `5c3c8dfe-e012-47ad-a8a9-0a048e53f3d5`
found 257 incidents and 6,001 event findings each for `honeytoken`,
`sensitive_path` and `sqli_union`. Counts include three functional setup events;
one request can match multiple rules. Incident count depends on five-minute
group boundaries and must not be interpreted as 257 real attacks or users.

This two-minute run does not replace the required ten-minute capacity gate,
actual-host testing, multi-tenant load, concurrent browser load or real-user data.
The earlier ten-minute report used a uniform profile and an older framework.

Reproduce on the dedicated local validation stack:

```sh
python tools/validate_stack.py --profile mixed --rate 500 --seconds 120 --max-processing-p95-seconds 10 --output mixed-load-upgraded-120s.json
```

Set `SHIELD_VALIDATION_COMPOSE` when the validation project uses an override.
The runner deliberately stops/starts its API for the fail-open check and creates
synthetic data. Never target a production stack. Default duration remains 600
seconds and default profile remains `uniform` for historical reproducibility.

Generator SHA256: `dbbc5dd87e3a70f618920dc3594c226d428b336235abb29312c8e9065f489570`.
Runner SHA256: `ec5e5e769b4e705d3f14b931be54353280850fc2857f80d1e6e413529237c6b0`.
