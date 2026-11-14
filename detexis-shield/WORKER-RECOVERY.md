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
touch tenant events or credentials. Until a passing runtime report is recorded,
the automated idle-recovery path is not accepted. Active-job recovery, a real
host suspend and a Redis outage require separate validation.
