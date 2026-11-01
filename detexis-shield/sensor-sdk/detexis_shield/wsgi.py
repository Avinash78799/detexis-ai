"""Flask-compatible WSGI sensor; does not import Flask."""
import time

from .middleware import ShieldMiddleware


class _Response:
    def __init__(self, response, finish):
        self.response = response
        self.iterator = iter(response)
        self.finish = finish
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self.iterator)
        except BaseException:
            self.finish()
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            close = getattr(self.response, "close", None)
            if close is not None:
                close()
        finally:
            self.finish()


class ShieldWSGIMiddleware(ShieldMiddleware):
    """Wrap app.wsgi_app; share event construction with the ASGI sensor.

    Bodies are passed through without being read. Latency includes streaming.
    Forwarded IP headers are ignored unless the host configures a trusted proxy.
    """

    def __call__(self, environ, start_response):
        start = time.perf_counter()
        code = 500
        recorded = False

        def capture_status(status, headers, exc_info=None):
            nonlocal code
            write = start_response(status, headers, exc_info)
            code = int(status.split(" ", 1)[0])
            return write

        def finish():
            nonlocal recorded
            if recorded:
                return
            recorded = True
            try:
                scope = {
                    "client": (environ.get("REMOTE_ADDR") or "0.0.0.0", 0),
                    "method": environ.get("REQUEST_METHOD", "GET"),
                    "path": environ.get("SCRIPT_NAME", "") + environ.get("PATH_INFO", ""),
                    "query_string": environ.get("QUERY_STRING", "").encode("latin-1"),
                    "headers": [(b"user-agent", environ.get("HTTP_USER_AGENT", "").encode("latin-1"))],
                }
                self._record(scope, code, (time.perf_counter() - start) * 1000)
            except Exception:
                pass

        try:
            return _Response(self.app(environ, capture_status), finish)
        except BaseException:
            finish()
            raise
