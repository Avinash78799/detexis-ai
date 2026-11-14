"""Bound raw ingest input before FastAPI allocates a JSON object."""
from starlette.responses import JSONResponse
import asyncio


class IngestBodyLimit:
    def __init__(self, app, max_bytes=1024 * 1024, body_timeout=15):
        self.app, self.max_bytes = app, max_bytes
        self.body_timeout = body_timeout

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path == "/v1/events" or path.startswith("/app/api/")):
            return await self.app(scope, receive, send)
        # Bound upload time as well as bytes. A bytearray also avoids retaining
        # an unbounded number of empty/tiny ASGI message objects.
        limit = (1500000 if path == "/app/api/analyze/file" else
                 16384 if path.startswith("/app/api/") else self.max_bytes)
        body = bytearray()
        try:
            async with asyncio.timeout(self.body_timeout):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > limit:
                        return await JSONResponse({"detail": "ingest body too large"}, 413)(scope, receive, send)
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await JSONResponse({"detail": "Upload timed out"}, 408)(scope, receive, send)
        messages = iter([{"type": "http.request", "body": bytes(body), "more_body": False}])

        async def replay():
            return next(messages, {"type": "http.disconnect"})

        await self.app(scope, replay, send)
