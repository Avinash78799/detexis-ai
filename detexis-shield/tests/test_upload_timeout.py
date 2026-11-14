import asyncio
from app.body_limit import IngestBodyLimit


def test_stalled_upload_returns_408_without_entering_application():
    sent = []
    async def receive():
        await asyncio.sleep(1)
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        sent.append(message)
    async def app(*args):
        raise AssertionError("A timed-out body must not enter the endpoint")
    async def run():
        await IngestBodyLimit(app, body_timeout=0.01)(
            {"type": "http", "path": "/app/api/analyze/file"}, receive, send)
    asyncio.run(run())
    assert sent[0]["status"] == 408
    assert b"Upload timed out" in sent[1]["body"]
