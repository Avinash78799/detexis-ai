from uuid import uuid4

from fastapi import Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.accounts import COOKIE, digest, owner
from app.db import Base, engine, get_db
from app.main import app
from app.models import BrowserSession


def test_logout_succeeds_if_session_is_invalidated_after_authentication():
    Base.metadata.create_all(engine)
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client, \
            TestClient(app, base_url="https://testserver") as other_device:
        origin = {"Origin":"https://testserver"}
        credentials = {"email":str(uuid4())+"@logout-race.example.test", "password":"Synthetic-logout-passphrase"}
        created = client.post("/app/api/register", headers=origin, json=credentials)
        assert created.status_code == 201
        csrf = created.json()["csrf_token"]
        assert other_device.post("/app/api/login", headers=origin, json=credentials).status_code == 200

        def invalidate_after_auth(request: Request, db=Depends(get_db)):
            user = owner(request, db)  # Authentication and CSRF checks still run.
            # Model concurrent sign-out/recovery completing before the handler.
            db.execute(delete(BrowserSession).where(
                BrowserSession.token_hash == digest(request.cookies[COOKIE])))
            db.commit()
            return user

        app.dependency_overrides[owner] = invalidate_after_auth
        try:
            rejected = client.post("/app/api/logout", headers={**origin,"X-CSRF-Token":"wrong-token"})
            assert rejected.status_code == 403
            response = client.post("/app/api/logout", headers={**origin,"X-CSRF-Token":csrf})
        finally:
            app.dependency_overrides.pop(owner, None)
        assert response.status_code == 204
        assert "max-age=0" in response.headers["set-cookie"].lower()
        assert client.get("/app/api/session").status_code == 401
        assert other_device.get("/app/api/session").status_code == 200
