# Detexis Shield threat model

Assets: tenant telemetry, API keys, incident/alert integrity, monitored-site latency,
the scanner's network boundary and the availability of ingestion/processing.
Attackers can control HTTP paths, query strings, user agents and timing on a
monitored site. A compromised sensor key can fabricate events for its own site.
The backend does not assume that telemetry proves an attack or exploit success.

## Trust boundaries and controls

- **Website → SDK:** inputs are untrusted. Bodies and credentials in headers are
  not captured. Query values for named sensitive keys are masked. Parsing, stored
  field sizes and buffer capacity are bounded. A background sender handles network
  work; runtime telemetry errors preserve the host response. Blocking is absent.
- **SDK → API:** HTTPS is required outside localhost. API keys have random secrets,
  SHA-256 storage and constant-time verification. Site identity comes only from
  authentication. Event deduplication uses the site's ID plus event ID, preventing
  cross-tenant ID suppression. Ingest has a 1 MiB body cap and atomic Redis budgets.
  Redis outage returns 503; the sensor continues serving the website.
- **Database → workers:** pending rows survive enqueue failures. Workers serialize
  per site on PostgreSQL, recompute features and ignore claimed honeytoken flags.
  Duplicate jobs skip processed rows. Redis windows use event IDs to avoid counting
  retries twice. There is no promise of exactly-once external notifications.
- **Telemetry → dashboard:** authenticated, read-only pages scope every query to
  the key's site. Jinja auto-escaping, no-store responses, local HTMX and a strict
  CSP address stored XSS. Basic authentication must run behind TLS. A sensor key
  currently also grants site dashboard access; separate read/write scopes are
  future work. Revoking a key prevents subsequent dashboard requests.
- **Backend → scanner:** scanning requires a recent DNS or exact HTTPS-file
  ownership proof. Unverified HTTPS fetches are restricted to the fixed ownership
  path. The scanner runs without DB/Redis credentials or their network. It resolves
  DNS itself, rejects mixed/private/loopback/link-local/multicast/tunnel destinations,
  pins connections to validated IPs and retains the verified hostname for TLS SNI.
  Redirects are limited to that exact domain, re-resolved, checked and never allowed
  to downgrade HTTPS. Ports, redirects, transfer bytes, body bytes and time are capped.
- **Operator → integrations/models:** alert destinations and model paths are operator
  settings, not public URLs or upload endpoints. Joblib artifacts execute trusted
  Python serialization: never load arbitrary uploaded or third-party model files.
  ML is disabled until a schema-compatible evaluated artifact is configured.

## Residual risks and validation gaps

Sensitive data in unrecognized query keys or paths can still be collected. The SDK
is designed for persistent Python worker processes, not Vercel's bounded function
lifecycle. Compromised tenant keys can poison their own telemetry. Regex rules can
be bypassed or flag benign examples of attack syntax; they are not a WAF. Daily IP
hashes group NAT users and cannot prove account identity or credential stuffing.
Incomplete history leaves baselines disabled. A scanner checklist score does not
establish that a site is secure. Container/network controls need live deployment
verification. Edge-level volumetric DDoS protection is outside this application.

See tests for tenant isolation, stored XSS, DNS rebinding, network classification,
redirects, response cleanup, lost acknowledgements and fail-open behavior. Production
load, real data FPR, real notification delivery and real-site onboarding remain
separate acceptance evidence rather than implied by unit tests.
