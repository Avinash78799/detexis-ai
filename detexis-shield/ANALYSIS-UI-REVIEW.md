# Authenticated analysis browser acceptance

## Website refresh race regressions — 22 November 2026

The account workspace now renders only the latest requested website list.
Controlled out-of-order tests cover an older success arriving after a newer
failure and an older failure arriving after a newer success. Confirmed account
removal also invalidates pending list responses and clears list status, so a
late response cannot restore cleared list content or an obsolete error. Existing
stale cards and recovery secrets remain preserved when the latest refresh fails.
All twenty JavaScript tests pass. These are interaction regressions; the new
change still requires CI, local activation and rendered acceptance. They do not
establish complete keyboard or assistive-technology acceptance.

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
