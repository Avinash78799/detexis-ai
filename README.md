# Detexis

This repository contains two stages of the project:

- The existing **Detexis AI** Flask application remains at the repository root.
- **Detexis Shield**, the sensor and monitoring backend under development, lives in
  [detexis-shield/](detexis-shield/README.md).

Shield includes authenticated ingestion, ASGI/WSGI sensors, 12 detection heuristics,
RQ workers, incident correlation, baselines, alerts, an isolated verified-domain
scanner and an authenticated HTMX dashboard. ML evaluation tooling is implemented;
real-data model validation and production deployment remain acceptance work.
The sensor never blocks requests. See the [evidence/status matrix](detexis-shield/STATUS.md).

Start with the [Shield setup and validation notes](detexis-shield/PHASE1-NOTES.md).
The existing app's deployment configuration still targets the root Flask app.
An optional, disabled-by-default well-known route supports ownership proof when
`SHIELD_VERIFICATION_TOKEN` is configured; it does not attach a sensor to Vercel.
