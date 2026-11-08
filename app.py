"""Lightweight Detexis entry point; original experiment is preserved in archive/."""
import os
from urllib.parse import urlsplit
from flask import Flask, redirect, render_template
from shield_verification import blueprint


def shield_origin(value):
    """Only accept an operator-configured HTTPS origin, never a request URL."""
    if not value or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        return None
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or url.port not in {None, 443}
                or url.path not in {"", "/"} or url.query or url.fragment):
            return None
        return "https://" + url.netloc
    except ValueError:
        return None


def create_app():
    app = Flask(__name__)
    app.register_blueprint(blueprint)
    app.config["MAX_CONTENT_LENGTH"] = 16384

    @app.after_request
    def headers(response):
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"})
        return response

    def page(archived=False, status=200):
        configured = shield_origin(os.environ.get("SHIELD_PUBLIC_ORIGIN", ""))
        return render_template("shield_entry.html", configured=bool(configured), archived=archived), status

    @app.get("/")
    def index():
        return page()

    @app.get("/shield")
    def shield():
        origin = shield_origin(os.environ.get("SHIELD_PUBLIC_ORIGIN", ""))
        return redirect(origin + "/app", code=303) if origin else page(status=503)

    @app.get("/analyze")
    def analyze():
        origin = shield_origin(os.environ.get("SHIELD_PUBLIC_ORIGIN", ""))
        return redirect(origin + "/app/analyze", code=303) if origin else page(status=503)

    @app.get("/health")
    def health():
        # Liveness of this entry point only, not remote backend readiness.
        return {"ok": True, "service": "detexis-entry"}

    def archived():
        # Never forward old credentials/uploads across origins.
        return page(archived=True, status=410)

    for route in ("/predict", "/signup", "/signin", "/login", "/logon", "/home", "/about",
                  "/analyze_upload", "/download_sample", "/sandbox_parse", "/whitelist_add",
                  "/correlation", "/clear_alerts", "/logout"):
        app.add_url_rule(route, endpoint="archived_" + route[1:], view_func=archived, methods=["GET", "POST"])

    @app.errorhandler(404)
    def missing(error):
        return page(status=404)

    return app


app = create_app()
