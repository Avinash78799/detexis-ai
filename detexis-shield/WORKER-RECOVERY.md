# Worker registration recovery

14 November: the running worker process was listening, but its native RQ Redis
hash contained only `last_heartbeat`. The existing health probe correctly marked
it unhealthy because its queue and state were missing. This is consistent with
an expired registration being partially recreated after a long pause; the exact
original expiry trigger was not captured, so a host-suspend cause is not proven.

The worker now runs an internal registration watcher. Three consecutive failed
checks, 30 seconds apart, request one SIGTERM. RQ handles that signal as a warm
shutdown and waits for an active job; it is not a forced job kill. The existing
Compose `unless-stopped` policy then starts a new worker with a unique native
registration. A recovered check resets the failure counter. Redis errors count
as failed checks; persistent infrastructure failure can still prevent recovery.

The native health predicate is unchanged. A heartbeat-only hash is not accepted
as healthy, and no custom healthy marker conceals invalid RQ registration. This
watcher does not repair arbitrary container failures, start Docker, prevent
computer sleep or guarantee continuous monitoring.

Unit regressions cover partial registration, recovery between transient failures,
Redis errors and watcher shutdown. The controlled runtime check is:

```powershell
python tools/check_worker_recovery.py --confirm-idle-fault-check --output worker-recovery-check.json
```

It refuses to run unless the instance has zero Site rows, an empty queue and an
idle healthy worker. It removes only that worker's ephemeral registration and
waits for a container restart, a new registration and native health. It does not
touch tenant events or credentials.

The 14 November [runtime report](worker-recovery-check.json) passed: one container
restart, a new registration and native health after 86.625 seconds. Source hashes
were checked against the running worker and local files; the report includes its
image ID. The logs showed a warm shutdown and subsequent queue listening. This
accepts idle registration recovery only. The active-job check below is separate;
a real host suspend and a Redis outage still require validation.


## Active-job registration-loss rehearsal — 22 November

The current version-3 image passed a separate isolated check with normal Linux
RQ fork execution, job timeout and the production registration watcher. A fresh
Redis and worker used a private internal fixture network with no published ports
and no application database connection. The synthetic job incremented a start
marker, waited 120 seconds, incremented a completion marker and returned a fixed
result. Its timeout was 180 seconds.

After confirming the native worker was busy, the harness removed only its own
Redis registration. The watcher requested a warm shutdown. The job finished with
both markers equal to one and the expected result; the worker then restarted
exactly once, acquired a different registration and passed native health.
Recovery from fault injection took **122.844 seconds**, including the remaining
job duration. Both fixture containers were stopped afterward; logs and Redis
volume remain retained. No owner data, sensor queue or real customer job was used.

The aggregate result and exact harness hash are in
[worker-active-recovery-check.json](worker-active-recovery-check.json).
The private task harness is `outputs/check_active_recovery_20261122.py` and its
original report/logs are under `outputs/active-worker-recovery-20261122/`.
This proves one waiting-job warm-shutdown case. It does not establish successful
completion of database-writing jobs during an outage, arbitrary stalled jobs,
host suspend behavior or Redis-outage recovery; those remain separate gates.
