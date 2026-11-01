# Detexis

This repository contains two stages of the project:

- The existing **Detexis AI** Flask application remains at the repository root.
- **Detexis Shield**, the sensor and monitoring backend under development, lives in
  [detexis-shield/](detexis-shield/README.md).

Shield currently includes authenticated batch ingestion, ASGI and WSGI sensors,
redaction, daily salted IP hashes, a demo application and sensor validation tests.
Attack detection workers, ML evaluation, incidents, alerts, scanning and the
dashboard are planned work; the current sensor does not block requests.

Start with the [Shield setup and validation notes](detexis-shield/PHASE1-NOTES.md).
The existing app's deployment configuration still targets the root Flask app.
