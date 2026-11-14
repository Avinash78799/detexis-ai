# Authenticated analysis browser acceptance — 14 November 2026

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
