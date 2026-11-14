# Dependency security checkpoint

14 November update: CI at `f827c94` blocked release on
`CVE-2026-128089` / `GHSA-vvf4-9x63-8xvv` in dnspython 2.9.0.
API and isolated-scanner pins are updated to the maintainer's patched 2.9.2.
The [advisory](https://github.com/rthalley/dnspython/security/advisories/GHSA-vvf4-9x63-8xvv)
concerns excessive resource use when parsing attacker-controlled WKS zonefile
text. Shield's ordinary DNS lookups do not establish exposure to that exact
parser path; the affected package is still being patched. The audit gate remains
enabled. The older clean audit below is historical, not current release evidence.

CI run `43561554348` at `d4ea1be` then passed the audit with no known findings
in its inspected Python environment, 300 Python tests including real services,
twelve Node tests and ML software smoke. Running API and scanner containers both
reported dnspython 2.9.2. The separate worker registration recovery check passed;
see `WORKER-RECOVERY.md`. These claims do not cover every container OS package or
all third-party client assets.

On 6 November 2026, pip-audit 2.10.1 inspected the installed local validation
environment. The original report identified affected Starlette 0.41.3,
dnspython 2.7.0, Flask 3.1.1, pytest 8.3.4 and pip 24.3.1. Some advisory records
were duplicated by aliases; the raw finding count is not a count of unique flaws.

Updated pins: FastAPI 0.162.0, Starlette 1.10.0, dnspython 2.9.0,
Flask 3.1.3 and pytest 9.0.3. Both Dockerfiles upgrade their installer to
pip 26.2.2. The scanner explicitly pins Pydantic 2.10.4 to match the API.
The framework resolver accepts these versions with the existing Pydantic pin.

The maintainer's [dnspython advisory](https://github.com/rthalley/dnspython/security/advisories/GHSA-45c3-73f7-pv4m)
describes excessive CPU use when decompressing crafted DNS names, fixed in 2.9.0.
[Starlette advisories](https://github.com/Kludex/starlette/security/advisories)
include file-serving and request handling issues. Shield uses StaticFiles, so
absence of multipart forms does not justify retaining the old framework.

After upgrade, pip-audit reported no known vulnerabilities in the inspected
environment. `pip check` passed and 246 tests passed with one real-service skip.
The suite emits an upstream TestClient httpx deprecation warning. CI now audits
its installed application/test environment using a separate audit-tool venv.
The local project itself has no published advisory identity; auditing third-party
packages does not assess Shield's own code or prove the absence of vulnerabilities.

Both API and scanner images subsequently built and started. Audits of the exact
installed Python package lists from both Linux containers also reported no known
vulnerabilities (the local Shield package itself is excluded as unpublished code).
API, worker and maintenance Docker health probes were healthy. Scanner startup
was observed; no real domain was scanned as part of this check.

The real-service assertions from `tests/test_services.py` passed inside the
upgraded API image, using isolated database `shield_upgrade_3b4545e3eae7` and a
previously empty Redis DB 12. Coverage includes migrations, RQ processing,
concurrent ingestion while processing, duplicate-worker exclusion, owner incident
evidence, tenant boundaries and one-use account recovery races. CI run
`42262890822` at source `68c77d8` completed successfully, including its audit gate.

Owner routes were remeasured; see `OWNER-ROUTE-PERFORMANCE.md`. The historical
500 events/s load report still uses the previous framework stack. This is a dated
advisory check, not a security guarantee. Container OS packages, the optional ML
image, concurrent deployment performance and browser acceptance remain separate
release checks.
