# Mixed-traffic checkpoint

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
