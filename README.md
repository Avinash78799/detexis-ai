# Detexis

Detexis Shield is the active product. This branch prepares migration from the old
manual network-feature prediction form to evidence-based website monitoring.

- The root Flask app is a lightweight entry point for the existing Vercel domain.
- **Detexis Shield**, the sensor and monitoring backend, lives in
  [detexis-shield/](detexis-shield/README.md).

Shield includes authenticated ingestion, ASGI/WSGI sensors, 12 detection heuristics,
RQ workers, incident correlation, baselines, alerts, an isolated verified-domain
scanner and an authenticated HTMX dashboard. ML evaluation tooling is implemented;
real-data model validation and production deployment remain acceptance work.
The sensor never blocks requests. See the [evidence/status matrix](detexis-shield/STATUS.md).

Use [computer hosting](detexis-shield/COMPUTER-HOSTING.md) for the chosen free,
computer-hosted instance. See [migration and rollback](MIGRATION.md) before
deploying this branch to the existing Vercel project. Production Vercel has not
been changed merely by editing this branch.

The original analyzer source and dependencies are preserved as text in `archive/`.
Models, CSVs, templates and existing databases are not deleted. Old analyzer and
account endpoints return a migration explanation (HTTP 410); they do not forward
passwords or uploads. Root startup no longer trains models or initializes a DB.

The new authenticated [threat-analysis tools](detexis-shield/THREAT-ANALYSIS.md)
inspect request patterns and offer optional, isolated ClamAV file-signature scans.
No pattern/signature detected does not establish safety.

The root deployment still targets `app.py`. Set `SHIELD_PUBLIC_ORIGIN` to the
operator's current HTTPS origin (without a path) to enable its workspace and
analysis links. If missing/invalid, the page explains setup and links return 503.
An optional, disabled-by-default well-known route supports ownership proof when
`SHIELD_VERIFICATION_TOKEN` is configured; it does not attach a sensor to Vercel.
