"""Bound raw ingest input before FastAPI allocates a JSON object."""
from starlette.responses import JSONResponse


class IngestBodyLimit:
    def __init__(self, app, max_bytes=1024 * 1024):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path == "/v1/events" or path.startswith("/app/api/")):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > (16384 if path.startswith("/app/api/") else self.max_bytes):
                return await JSONResponse({"detail": "ingest body too large"}, 413)(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body", False):
                break
        messages = iter(chunks)

        async def replay():
            return next(messages, {"type": "http.disconnect"})

        await self.app(scope, replay, send)
