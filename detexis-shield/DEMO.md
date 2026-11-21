# Demo and onboarding runbook

## Local recording sequence

1. Run the complete Docker stack and create `demo.local` using DEPLOYMENT.md.
2. Start the demo on localhost:9000 with its API key and unique site salt.
3. Open the authenticated dashboard and show ordinary search traffic first.
4. On localhost only, request `/.env`, then a search query with a UNION SELECT
   example. Show the canary, grouped incident and recon-to-exploit label.
5. Stop the Shield API and show that the demo still responds. Restart it and
   explain bounded retries, drops, pending-row recovery and monitor-only mode.
6. Show an escaped HTML-like path in the feed and a second site's isolated view.
7. Explain that ML is disabled until real data passes evaluation. Show the schema,
   FPR confidence bound and rejected-artifact test rather than synthetic accuracy.
8. After verifying a domain you own, request a scan and explain assessed vs unknown
   checks. Do not present a 0–100 score as a guarantee of security.

Record the screen with your preferred recorder once a persistent demo host is
running. No recorded video is included yet.

## Real-site trial checklist

Get the owner's explicit permission; record hostname, contact, trial dates, data
retention and how to disable/remove the sensor. Create a separate site key and
unique salt. Never share one key/salt among independent owners. Install only on
supported persistent Python processes. Verify ownership for scanning independently
from sensor installation. Agree on alert destinations and redact sensitive URL
data before enabling the trial. Monitor latency and drops during an initial quiet
window; review flagged benign traffic with the owner.

Record measured median/p95 overhead, accepted/processed event counts, lost events,
alerts per 1,000 requests, reviewed false positives and scanner findings. Do not
count a site as monitored until it has actually sent telemetry over the trial.

## Benchmark table to fill with real evidence

| Measurement | Value | Evidence |
| --- | --- | --- |
| Monitored real sites | Not measured | Permission and telemetry records required |
| Real-data classifier FPR / upper confidence bound | Not measured | Frozen evaluation report required |
| 500 events/s sustained for ten minutes | Not measured | Run tools/load_test.py against staging; also measure processing lag |
| Production sensor median/p95 overhead | Not measured | Persistent-host comparison required |
| Notification delivery | Not measured | Owner-configured destination test required |

Resume wording before the trial: “Built Detexis Shield, a Python web security
sensor and monitoring backend with rule detection, incident correlation, a
verified-domain scanner and tested ML-evaluation tooling.” Add an FPR or N real
sites only after the matching evidence exists.
