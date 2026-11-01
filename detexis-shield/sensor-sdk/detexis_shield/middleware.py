import time
import uuid
from datetime import datetime, timezone

from .client import ShieldClient
from .redact import hash_ip, redact_query

HONEYTOKEN_PATHS = {"/.env", "/admin-backup"}  # TODO(you): pull from GET /v1/config


class ShieldMiddleware:
    """Pure ASGI middleware for FastAPI/Starlette."""

    def __init__(self, app, api_url: str, api_key: str, site_salt: str, **client_kwargs):
        self.app = app
        self.site_salt = site_salt
        self.client = ShieldClient(api_url, api_key, **client_kwargs)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            try:  # telemetry must never break the host app
                self._record(scope, status["code"], (time.perf_counter() - start) * 1000)
            except Exception:
                pass

    def _record(self, scope, code: int, latency_ms: float) -> None:
        headers = {k.decode().lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        client = scope.get("client") or ("0.0.0.0", 0)
        path = scope.get("path", "")
        flags = ["honeytoken_hit"] if path in HONEYTOKEN_PATHS else []
        self.client.submit({
            "event_id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "ip_hash": hash_ip(client[0], self.site_salt),
            "method": scope.get("method", "GET")[:10],
            "path": path[:2048],
            "query_redacted": redact_query(scope.get("query_string", b"").decode("latin-1")),
            "ua": headers.get("user-agent", "")[:512],
            "status": code,
            "latency_ms": round(latency_ms, 3),
            "flags": flags,
            "features": {},  # TODO(you): payload_len, special_char_ratio, req_per_min ...
        })
