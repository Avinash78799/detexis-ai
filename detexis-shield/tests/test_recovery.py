from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.accounts import digest
from app.db import SessionLocal
from app.models import User
from test_accounts import ORIGIN


def test_recovery_is_single_use_revokes_old_sessions_and_replaces_code():
    email = "recovery-case@example.test"
    original = "Original-strong-test-passphrase"
    replacement = "Replacement-strong-test-passphrase"
    with TestClient(app, base_url="https://testserver") as first, TestClient(app, base_url="https://testserver") as second, TestClient(app, base_url="https://testserver") as recovery:
        signup = first.post("/app/api/register", headers=ORIGIN, json={"email":email,"password":original})
        assert signup.status_code == 201
        code = signup.json()["recovery_code"]
        assert second.post("/app/api/login", headers=ORIGIN, json={"email":email,"password":original}).status_code == 200
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            assert user.recovery_hash == digest("recovery:" + code) and code not in user.recovery_hash
        changed = recovery.post("/app/api/recover", headers=ORIGIN, json={"email":email,"password":replacement,"recovery_code":code})
        assert changed.status_code == 200
        assert changed.json()["recovery_code"] != code
        assert first.get("/app/api/sites").status_code == 401
        assert second.get("/app/api/sites").status_code == 401
        assert recovery.get("/app/api/sites").status_code == 200
        assert first.post("/app/api/recover", headers=ORIGIN, json={"email":email,"password":original,"recovery_code":code}).status_code == 401
        assert first.post("/app/api/login", headers=ORIGIN, json={"email":email,"password":original}).status_code == 401
        assert first.post("/app/api/login", headers=ORIGIN, json={"email":email,"password":replacement}).status_code == 200


def test_recovery_code_rotation_requires_password_and_csrf():
    with TestClient(app, base_url="https://testserver") as client:
        password = "Recovery-settings-passphrase"
        email = "recovery-settings@example.test"
        registered = client.post("/app/api/register", headers=ORIGIN,json={"email":email,"password":password}).json()
        csrf = {**ORIGIN,"X-CSRF-Token":registered["csrf_token"]}
        assert client.post("/app/api/recovery-code", headers=ORIGIN,json={"password":password}).status_code == 403
        assert client.post("/app/api/recovery-code", headers=csrf,json={"password":"Wrong-long-password"}).status_code == 401
        rotated = client.post("/app/api/recovery-code", headers=csrf,json={"password":password})
        assert rotated.status_code == 200 and rotated.json()["recovery_code"] != registered["recovery_code"]
        assert client.post("/app/api/recover",headers=ORIGIN,json={"email":email,"password":password,"recovery_code":registered["recovery_code"]}).status_code == 401


def test_password_change_requires_current_password_and_revokes_other_sessions():
    with TestClient(app, base_url="https://testserver") as owner, TestClient(app, base_url="https://testserver") as other:
        body = {"email":"password-change@example.test","password":"Current-strong-passphrase"}
        signed = owner.post("/app/api/register",headers=ORIGIN,json=body).json()
        headers = {**ORIGIN,"X-CSRF-Token":signed["csrf_token"]}
        assert other.post("/app/api/login",headers=ORIGIN,json=body).status_code == 200
        assert owner.post("/app/api/password",headers=headers,json={"password":"Wrong-long-password","new_password":"Replacement-strong-passphrase"}).status_code == 401
        updated = owner.post("/app/api/password",headers=headers,json={"password":body["password"],"new_password":"Replacement-strong-passphrase"})
        assert updated.status_code == 200
        assert owner.get("/app/api/sites").status_code == 200
        assert other.get("/app/api/sites").status_code == 401
        assert updated.json()["recovery_code"] != signed["recovery_code"]


def test_malformed_origin_is_rejected_without_server_error():
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/app/api/recover",headers={"Origin":"https://[invalid"},json={"email":"unknown@example.test","password":"Long-test-passphrase","recovery_code":"invalid-long-test-code"})
        assert response.status_code == 403
