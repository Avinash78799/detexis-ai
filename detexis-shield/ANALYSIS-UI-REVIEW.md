# Authenticated analysis browser acceptance

## Per-website action semantics — 22 November 2026

Dashboard links, connection checks, key management, key revocation/replacement
and verification/scan entry controls now include the website in their accessible
names. Connection controls identify a distinct named results region, expose its
expanded/busy state, show loading feedback and remain retryable after failure.
Key-list loading/count/error feedback names the site in a polite status region;
the private issued key is rendered in a separate region without live announcements.
Three interaction regressions use two synthetic sites to check control targeting,
connection loading/failure/retry, key-list recovery and private-key separation
from announcements. All 23 JavaScript tests pass. Commit
`ca6061039cd530d8ccb5cc2db3f27294d48f4a24` passed all four CI jobs in run
`44994620632` and is active locally in API image
`sha256:6c02608c4c2f989ac6b111c1940ce5e585b5070e2eb4a5caf31eca3fafb4673e`.
All 65 application/migration files matched source. A fresh backup preceded the
API update; full table digests and environment values remained unchanged, and
workers/maintenance were not recreated. CA-verified readiness and the served
JavaScript source hash passed. Private evidence:
`outputs/site-controls-runtime-20261122.json`.

Rendered multi-site/screen-reader acceptance remains pending. The existing
synthetic session opened the updated workspace. A reserved test hostname was
entered, but site creation was not submitted: the browser access rule requires
confirmation for its automatically issued persistent sensor key. Two synthetic
sites/keys were proposed together for this check; no actual domain scan is part
of the proposed test. No real-owner account is involved.

## Website refresh race regressions — 22 November 2026

The account workspace now renders only the latest requested website list.
Controlled out-of-order tests cover an older success arriving after a newer
failure and an older failure arriving after a newer success. Confirmed account
removal also invalidates pending list responses and clears list status, so a
late response cannot restore cleared list content or an obsolete error. Existing
stale cards and recovery secrets remain preserved when the latest refresh fails.
All twenty JavaScript tests pass. Commit `0bd8f883d298c12e13bbe34ea31409a5ffd2c857`
passed all four CI jobs in run `44993557821`. The fix is active locally in API
image `sha256:76934e65907417b2962d682f2bad03ff5e6631636c2c0a366d436f75505f4933`.
All 65 application/migration files matched source. A fresh backup preceded the
API-only update; service environment values and complete database row digests
stayed unchanged, and existing workers/maintenance were not recreated.
CA-verified readiness and the served JavaScript source hash passed. Private
evidence: `outputs/refresh-race-runtime-20261122.json`.

The first rendered check was blocked: the embedded browser had a cached
connection-error page, and browser policy refused its internal error-page URL.
The owner manually reopened the local page. A fresh tab binding then showed the
existing approved synthetic account still signed in with an empty website list.
Sending Return to the Refresh websites control re-rendered the empty-state
heading/description, kept the signed-in workspace and left the refresh control
enabled. No site, key, upload, password change or account removal was performed.
No warning/policy bypass or alternate browser was used.

This passes the focused rendered keyboard-activation/refresh check. Out-of-order
network responses and deletion races have JavaScript regression evidence, not
rendered fault-injection acceptance. Full keyboard navigation, focus behavior,
screen-reader announcements and responsive/error-state acceptance remain open.

## Local version 3 recheck — 21 November 2026

The existing embedded-browser tab at `https://localhost:8443/app` rendered the
sign-in page without a security interstitial. Using the owner's explicit local
synthetic-account approval, the browser created one test-only `example.test`
account and opened its signed-in empty workspace. No real-owner session was
changed, and no website, sensor key or file upload was created. Account recovery
secrets and passwords are excluded from this report.

The Detection coverage link rendered release **2026.11.21.1**, twelve rule
families, monitor-only mode, the disabled optional classifier, and the detection
limits. The Threat analysis link then completed three real form submissions:

- An ordinary search query returned **No pattern detected**.
- An inert UNION SELECT query returned **Suspicious pattern detected**, high
  severity, `sqli_union`, CWE-89 and A05:2025, with a review recommendation.
- The benign assignment-boundary query `q=ordinary&&id=42` returned **No pattern
  detected**, replacing the previous SQL finding rather than retaining it.

The file-scanner status changed from loading to ready and displayed definitions
dated 20 November. No local file upload was performed. The rendered result card
and its limitations were visually inspected in the existing narrow browser view;
this was not a measured responsive-layout or accessibility audit.

Chrome's native window inventory exposed Download history rather than the
owner-reported Incognito tab. This embedded-browser check therefore does **not**
close Chrome-specific acceptance. Authenticated refresh/error states, recovery,
removal, complete keyboard navigation and wider viewport checks remain open.
The synthetic account remains signed in; no password manager was used. These
three samples establish UI behavior, not representative detection quality.

## Earlier temporary-origin review — 14 November 2026

A real in-app browser used the restored computer-hosted HTTPS service. The owner
explicitly approved a synthetic test account and a generated harmless text upload
to the exact temporary origin. No real-account credentials were used, no website
or sensor key was created, and no live malware or personal file was submitted.
This synthetic account is not a real monitored-site adoption claim.

Verified interactions:

- Register a synthetic account and navigate through the workspace's Threat
  analysis link. No password/recovery code appears in screenshots or this report.
- Inspect `/search` with a synthetic UNION SELECT query. The rendered result
  showed `sqli_union`, high severity, CWE-89, A05:2025, its reason and next step.
- Inspect the benign `q=union%20membership` example. The result changed to
  `no_pattern_detected`, and the previous SQL finding was removed.
- Upload the explicitly approved 62-byte harmless text fixture through the real
  file chooser. The rendered result showed `no_signature_detected`, its SHA-256,
  byte count, ClamAV 1.4.6 / definitions 28182 and the safety limitation.
- The scanner's readiness message showed definitions dated 13 November and the
  manual Check scanner status control. Offline/stale/recovery/race states have
  Node interaction coverage; this browser session did not stop the live engine
  to simulate those failures.
- At a 390×844 viewport, document width was 375 pixels (vertical scrollbar
  excluded): one column, no horizontal overflow. At 1280×900, document width
  was 1265 pixels and two grid columns were about 588 pixels each. Long hashes
  wrapped inside their result cards. The temporary viewport override was reset.
- Keyboard Tab from Request path reached Query string. This is a focused
  keyboard check, not a full accessibility or assistive-technology audit.

Private task outputs retain desktop/mobile screenshots and the harmless fixture;
screenshots contain no authentication secrets. The synthetic account remains in
the computer instance. This check does not prove all error flows, account recovery,
representative detection quality, real customer usage or persistent availability.

Independent backend acceptance in `threat-analysis-smoke-extended.json` covers
six harmless fixtures, including ZIP-wrapped EICAR and an archive beyond the
8 MiB unpacked budget. That test found a silent per-member skip under the original
1 MiB engine file cap. The engine now allows members up to the aggregate 8 MiB
scan budget; the API still accepts at most 1 MiB of input. The oversized archive
returned `needs_review` with `Heuristics.Limits.Exceeded.MaxScanSize` after the fix.
Other formats and all possible incomplete-inspection cases remain unproven.
