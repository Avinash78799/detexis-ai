"""CI-only acceptance of a disposable local TLS stack; never imports a root.

Creates one synthetic account in the dedicated test project's database. Trusts
only the supplied public CA file within this process; preserves verification.
"""
import argparse
import json
from pathlib import Path
import secrets
import ssl
import time
from uuid import uuid4

import httpx

ORIGIN = "https://localhost:8443"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ca", type=Path, required=True)
    parser.add_argument("--confirm-disposable-ci-stack", action="store_true", required=True)
    args = parser.parse_args()
    context = ssl.create_default_context(cafile=str(args.ca))
    with httpx.Client(base_url=ORIGIN, verify=context, timeout=5, trust_env=False) as client:
        for attempt in range(30):
            try:
                response = client.get("/ready")
                if response.status_code == 200 and response.json() == {"ok":True}:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Local TLS readiness failed")
        body = {"email":"local-tls-"+uuid4().hex+"@example.test", "password":secrets.token_urlsafe(32)}
        created = client.post("/app/api/register", headers={"Origin":ORIGIN}, json=body)
        assert created.status_code == 201, "Synthetic registration failed"
        cookie = created.headers["set-cookie"].lower()
        assert "__host-dxs_session=" in cookie and "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
        assert client.get("/app/api/session").status_code == 200, "HTTPS session cookie was not retained"
        manifest = client.get("/app/api/detection")
        assert manifest.status_code == 200 and manifest.json()["release_record_verified"] is True
        page = client.get("/app/detection")
        assert page.status_code == 200 and manifest.json()["release_id"] in page.text
        assert page.headers["cache-control"] == "no-store"
        health = client.get("/app/api/sensor-health")
        assert health.status_code == 200 and health.json()["open_count"] == 0 and health.json()["alerts"] == []
        assert client.get("/app/sensor-health").status_code == 200
        assert client.post("/app/api/sites", headers={"Origin":ORIGIN}, json={"domain":"fixture.example"}).status_code == 403
        assert client.post("/app/api/login", headers={"Origin":"https://other.example"}, json=body).status_code == 403
        assert client.post("/app/api/login", headers={"Origin":"http://localhost:8443"}, json=body).status_code == 403
    try:
        # Explicit context avoids environment CA overrides. No root was installed.
        with httpx.Client(verify=ssl.create_default_context(), trust_env=False, timeout=5) as untrusted:
            untrusted.get(ORIGIN+"/ready")
    except httpx.ConnectError as error:
        assert "CERTIFICATE_VERIFY_FAILED" in str(error), "Failure was not certificate verification"
    else:
        raise AssertionError("Test root was unexpectedly trusted by the host")
    print(json.dumps({"passed":True,"scope":"Disposable CI stack: CA-verified TLS and hostname, secure-cookie account session, authenticated coverage manifest/page, no-store, missing-CSRF and cross/scheme-origin refusal, default trust refusal. No host trust installation or desktop-browser acceptance."}))


if __name__ == "__main__":
    main()
