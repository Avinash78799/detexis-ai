# Dependency security checkpoint

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

This is a dated advisory check, not a security guarantee. Linux-only dependencies,
container OS packages, image builds, real PostgreSQL/Redis integration and the
optional ML image require their corresponding release checks. Historical load
and owner-route reports used the previous framework stack and do not establish
performance of the upgraded stack. Rebuild and validate before deployment.
