# Detexis Shield: Phase 0 + 1 starter

Sensor validation and Flask/WSGI support have been added. See
[PHASE1-NOTES.md](PHASE1-NOTES.md) for usage, checks, and remaining limits.

Working scaffold (about 30% boilerplate). The detection logic, features, ML and dashboard are yours to build.

## Run it
```bash
# Quick local run (SQLite, no Docker)
python -m pip install -r requirements-dev.txt -e sensor-sdk
python -m pytest -q -p no:cacheprovider       # 23 tests should pass

cd backend && python create_site.py demo.local   # prints API key ONCE
uvicorn app.main:app --port 8000

# second terminal
cd demo && pip install -r requirements.txt
SHIELD_API_KEY=<key> uvicorn app:app --port 9000
curl "localhost:9000/search?q=' OR '1'='1&password=x"; curl localhost:9000/.env
# events show up in backend/detexis.db (table: events)

# Postgres + Redis version
docker compose up --build
```

## What already works
- API-key auth (hashed keys, constant-time compare), tenant id taken from the key only
- Idempotent batch ingest (duplicate event_id ignored), batch cap 100, field limits
- SDK: ASGI and WSGI middleware, background batching, bounded buffer, fail-open, query redaction, salted daily IP hash
- Honeytoken flag on `/.env` and `/admin-backup`
- Tests for auth, idempotency, tenant isolation, batch cap, redaction

## Your TODOs (search the code for `TODO(you)`)
1. **Phase 1:** retry with backoff in `client.py`; pull honeytokens from `/v1/config`; real features in `middleware.py` (payload_len, special_char_ratio, req_per_min); rate limit on ingest; Alembic migrations
2. **Phase 1:** a measured overhead test (median under 5 ms, p95 under 10 ms)
3. **Phase 2:** Redis/RQ queue, rule engine (each rule mapped to OWASP/CWE with positive and negative tests), incidents table, live feed page, alerts
4. Write the threat model (one page) before Phase 2

## Known limits of this scaffold
- Request bodies are not captured yet (decide what to capture and how to redact it)
- No per-site salt management or key rotation endpoint
- No ingest rate limiting yet
- Dashboard and user accounts do not exist yet
