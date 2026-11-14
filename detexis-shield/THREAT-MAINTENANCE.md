# Keeping detection current

Current checkpoint: 14 November 2026. This is an implementation and remaining-work
record, not a claim that Shield detects every new attack or unknown vulnerability.

## Implemented

- ClamAV's FreshClam process updates official malware definitions while the
  optional engine and its network connection are available. The application
  rejects definition metadata older than three days. Signature updates do not
  upgrade the engine binary or add web-request detection rules.
- Authenticated file readiness distinguishes an unconfigured/unavailable engine,
  stale definitions, an in-progress check and readiness. Metadata probes are
  cached for five seconds; every actual scan checks independently. This change
  has local regression coverage and focused runtime/browser acceptance; see
  `ANALYSIS-UI-REVIEW.md` for the scope and remaining failure-state checks.
- CI audits installed Python dependencies and checks rules, auth/tenant boundaries,
  pipelines and frontend interactions. Twelve bundled web-detection heuristics
  remain a limited baseline, not a comprehensive maintained WAF rule set.

## Prepared for activation

`../.github/dependabot.yml` prepares daily Python dependency-update PRs and weekly
Dockerfile/GitHub Actions update PRs. It must reach the default branch before
GitHub version-update checks activate. Updates are reviewed and tested, not
automatically merged or deployed. Repository policies may also require enabling
Dependabot alerts/security updates. No successful bot run is claimed yet.

This does not monitor every Compose image or the bundled HTMX asset. Those still
need explicit release review, including ClamAV engine patches, PostgreSQL/Redis,
scanner images and relevant operating-system packages. A passing package audit
is not a complete software supply-chain security assessment.

## Versioned web-release path

The new `2026.11.14.1` / version-2 source update, packaged fingerprints, immutable
release records, CI version gate, event provenance and owner coverage page are
implemented with regression coverage. See `RULE-RELEASES.md` for commands, exact
scope and the controlled runtime/rollback acceptance report. The original twelve families
remain; tested SQL-comment coverage and cross-field false-positive handling are
improved. No real-traffic quality claim follows from the fixture tests.

## Remaining detection-update work

1. Review CISA KEV and vendor advisories for actively exploited vulnerabilities.
   Determine applicability from owner-provided technology/version inventory.
   A feed entry alone does not prove a monitored site is vulnerable or under attack.
2. Maintain the implemented versioned web-release process with source references,
   supported inputs, known blind spots and stable rule identifiers. Broader CRS integration
   requires a compatible detection engine and privacy/input review; the current
   Python regex engine cannot simply execute CRS rules.
3. Add representative attack, encoding/evasion and legitimate-traffic regression
   cases before releasing an updated detector. Measure false positives on
   permissioned traffic and preserve detection-only operation.
4. Extend the completed empty-instance rollback rehearsal to isolated traffic/job
   recovery scenarios and maintain release regression gates. The coverage page shows the installed source and explicitly reports that
   a live web-rule feed is not connected. Do not download and execute arbitrary remote code
   or accept unreviewed regex patterns as updates.
5. Evaluate ML only with provenance-reviewed data, time/session separation and
   independent tests. Do not automatically learn labels from an attacker-controlled
   request stream or from an unreviewed incident decision.

These steps require continued maintenance after launch. They cannot guarantee
zero-day detection or compensate for missing telemetry, an offline computer,
application authorization flaws or unpatched underlying software.

Primary references: [FreshClam signature updates](https://docs.clamav.net/manual/Usage/SignatureManagement.html),
[CISA KEV prioritization](https://content.govdelivery.com/accounts/USDHSCISA/bulletins/425854d),
[CRS tuning and false positives](https://coreruleset.org/docs/2-how-crs-works/2-2-paranoia_levels/),
[Dependabot activation](https://docs.github.com/en/code-security/concepts/supply-chain-security/about-the-dependabot-yml-file).
